#!/usr/bin/env python3
"""
Test script to verify Docker environment is properly configured.
"""
import sys
import subprocess
from playwright.sync_api import sync_playwright


def test_kiro_cli():
    """Test if kiro-cli is installed and accessible."""
    print("Testing kiro-cli...")
    try:
        result = subprocess.run(
            ["kiro-cli", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"✓ kiro-cli found: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("✗ kiro-cli not found in PATH")
        return False
    except Exception as e:
        print(f"✗ Error testing kiro-cli: {e}")
        return False


def test_playwright():
    """Test if Playwright can launch Chromium in headless mode."""
    print("\nTesting Playwright + Chromium...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ]
            )
            page = browser.new_page()
            page.goto("https://www.google.com")
            title = page.title()
            browser.close()
            print(f"✓ Playwright working, page title: {title}")
            return True
    except Exception as e:
        print(f"✗ Playwright test failed: {e}")
        return False


def main():
    print("=" * 60)
    print("Docker Environment Test")
    print("=" * 60)

    results = []
    results.append(("kiro-cli", test_kiro_cli()))
    results.append(("Playwright", test_playwright()))

    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{name:20s} {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("All tests passed! Environment is ready.")
        return 0
    else:
        print("Some tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
