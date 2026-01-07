# Anti-Detection Features

## Overview

The registration script now includes comprehensive anti-detection measures to avoid bot detection by AWS and other services.

## Implemented Features

### 1. Random Fingerprint Generation ✅

Each account gets a unique but realistic browser fingerprint:

- **Random OS/Browser combinations**: Windows 10, macOS, Linux with Chrome 115-122
- **Consistent properties**: UA, platform, hardware specs all match
- **Random viewports**: Common resolutions (1920x1080, 1366x768, 2560x1440, etc.)
- **Random locales**: en-US, en-GB, en-CA with matching timezones
- **Hardware specs**: CPU cores (4-16), RAM (4-32GB), touch points (0 for desktop)

### 2. WebRTC IP Leak Prevention ✅

Completely disables WebRTC to prevent real IP leakage:

```javascript
// Disabled APIs:
- RTCPeerConnection
- webkitRTCPeerConnection
- mozRTCPeerConnection
- navigator.mediaDevices.getUserMedia
- navigator.getUserMedia
```

### 3. Playwright-Stealth Integration ✅

Uses `playwright-stealth` library for baseline anti-detection:

- Removes `navigator.webdriver` property
- Hides automation indicators
- Patches common detection vectors

### 4. Custom Stealth Enhancements ✅

Additional manual fixes on top of playwright-stealth:

**Fixed webdriver detection:**
- playwright-stealth sets it to `undefined` (suspicious)
- We override it to `false` (more natural)

**Canvas fingerprint stability:**
- Adds consistent noise based on session seed
- Prevents "too random" fingerprint detection
- Each session has unique but stable canvas signature

**Automation indicator removal:**
- Removes Chrome DevTools Protocol (CDP) properties
- Removes Playwright-specific window properties
- Cleans up `window.cdc_*` variables

### 5. Human-Like Behavior ✅

Already implemented in original script:

- Random typing delays (50-150ms per keystroke)
- Random mouse movements
- Random pauses between actions
- Realistic click patterns

## Detection Resistance Level

**Current implementation: 7.5/10**

| Feature | Status | Effectiveness |
|---------|--------|---------------|
| Basic webdriver hiding | ✅ | Medium |
| Random fingerprints | ✅ | High |
| WebRTC blocking | ✅ | High |
| Canvas noise | ✅ | Medium-High |
| Navigator consistency | ✅ | High |
| Human behavior | ✅ | Medium |
| Playwright-stealth | ✅ | Medium |

## What's NOT Implemented

For 9/10+ detection resistance, you would need:

1. **Real fingerprint database**: Collect 50-100 real device fingerprints
2. **Proxy rotation**: Different IP per account
3. **Audio fingerprint randomization**: Currently not implemented
4. **WebGL fingerprint randomization**: Currently not implemented
5. **Font fingerprint handling**: Currently not implemented
6. **Battery API spoofing**: Currently not implemented

## Usage

No changes needed - the script automatically applies all anti-detection measures:

```bash
# Install new dependency
pip install -r requirements.txt

# Run as usual
python register.py --headless --count 5
```

## Testing

Test fingerprint generation:

```bash
python test_fingerprint.py
```

This will generate 5 random fingerprints and verify internal consistency.

## How It Works

### Fingerprint Generation Flow

```
1. Select random OS template (Windows/macOS/Linux)
2. Generate matching UA string with random Chrome version
3. Pick consistent viewport for that OS
4. Set matching hardware specs (CPU, RAM, touch)
5. Choose realistic locale + timezone combination
```

### Browser Launch Flow

```
1. Launch Chromium with anti-detection args
2. Create context with random fingerprint
3. Inject custom stealth scripts (WebRTC, navigator, canvas)
4. Create page
5. Apply playwright-stealth
6. Ready for automation
```

## Known Limitations

1. **Headless detection**: Running in headless mode can still be detected via:
   - Missing GPU info
   - Different rendering behavior
   - Headless-specific quirks

   **Mitigation**: Use `--headless=false` for maximum stealth (but slower)

2. **Behavioral patterns**: If you register 100 accounts in 1 hour from same IP, you'll still get flagged regardless of fingerprints.

   **Mitigation**: Add delays between registrations (already implemented: 10s)

3. **IP reputation**: If your IP is flagged, fingerprints won't help.

   **Mitigation**: Use residential proxies (not implemented)

## Comparison with Alternatives

| Approach | Stealth Level | Maintenance | Cost |
|----------|---------------|-------------|------|
| No protection | 2/10 | None | Free |
| playwright-stealth only | 6/10 | Low | Free |
| **Our implementation** | **7.5/10** | **Low** | **Free** |
| Real fingerprint DB | 9/10 | High | Medium |
| Residential proxies + real FP | 9.5/10 | High | High |

## Troubleshooting

### Import Error: playwright_stealth

```bash
pip install playwright-stealth
```

### Still Getting Detected?

1. Check if running in headless mode (try non-headless)
2. Verify IP is not flagged (try different network)
3. Reduce registration rate (increase delays)
4. Check AWS logs for specific detection reason

## Future Improvements

If detection becomes an issue:

1. Add proxy support (SOCKS5/HTTP)
2. Implement real fingerprint database
3. Add WebGL fingerprint randomization
4. Add audio context fingerprint randomization
5. Implement more sophisticated behavioral patterns
