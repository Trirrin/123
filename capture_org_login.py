#!/usr/bin/env python3
"""
mitmproxy script to capture Kiro organization login mode API calls.
Specifically captures:
1. Access token acquisition endpoint
2. Quota/usage query endpoint

Usage:
    mitmdump -s capture_org_login.py --set block_global=false

Then run kiro-cli with proxy:
    HTTPS_PROXY=http://127.0.0.1:8080 kiro-cli <your-command>
"""

import json
import logging
from datetime import datetime
from mitmproxy import http, ctx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class KiroOrgLoginCapture:
    """Capture Kiro organization login API calls"""

    def __init__(self):
        self.captured_requests = []
        self.output_file = f"kiro_org_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Target endpoints to capture
        self.target_patterns = [
            # Access token endpoints
            "token",
            "auth",
            "login",
            "sso",
            "bearer",
            # Quota/usage endpoints
            "quota",
            "usage",
            "limit",
            "subscription",
            "billing",
            "account",
            "organization",
            "org",
        ]

        logger.info("=" * 80)
        logger.info("Kiro Organization Login Capture Script Started")
        logger.info(f"Output file: {self.output_file}")
        logger.info("Monitoring for token and quota endpoints...")
        logger.info("=" * 80)

    def request(self, flow: http.HTTPFlow) -> None:
        """Intercept and log requests"""
        url = flow.request.pretty_url
        method = flow.request.method

        # Check if this is a target endpoint
        if self._is_target_endpoint(url):
            logger.info(f"\n{'='*80}")
            logger.info(f"🎯 CAPTURED REQUEST: {method} {url}")
            logger.info(f"{'='*80}")

            # Log headers
            logger.info("\n📋 Request Headers:")
            for key, value in flow.request.headers.items():
                # Mask sensitive data
                if key.lower() in ['authorization', 'cookie', 'x-api-key']:
                    value = self._mask_sensitive(value)
                logger.info(f"  {key}: {value}")

            # Log request body if present
            if flow.request.content:
                logger.info("\n📦 Request Body:")
                try:
                    body = flow.request.content.decode('utf-8')
                    try:
                        body_json = json.loads(body)
                        logger.info(json.dumps(body_json, indent=2, ensure_ascii=False))
                    except json.JSONDecodeError:
                        logger.info(body)
                except UnicodeDecodeError:
                    logger.info(f"  [Binary data, {len(flow.request.content)} bytes]")

    def response(self, flow: http.HTTPFlow) -> None:
        """Intercept and log responses"""
        url = flow.request.pretty_url

        if self._is_target_endpoint(url):
            status_code = flow.response.status_code
            logger.info(f"\n📥 RESPONSE: {status_code}")

            # Log response headers
            logger.info("\n📋 Response Headers:")
            for key, value in flow.response.headers.items():
                if key.lower() in ['set-cookie', 'authorization']:
                    value = self._mask_sensitive(value)
                logger.info(f"  {key}: {value}")

            # Log response body
            if flow.response.content:
                logger.info("\n📦 Response Body:")
                try:
                    body = flow.response.content.decode('utf-8')
                    try:
                        body_json = json.loads(body)
                        logger.info(json.dumps(body_json, indent=2, ensure_ascii=False))

                        # Highlight important fields
                        self._highlight_important_fields(body_json)
                    except json.JSONDecodeError:
                        logger.info(body[:1000])  # First 1000 chars
                except UnicodeDecodeError:
                    logger.info(f"  [Binary data, {len(flow.response.content)} bytes]")

            # Save to file
            self._save_capture(flow)

            logger.info(f"\n{'='*80}\n")

    def _is_target_endpoint(self, url: str) -> bool:
        """Check if URL matches target patterns"""
        url_lower = url.lower()

        # Must be HTTPS
        if not url.startswith('https://'):
            return False

        # Exclude telemetry only
        if 'telemetry' in url_lower:
            return False

        # Capture all AWS requests
        return 'amazonaws.com' in url_lower

    def _mask_sensitive(self, value: str) -> str:
        """Mask sensitive data but keep structure visible"""
        if len(value) <= 20:
            return value[:4] + "****" + value[-4:]
        else:
            return value[:8] + "****" + value[-8:]

    def _highlight_important_fields(self, data: dict, prefix: str = "") -> None:
        """Highlight important fields in response"""
        important_keys = [
            'access_token', 'accessToken', 'token', 'bearer',
            'refresh_token', 'refreshToken',
            'quota', 'usage', 'limit', 'remaining',
            'expires_in', 'expiresIn', 'expiry',
            'organization', 'org', 'orgId',
            'subscription', 'plan', 'tier'
        ]

        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key

                if key.lower() in [k.lower() for k in important_keys]:
                    logger.info(f"\n⭐ IMPORTANT: {full_key} = {value}")

                # Recurse into nested structures
                if isinstance(value, dict):
                    self._highlight_important_fields(value, full_key)
                elif isinstance(value, list) and value and isinstance(value[0], dict):
                    for i, item in enumerate(value):
                        self._highlight_important_fields(item, f"{full_key}[{i}]")

    def _save_capture(self, flow: http.HTTPFlow) -> None:
        """Save captured request/response to file"""
        capture_data = {
            'timestamp': datetime.now().isoformat(),
            'request': {
                'method': flow.request.method,
                'url': flow.request.pretty_url,
                'headers': dict(flow.request.headers),
                'body': self._decode_content(flow.request.content)
            },
            'response': {
                'status_code': flow.response.status_code,
                'headers': dict(flow.response.headers),
                'body': self._decode_content(flow.response.content)
            }
        }

        self.captured_requests.append(capture_data)

        # Write to file
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.captured_requests, f, indent=2, ensure_ascii=False)
            logger.info(f"💾 Saved to {self.output_file}")
        except Exception as e:
            logger.error(f"Failed to save capture: {e}")

    def _decode_content(self, content: bytes) -> any:
        """Decode content to JSON or string"""
        if not content:
            return None

        try:
            text = content.decode('utf-8')
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        except UnicodeDecodeError:
            return f"[Binary data, {len(content)} bytes]"

    def done(self):
        """Called when mitmproxy shuts down"""
        # Always save file even if empty
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(self.captured_requests, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save final capture: {e}")

        logger.info("\n" + "=" * 80)
        logger.info(f"Capture session ended. Total captures: {len(self.captured_requests)}")
        logger.info(f"Data saved to: {self.output_file}")
        logger.info("=" * 80)


# Create addon instance
addons = [KiroOrgLoginCapture()]
