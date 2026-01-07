#!/usr/bin/env python3
"""Test fingerprint generation to verify consistency."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from register import generate_random_fingerprint

def test_fingerprint_consistency():
    """Test that generated fingerprints are internally consistent."""
    print("Testing fingerprint generation...\n")

    for i in range(5):
        print(f"=== Fingerprint {i+1} ===")
        fp = generate_random_fingerprint()

        print(f"User-Agent: {fp['user_agent']}")
        print(f"Platform: {fp['platform']}")
        print(f"Viewport: {fp['viewport']}")
        print(f"Hardware Concurrency: {fp['hardware_concurrency']}")
        print(f"Device Memory: {fp['device_memory']} GB")
        print(f"Max Touch Points: {fp['max_touch_points']}")
        print(f"Locale: {fp['locale']}")
        print(f"Timezone: {fp['timezone']}")

        # Verify consistency
        ua = fp['user_agent']
        platform = fp['platform']

        # Check Windows consistency
        if 'Windows' in ua:
            assert platform == 'Win32', f"Windows UA but platform is {platform}"
            assert fp['max_touch_points'] == 0, "Windows desktop should have 0 touch points"
            print("✅ Windows fingerprint is consistent")

        # Check macOS consistency
        elif 'Macintosh' in ua:
            assert platform == 'MacIntel', f"macOS UA but platform is {platform}"
            assert fp['max_touch_points'] == 0, "macOS should have 0 touch points"
            print("✅ macOS fingerprint is consistent")

        # Check Linux consistency
        elif 'Linux' in ua:
            assert 'Linux' in platform, f"Linux UA but platform is {platform}"
            assert fp['max_touch_points'] == 0, "Linux desktop should have 0 touch points"
            print("✅ Linux fingerprint is consistent")

        print()

    print("All fingerprints are internally consistent! ✅")

if __name__ == "__main__":
    test_fingerprint_consistency()
