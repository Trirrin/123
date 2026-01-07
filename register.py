#!/usr/bin/env python3
"""
Kiro Auto Register - Automate AWS Builder ID registration and kiro-cli login.
Usage: python register.py [--headless] [--count N]
"""

import argparse
import functools
import json
import os
import random
import re
import secrets
import sqlite3
import string
import subprocess
import sys
import time
from pathlib import Path

import requests
from faker import Faker
from imapclient import IMAPClient
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth


CONFIG_FILE = Path(__file__).parent / "config.json"
KIRO_DB_PATH = Path.home() / ".local" / "share" / "kiro-cli" / "data.sqlite3"
DEVICE_AUTH_URL = "https://view.awsapps.com/start/#/device"
BUILDER_ID_URL = "https://profile.aws.amazon.com/"


def retry_on_failure(max_attempts: int = 3, delay: float = 2.0, backoff: float = 2.0):
    """Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_attempts:
                        print(f"[RETRY] {func.__name__} failed after {max_attempts} attempts")
                        raise

                    print(f"[RETRY] {func.__name__} attempt {attempt}/{max_attempts} failed: {e}")
                    print(f"[RETRY] Retrying in {current_delay:.1f}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff

            raise last_exception
        return wrapper
    return decorator


def human_delay(min_sec: float = 0.5, max_sec: float = 1.5):
    """Add random human-like delay."""
    time.sleep(random.uniform(min_sec, max_sec))


def generate_random_fingerprint() -> dict:
    """Generate random but realistic browser fingerprint.

    Returns a dict with viewport, user_agent, platform, and other browser properties
    that are internally consistent (e.g., Windows UA matches Win32 platform).
    """
    # Define realistic fingerprint templates.
    templates = [
        # Windows 10 + Chrome
        {
            "os": "Windows",
            "platform": "Win32",
            "ua_os": "Windows NT 10.0; Win64; x64",
            "chrome_version": random.randint(115, 122),
            "viewport": random.choice([
                {"width": 1920, "height": 1080},
                {"width": 1366, "height": 768},
                {"width": 1536, "height": 864},
                {"width": 2560, "height": 1440},
            ]),
            "hardware_concurrency": random.choice([4, 8, 12, 16]),
            "device_memory": random.choice([4, 8, 16]),
            "max_touch_points": 0,
        },
        # macOS + Chrome
        {
            "os": "macOS",
            "platform": "MacIntel",
            "ua_os": "Macintosh; Intel Mac OS X 10_15_7",
            "chrome_version": random.randint(115, 122),
            "viewport": random.choice([
                {"width": 1440, "height": 900},
                {"width": 1680, "height": 1050},
                {"width": 1920, "height": 1080},
                {"width": 2560, "height": 1440},
            ]),
            "hardware_concurrency": random.choice([4, 8, 10, 12]),
            "device_memory": random.choice([8, 16, 32]),
            "max_touch_points": 0,
        },
        # Linux + Chrome
        {
            "os": "Linux",
            "platform": "Linux x86_64",
            "ua_os": "X11; Linux x86_64",
            "chrome_version": random.randint(115, 122),
            "viewport": random.choice([
                {"width": 1920, "height": 1080},
                {"width": 1366, "height": 768},
                {"width": 2560, "height": 1440},
            ]),
            "hardware_concurrency": random.choice([4, 8, 12, 16]),
            "device_memory": random.choice([4, 8, 16]),
            "max_touch_points": 0,
        },
    ]

    template = random.choice(templates)
    chrome_version = template["chrome_version"]

    # Build consistent user agent.
    user_agent = (
        f"Mozilla/5.0 ({template['ua_os']}) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{chrome_version}.0.0.0 Safari/537.36"
    )

    # Random but realistic locale.
    locale = random.choice(["en-US", "en-GB", "en-CA"])
    timezone = random.choice([
        "America/New_York",
        "America/Chicago",
        "America/Los_Angeles",
        "America/Denver",
        "Europe/London",
        "America/Toronto",
    ])

    return {
        "user_agent": user_agent,
        "viewport": template["viewport"],
        "platform": template["platform"],
        "hardware_concurrency": template["hardware_concurrency"],
        "device_memory": template["device_memory"],
        "max_touch_points": template["max_touch_points"],
        "locale": locale,
        "timezone": timezone,
    }


def get_stealth_init_scripts(fingerprint: dict) -> list:
    """Generate init scripts for advanced anti-detection.

    These scripts fix known playwright-stealth issues and add extra protections:
    - WebRTC IP leak prevention
    - Consistent navigator properties
    - Canvas/WebGL fingerprint stability
    """
    scripts = []

    # Script 1: Fix webdriver detection (stealth sets it to undefined, we make it false).
    scripts.append("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => false,
            configurable: true
        });
    """)

    # Script 2: Disable WebRTC to prevent IP leaks.
    scripts.append("""
        // Disable WebRTC completely
        if (window.RTCPeerConnection) {
            window.RTCPeerConnection = undefined;
        }
        if (window.webkitRTCPeerConnection) {
            window.webkitRTCPeerConnection = undefined;
        }
        if (window.mozRTCPeerConnection) {
            window.mozRTCPeerConnection = undefined;
        }
        if (navigator.mediaDevices) {
            navigator.mediaDevices.getUserMedia = undefined;
        }
        if (navigator.getUserMedia) {
            navigator.getUserMedia = undefined;
        }
    """)

    # Script 3: Override navigator properties to match fingerprint.
    scripts.append(f"""
        Object.defineProperty(navigator, 'platform', {{
            get: () => '{fingerprint["platform"]}',
            configurable: true
        }});

        Object.defineProperty(navigator, 'hardwareConcurrency', {{
            get: () => {fingerprint["hardware_concurrency"]},
            configurable: true
        }});

        Object.defineProperty(navigator, 'deviceMemory', {{
            get: () => {fingerprint["device_memory"]},
            configurable: true
        }});

        Object.defineProperty(navigator, 'maxTouchPoints', {{
            get: () => {fingerprint["max_touch_points"]},
            configurable: true
        }});
    """)

    # Script 4: Add subtle Canvas noise (makes fingerprint unique but stable per session).
    scripts.append("""
        // Add consistent canvas noise to avoid detection
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        const originalToBlob = HTMLCanvasElement.prototype.toBlob;
        const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;

        // Generate session-specific noise seed
        const noiseSeed = Math.random();

        const addNoise = (canvas, context) => {
            const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
            for (let i = 0; i < imageData.data.length; i += 4) {
                // Add minimal noise based on seed (not purely random)
                const noise = (Math.sin(noiseSeed * i) * 2) | 0;
                imageData.data[i] = imageData.data[i] + noise;
                imageData.data[i + 1] = imageData.data[i + 1] + noise;
                imageData.data[i + 2] = imageData.data[i + 2] + noise;
            }
            context.putImageData(imageData, 0, 0);
        };

        HTMLCanvasElement.prototype.toDataURL = function() {
            if (this.width > 0 && this.height > 0) {
                const context = this.getContext('2d');
                if (context) addNoise(this, context);
            }
            return originalToDataURL.apply(this, arguments);
        };
    """)

    # Script 5: Remove automation indicators.
    scripts.append("""
        // Remove common automation indicators
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

        // Hide Playwright-specific properties
        delete window.__playwright;
        delete window.__pw_manual;
        delete window.__PW_inspect;
    """)

    return scripts


def human_type(element, text: str):
    """Type text with human-like delays between keystrokes."""
    element.click()
    human_delay(0.3, 0.6)
    for char in text:
        element.type(char, delay=random.randint(50, 150))
        if random.random() < 0.1:  # 10% chance of extra pause.
            human_delay(0.1, 0.3)


def human_click(page, locator):
    """Click with mouse movement simulation."""
    element = locator.first
    element.scroll_into_view_if_needed()
    human_delay(0.2, 0.5)

    # Get element bounding box.
    box = element.bounding_box()
    if box:
        # Move to random point within element.
        x = box["x"] + random.uniform(box["width"] * 0.3, box["width"] * 0.7)
        y = box["y"] + random.uniform(box["height"] * 0.3, box["height"] * 0.7)
        page.mouse.move(x, y)
        human_delay(0.1, 0.3)
        page.mouse.click(x, y)
    else:
        element.click()

    human_delay(0.3, 0.8)


def load_config():
    """Load configuration from config.json."""
    if not CONFIG_FILE.exists():
        print(f"Error: {CONFIG_FILE} not found.")
        print(f"Copy config.example.json to config.json and fill in your settings.")
        sys.exit(1)
    return json.loads(CONFIG_FILE.read_text())


def generate_identity(email_domain: str) -> dict:
    """Generate a random identity with realistic name and human-like email."""
    fake = Faker("en_US")
    first_name = fake.first_name()
    last_name = fake.last_name()
    full_name = f"{first_name} {last_name}"

    # Generate human-like email with multiple realistic patterns.
    first_lower = first_name.lower()
    last_lower = last_name.lower()
    first_initial = first_lower[0]

    # Choose email pattern randomly with weighted probabilities.
    pattern = random.choices(
        ["classic", "year", "initial_last", "last_initial", "short_number", "middle_initial"],
        weights=[40, 20, 15, 10, 10, 5],
        k=1
    )[0]

    if pattern == "classic":
        # Classic full name: john.smith, johnsmith, john_smith
        separator = random.choice([".", "_", ""])
        email = f"{first_lower}{separator}{last_lower}@{email_domain}"

    elif pattern == "year":
        # Name + birth year: john1995, john.1992
        year = random.randint(1985, 2002)  # Realistic age range
        separator = random.choice(["", "."])
        email = f"{first_lower}{separator}{year}@{email_domain}"

    elif pattern == "initial_last":
        # First initial + last name: jsmith, j.smith
        separator = random.choice(["", "."])
        email = f"{first_initial}{separator}{last_lower}@{email_domain}"

    elif pattern == "last_initial":
        # Last name + first initial: smithj, smith.j
        separator = random.choice(["", "."])
        email = f"{last_lower}{separator}{first_initial}@{email_domain}"

    elif pattern == "short_number":
        # Full name + short number (lucky number style): johnsmith23, john.smith7
        separator = random.choice(["", ".", "_"])
        number = random.randint(1, 99)  # Short, looks like lucky number
        email = f"{first_lower}{separator}{last_lower}{number}@{email_domain}"

    else:  # middle_initial
        # Fake middle initial: john.m.smith, johnmsmith
        middle_initial = random.choice(string.ascii_lowercase)
        separator = random.choice([".", ""])
        if separator:
            email = f"{first_lower}{separator}{middle_initial}{separator}{last_lower}@{email_domain}"
        else:
            email = f"{first_lower}{middle_initial}{last_lower}@{email_domain}"

    # Generate password meeting AWS requirements:
    # - At least 8 characters
    # - Uppercase, lowercase, number, special char
    password = (
        secrets.choice(string.ascii_uppercase)
        + secrets.choice(string.ascii_lowercase)
        + secrets.choice(string.digits)
        + secrets.choice("!@#$%^&*")
        + "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
    )
    # Shuffle to avoid predictable pattern.
    password = "".join(random.sample(password, len(password)))

    return {
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "email": email,
        "password": password,
    }


def fetch_verification_code(config: dict, target_email: str, timeout: int = 120) -> str:
    """Fetch AWS verification code from IMAP server.

    Searches for emails sent TO the target email address.
    """
    import ssl as ssl_module

    imap_cfg = config["imap"]
    print(f"Connecting to IMAP server {imap_cfg['host']}...")

    # Build SSL context if needed.
    ssl_context = None
    if imap_cfg.get("starttls") or imap_cfg.get("use_ssl"):
        ssl_context = ssl_module.create_default_context()
        if not imap_cfg.get("verify_cert", True):
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl_module.CERT_NONE

    # Connect to IMAP.
    if imap_cfg.get("use_ssl"):
        client = IMAPClient(imap_cfg["host"], port=imap_cfg["port"], ssl_context=ssl_context)
    else:
        client = IMAPClient(imap_cfg["host"], port=imap_cfg["port"], ssl=False)
        if imap_cfg.get("starttls"):
            client.starttls(ssl_context=ssl_context)

    with client:
        client.login(imap_cfg["username"], imap_cfg["password"])
        client.select_folder("INBOX")

        start_time = time.time()
        print(f"Waiting for verification email to {target_email}...")

        while time.time() - start_time < timeout:
            # Refresh mailbox.
            client.noop()

            # Search for emails TO target address from AWS.
            messages = client.search(["TO", target_email, "FROM", "no-reply@signin.aws"])
            if not messages:
                # Fallback: try broader AWS sender search.
                messages = client.search(["TO", target_email, "FROM", "aws"])

            if messages:
                # Check newest message first.
                for msg_id in sorted(messages, reverse=True):
                    data = client.fetch([msg_id], ["BODY[]"])
                    body = data[msg_id][b"BODY[]"].decode("utf-8", errors="ignore")

                    # Extract 6-digit verification code.
                    # Pattern 1: "Verification code: 123456"
                    match = re.search(r"[Vv]erification\s+code:+\s*(\d{6})", body)
                    if not match:
                        # Pattern 2: Standalone 6-digit code on its own line.
                        match = re.search(r"^\s*(\d{6})\s*$", body, re.MULTILINE)

                    if match:
                        code = match.group(1)
                        print(f"Found verification code: {code}")
                        return code

            elapsed = int(time.time() - start_time)
            print(f"Waiting for verification email... ({elapsed}s / {timeout}s)")
            time.sleep(5)

    raise TimeoutError(f"No verification code received within {timeout} seconds")


def safe_page_load(page, url: str, max_attempts: int = 3) -> bool:
    """Load page with retry on failure."""
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"Loading page (attempt {attempt}/{max_attempts}): {url}")
            page.goto(url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=30000)
            print("Page loaded successfully")
            return True
        except Exception as e:
            print(f"Page load failed: {e}")
            if attempt < max_attempts:
                print(f"Retrying in 2s...")
                time.sleep(2)
            else:
                print(f"Page load failed after {max_attempts} attempts")
                return False
    return False


def safe_wait_for_element(page, locator_str: str, timeout: int = 10000, max_attempts: int = 3):
    """Wait for element with page refresh retry on failure."""
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"Waiting for element (attempt {attempt}/{max_attempts}): {locator_str}")
            locator = page.locator(locator_str).first
            locator.wait_for(state="visible", timeout=timeout)
            print("Element found")
            return locator
        except PlaywrightTimeout:
            print(f"Element not found within {timeout}ms")
            if attempt < max_attempts:
                print("Refreshing page and retrying...")
                page.reload(timeout=30000)
                page.wait_for_load_state("networkidle", timeout=30000)
                human_delay(2, 3)
            else:
                print(f"Element not found after {max_attempts} attempts")
                raise
    return None


@retry_on_failure(max_attempts=3, delay=2.0)
def register_builder_id(page, identity: dict, config: dict) -> bool:
    """Register AWS Builder ID using Playwright with human-like behavior."""
    print(f"\n=== Registering AWS Builder ID ===")
    print(f"Name: {identity['full_name']}")
    print(f"Email: {identity['email']}")

    try:
        # Go to Builder ID signup with retry.
        if not safe_page_load(page, BUILDER_ID_URL):
            return False
        human_delay(2, 3)

        # Accept cookies if present.
        accept_btn = page.locator('button:has-text("接受"), button:has-text("Accept")')
        if accept_btn.first.is_visible():
            print("Accepting cookies...")
            human_click(page, accept_btn)
            human_delay(1, 2)

        # Fill email - the input has placeholder="username@example.com".
        email_input = safe_wait_for_element(
            page,
            'input[placeholder*="@"], input[type="text"], input[type="email"]'
        )
        print(f"Filling email: {identity['email']}")
        human_type(email_input, identity["email"])
        human_delay(0.5, 1)

        # Click continue button.
        continue_btn = page.locator('button:has-text("继续"), button:has-text("Continue")')
        human_click(page, continue_btn)
        page.wait_for_load_state("networkidle")
        human_delay(2, 3)

        # Fill name on next page - find the text input that's not email.
        name_input = safe_wait_for_element(
            page,
            'input[type="text"][autocomplete="on"], input[type="text"]:not([placeholder*="@"])'
        )
        print(f"Filling name: {identity['full_name']}")
        human_type(name_input, identity["full_name"])
        human_delay(0.5, 1)

        continue_btn = page.locator('button:has-text("继续"), button:has-text("Continue")')
        human_click(page, continue_btn)
        page.wait_for_load_state("networkidle")
        human_delay(2, 3)

        # Wait for and fetch verification code.
        print("Waiting for verification email...")
        code = fetch_verification_code(config, identity["email"])

        # Fill verification code.
        code_input = safe_wait_for_element(
            page,
            'input[type="text"], input[name="code"], input[placeholder*="code"]',
            timeout=30000
        )
        print(f"Filling verification code: {code}")
        human_type(code_input, code)
        human_delay(0.5, 1)

        # Submit code.
        verify_btn = page.locator('button:has-text("验证"), button:has-text("Verify"), button:has-text("继续"), button:has-text("Continue")')
        human_click(page, verify_btn)
        page.wait_for_load_state("networkidle")
        human_delay(2, 3)

        # Set password - wait for password fields to appear.
        print("Waiting for password fields...")
        password_input = safe_wait_for_element(
            page,
            'input[type="password"]',
            timeout=30000
        )
        human_delay(1, 2)

        password_inputs = page.locator('input[type="password"]').all()
        print(f"Found {len(password_inputs)} password field(s)")
        print(f"Setting password: {identity['password']}")

        # First password field.
        human_type(password_inputs[0], identity["password"])
        human_delay(0.5, 1)

        # Confirm password if there's a second field.
        if len(password_inputs) > 1:
            human_type(password_inputs[1], identity["password"])
            human_delay(0.5, 1)

        # Submit - find the visible submit button (not cookie buttons).
        human_delay(1, 2)  # Wait for validation.

        # Debug: print all visible buttons.
        print("Available visible buttons:")
        for btn in page.locator('button:visible').all():
            try:
                text = btn.text_content().strip()
                if text:
                    print(f"  - {text}")
            except:
                pass

        # Look for the main form submit button - exclude cookie buttons.
        submit_btn = page.locator('button:visible:has-text("创建"), button:visible:has-text("Create AWS Builder ID"), button:visible:has-text("继续"), button:visible:has-text("Continue")').first
        human_click(page, submit_btn)
        page.wait_for_load_state("networkidle")
        human_delay(3, 5)

        print("Builder ID registration completed!")
        return True

    except PlaywrightTimeout as e:
        print(f"Timeout during registration: {e}")
        page.screenshot(path="error_registration.png")
        return False
    except Exception as e:
        print(f"Error during registration: {e}")
        page.screenshot(path="error_registration.png")
        return False


def start_kiro_cli_login() -> subprocess.Popen:
    """Start kiro-cli login in device flow mode."""
    print("\n=== Starting kiro-cli login ===")

    # Logout first if already logged in.
    subprocess.run(["kiro-cli", "logout"], capture_output=True)

    # Start login with device flow.
    proc = subprocess.Popen(
        ["kiro-cli", "login", "--license", "free", "--use-device-flow"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc


def extract_device_code(proc: subprocess.Popen, timeout: int = 30) -> str:
    """Extract device code from kiro-cli output."""
    start_time = time.time()
    output = ""

    while time.time() - start_time < timeout:
        line = proc.stdout.readline()
        if not line:
            # Check if process died.
            if proc.poll() is not None:
                print(f"kiro-cli process exited with code {proc.returncode}")
                raise RuntimeError(f"kiro-cli exited unexpectedly with code {proc.returncode}")
            time.sleep(0.1)
            continue

        output += line
        print(f"kiro-cli: {line.strip()}")

        # Check for errors.
        if "error:" in line.lower() or "dispatch failure" in line.lower():
            print(f"kiro-cli error detected: {line.strip()}")
            proc.terminate()
            raise RuntimeError(f"kiro-cli failed: {line.strip()}")

        # Look for device code.
        match = re.search(r"Code:\s*([A-Z0-9-]+)", output)
        if match:
            return match.group(1)

    proc.terminate()
    raise TimeoutError("Failed to get device code from kiro-cli")


@retry_on_failure(max_attempts=3, delay=2.0)
def complete_device_auth(page, identity: dict, device_code: str) -> bool:
    """Complete device authorization in browser with human-like behavior."""
    print(f"\n=== Completing device authorization ===")
    print(f"Device code: {device_code}")

    try:
        # Go to device auth page with retry.
        url = f"{DEVICE_AUTH_URL}?user_code={device_code}"
        if not safe_page_load(page, url):
            return False
        human_delay(2, 3)

        # Check if we need to login (not already logged in from registration).
        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="@"]').first
        if email_input.is_visible():
            print("Logging in with Builder ID...")
            human_type(email_input, identity["email"])
            human_delay(0.5, 1)

            next_btn = page.locator('button:has-text("Next"), button:has-text("Continue"), button:has-text("继续")')
            human_click(page, next_btn)
            page.wait_for_load_state("networkidle")
            human_delay(2, 3)

            # Enter password.
            password_input = safe_wait_for_element(
                page,
                'input[type="password"]',
                timeout=10000
            )
            human_type(password_input, identity["password"])
            human_delay(0.5, 1)

            submit_btn = page.locator('button:has-text("Sign in"), button:has-text("Continue"), button:has-text("登录")')
            human_click(page, submit_btn)
            page.wait_for_load_state("networkidle")
            human_delay(3, 5)
        else:
            print("Already logged in, skipping login step...")

        # Wait for and click allow/authorize button.
        human_delay(2, 3)

        # Debug: print all visible buttons.
        print("Device auth page - visible buttons:")
        for btn in page.locator('button:visible').all():
            try:
                text = btn.text_content().strip()
                if text:
                    print(f"  - {text}")
            except:
                pass

        # Step 1: Click "Confirm and continue".
        confirm_btn = safe_wait_for_element(
            page,
            'button:visible:has-text("Confirm and continue"), button:visible:has-text("Confirm"), button:visible:has-text("确认")',
            timeout=30000
        )
        human_click(page, page.locator('button:visible:has-text("Confirm and continue"), button:visible:has-text("Confirm"), button:visible:has-text("确认")'))
        page.wait_for_load_state("networkidle")
        human_delay(2, 3)

        # Step 2: Click "Allow access".
        allow_btn = safe_wait_for_element(
            page,
            'button:visible:has-text("Allow access"), button:visible:has-text("Allow"), button:visible:has-text("允许")',
            timeout=30000
        )
        human_click(page, page.locator('button:visible:has-text("Allow access"), button:visible:has-text("Allow"), button:visible:has-text("允许")'))
        page.wait_for_load_state("networkidle")
        human_delay(3, 5)

        print("Device authorization completed!")
        return True

    except PlaywrightTimeout as e:
        print(f"Timeout during device auth: {e}")
        page.screenshot(path="error_device_auth.png")
        return False
    except Exception as e:
        print(f"Error during device auth: {e}")
        page.screenshot(path="error_device_auth.png")
        return False


def wait_for_kiro_login(proc: subprocess.Popen, timeout: int = 60) -> bool:
    """Wait for kiro-cli login to complete."""
    print("Waiting for kiro-cli login to complete...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        # Check if process finished.
        ret = proc.poll()
        if ret is not None:
            # Read remaining output.
            remaining = proc.stdout.read()
            if remaining:
                print(f"kiro-cli: {remaining.strip()}")

            if ret == 0:
                print("kiro-cli login successful!")
                return True
            else:
                print(f"kiro-cli login failed with code {ret}")
                return False

        # Read any available output.
        line = proc.stdout.readline()
        if line:
            print(f"kiro-cli: {line.strip()}")
            if "successfully" in line.lower() or "logged in" in line.lower():
                return True

        time.sleep(0.5)

    print("Timeout waiting for kiro-cli login")
    proc.terminate()
    return False


@retry_on_failure(max_attempts=3, delay=1.0)
def extract_tokens() -> dict:
    """Extract tokens from kiro-cli SQLite database."""
    print("\n=== Extracting tokens ===")

    if not KIRO_DB_PATH.exists():
        raise FileNotFoundError(f"kiro-cli database not found: {KIRO_DB_PATH}")

    conn = sqlite3.connect(str(KIRO_DB_PATH))
    cursor = conn.cursor()

    # Get token data.
    cursor.execute("SELECT value FROM auth_kv WHERE key='kirocli:odic:token'")
    token_row = cursor.fetchone()

    # Get device registration (client_id, client_secret).
    cursor.execute("SELECT value FROM auth_kv WHERE key='kirocli:odic:device-registration'")
    reg_row = cursor.fetchone()

    conn.close()

    if not token_row:
        raise ValueError("No token found in database")

    token_data = json.loads(token_row[0])
    result = {
        "refresh_token": token_data.get("refresh_token", ""),
        "access_token": token_data.get("access_token", ""),
    }

    if reg_row:
        reg_data = json.loads(reg_row[0])
        result["client_id"] = reg_data.get("client_id", "")
        result["client_secret"] = reg_data.get("client_secret", "")

    print(f"Extracted refresh_token: {result['refresh_token'][:50]}...")
    print(f"Extracted client_id: {result.get('client_id', 'N/A')[:30]}...")
    print(f"Extracted client_secret: {result.get('client_secret', 'N/A')[:30]}...")

    return result


@retry_on_failure(max_attempts=3, delay=2.0)
def add_to_backend(config: dict, identity: dict, tokens: dict) -> bool:
    """Add account to backend API."""
    print("\n=== Adding account to backend ===")

    url = f"{config['backend_url']}/api/accounts"
    payload = {
        "name": identity["full_name"],
        "refresh_token": tokens["refresh_token"],
        "auth_type": "cli",
        "client_id": tokens.get("client_id", ""),
        "client_secret": tokens.get("client_secret", ""),
        "priority": 0,
    }

    # Build headers with authorization.
    headers = {"Content-Type": "application/json"}
    admin_password = config.get("admin_password", "")
    if admin_password:
        headers["Authorization"] = f"Bearer {admin_password}"

    print(f"POST {url}")
    print(f"Name: {payload['name']}")

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            print(f"Account added successfully!")
            print(f"Response: {resp.json()}")
            return True
        elif resp.status_code == 401:
            print(f"Unauthorized! Check admin_password in config.json")
            return False
        else:
            print(f"Failed to add account: {resp.status_code}")
            print(f"Response: {resp.text}")
            return False
    except Exception as e:
        print(f"Error adding account: {e}")
        return False


def register_single_account(account_num: int, config: dict, headless: bool) -> dict:
    """Register a single account.

    Returns:
        dict with keys: success (bool), identity (dict), error (str)
    """
    print(f"\n{'='*60}")
    print(f"[Account {account_num}] Starting registration")
    print(f"{'='*60}")

    # Generate identity.
    identity = generate_identity(config["email_domain"])
    print(f"[Account {account_num}] Generated identity:")
    print(f"[Account {account_num}]   Name: {identity['full_name']}")
    print(f"[Account {account_num}]   Email: {identity['email']}")

    # Save identity for reference.
    identity_file = Path(__file__).parent / f"identity_account_{account_num}.json"
    identity_file.write_text(json.dumps(identity, indent=2))

    # Generate random fingerprint for this account.
    fingerprint = generate_random_fingerprint()
    print(f"[Account {account_num}] Generated fingerprint:")
    print(f"[Account {account_num}]   Platform: {fingerprint['platform']}")
    print(f"[Account {account_num}]   Viewport: {fingerprint['viewport']}")
    print(f"[Account {account_num}]   Locale: {fingerprint['locale']}")

    with sync_playwright() as p:
        # Launch browser with anti-detection args.
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-web-security",  # Sometimes needed for stealth
                "--disable-features=IsolateOrigins,site-per-process",
            ]
        )

        # Create context with random fingerprint.
        context = browser.new_context(
            user_agent=fingerprint["user_agent"],
            viewport=fingerprint["viewport"],
            locale=fingerprint["locale"],
            timezone_id=fingerprint["timezone"],
            # Additional realistic settings
            color_scheme="light",
            device_scale_factor=1,
            has_touch=fingerprint["max_touch_points"] > 0,
            is_mobile=False,
        )

        # Apply stealth scripts BEFORE creating page.
        stealth_scripts = get_stealth_init_scripts(fingerprint)
        for script in stealth_scripts:
            context.add_init_script(script)

        page = context.new_page()

        # Apply playwright-stealth (this adds additional protections).
        stealth = Stealth()
        stealth.apply_stealth_sync(page)

        try:
            # Step 1: Register Builder ID (with retry).
            try:
                if not register_builder_id(page, identity, config):
                    return {
                        "success": False,
                        "identity": identity,
                        "error": "Failed to register Builder ID"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "identity": identity,
                    "error": f"Fatal error during Builder ID registration: {e}"
                }

            # Step 2-3: Start kiro-cli login and get device code (with retry).
            device_code = None
            max_kiro_attempts = 3
            for kiro_attempt in range(1, max_kiro_attempts + 1):
                try:
                    print(f"[Account {account_num}] Starting kiro-cli login (attempt {kiro_attempt}/{max_kiro_attempts})...")
                    proc = start_kiro_cli_login()
                    device_code = extract_device_code(proc)
                    print(f"[Account {account_num}] Got device code: {device_code}")
                    break
                except Exception as e:
                    print(f"[Account {account_num}] kiro-cli attempt {kiro_attempt} failed: {e}")
                    if kiro_attempt < max_kiro_attempts:
                        print(f"[Account {account_num}] Retrying in 3s...")
                        time.sleep(3)
                    else:
                        return {
                            "success": False,
                            "identity": identity,
                            "error": f"kiro-cli failed after {max_kiro_attempts} attempts: {e}"
                        }

            # Step 4: Complete device auth (with retry).
            try:
                if not complete_device_auth(page, identity, device_code):
                    proc.terminate()
                    return {
                        "success": False,
                        "identity": identity,
                        "error": "Failed to complete device authorization"
                    }
            except Exception as e:
                proc.terminate()
                return {
                    "success": False,
                    "identity": identity,
                    "error": f"Fatal error during device authorization: {e}"
                }

            # Step 5: Wait for kiro-cli to finish.
            if not wait_for_kiro_login(proc):
                return {
                    "success": False,
                    "identity": identity,
                    "error": "kiro-cli login did not complete successfully"
                }

            # Step 6: Extract tokens (with retry).
            try:
                tokens = extract_tokens()
            except Exception as e:
                return {
                    "success": False,
                    "identity": identity,
                    "error": f"Fatal error extracting tokens: {e}"
                }

            # Step 7: Add to backend (with retry).
            try:
                if not add_to_backend(config, identity, tokens):
                    return {
                        "success": False,
                        "identity": identity,
                        "error": "Failed to add account to backend"
                    }
            except Exception as e:
                return {
                    "success": False,
                    "identity": identity,
                    "error": f"Fatal error adding to backend: {e}"
                }

            print(f"\n[Account {account_num}] {'='*60}")
            print(f"[Account {account_num}] SUCCESS! Account registered.")
            print(f"[Account {account_num}] {'='*60}")

            return {
                "success": True,
                "identity": identity,
                "error": None
            }

        except Exception as e:
            print(f"\n[Account {account_num}] [FATAL] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "identity": identity,
                "error": f"Unexpected error: {e}"
            }
        finally:
            browser.close()


def main():
    # Parse arguments.
    parser = argparse.ArgumentParser(description="Kiro Auto Register - Batch account registration")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--count", type=int, default=1, help="Number of accounts to register sequentially (default: 1)")
    args = parser.parse_args()

    print("=" * 60)
    print("Kiro Auto Register - Sequential Mode")
    print("=" * 60)
    print(f"Accounts to register: {args.count}")
    print(f"Headless: {args.headless}")
    print("=" * 60)

    # Load config.
    config = load_config()
    print(f"Backend URL: {config['backend_url']}")
    print(f"Email domain: {config['email_domain']}")

    results = []
    for i in range(1, args.count + 1):
        print(f"\n{'='*60}")
        print(f"Starting registration {i}/{args.count}")
        print(f"{'='*60}")

        result = register_single_account(i, config, args.headless)
        results.append(result)

        if result["success"]:
            print(f"\n[Main] Account {i}/{args.count} registered successfully")
        else:
            print(f"\n[Main] Account {i}/{args.count} failed: {result['error']}")

        # Add delay between registrations to avoid rate limiting.
        if i < args.count:
            print(f"\n[Main] Waiting 10s before next registration...")
            time.sleep(10)

    # Print summary.
    print("\n" + "=" * 60)
    print("BATCH REGISTRATION SUMMARY")
    print("=" * 60)

    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count

    print(f"Total attempts: {args.count}")
    print(f"Successful: {success_count}")
    print(f"Failed: {fail_count}")

    if success_count > 0:
        print("\nSuccessful accounts:")
        for i, r in enumerate(results, 1):
            if r["success"]:
                print(f"  {i}. {r['identity']['email']} ({r['identity']['full_name']})")

    if fail_count > 0:
        print("\nFailed accounts:")
        for i, r in enumerate(results, 1):
            if not r["success"]:
                identity = r.get("identity")
                if identity:
                    print(f"  {i}. {identity['email']} - {r['error']}")
                else:
                    print(f"  {i}. Unknown - {r['error']}")

    print("=" * 60)

    # Return 0 if at least one succeeded, 1 if all failed.
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
