#!/usr/bin/env python
"""
Check Response Required emails from IMAP inbox.
"""
import ssl as ssl_module
from imapclient import IMAPClient

# IMAP config
IMAP_HOST = "mail.tribios.top"
IMAP_PORT = 143
IMAP_USER = "xr@tribios.top"
IMAP_PASS = "Password123"

def check_response_required_emails():
    """Connect to IMAP and check Response Required emails."""
    print(f"Connecting to IMAP server {IMAP_HOST}...")

    # Build SSL context
    ssl_context = ssl_module.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl_module.CERT_NONE

    # Connect to IMAP
    client = IMAPClient(IMAP_HOST, port=IMAP_PORT, ssl=False)
    client.starttls(ssl_context=ssl_context)

    with client:
        client.login(IMAP_USER, IMAP_PASS)
        client.select_folder("INBOX")

        # Search for "Response Required" emails
        print("\nSearching for 'Response Required' emails...")
        messages = client.search(["SUBJECT", "Response Required"])

        if not messages:
            print("No 'Response Required' emails found.")
            return

        print(f"Found {len(messages)} email(s) with 'Response Required' subject.\n")

        # Fetch and display the most recent one
        msg_id = sorted(messages, reverse=True)[0]
        print(f"=" * 80)
        print(f"Message ID: {msg_id}")

        # Fetch envelope info
        envelope_data = client.fetch([msg_id], ["ENVELOPE"])
        envelope = envelope_data[msg_id][b"ENVELOPE"]

        print(f"From: {envelope.from_[0].mailbox.decode()}@{envelope.from_[0].host.decode()}")
        print(f"Subject: {envelope.subject.decode()}")
        print(f"Date: {envelope.date}")

        # Fetch full body
        body_data = client.fetch([msg_id], ["BODY[]"])
        body = body_data[msg_id][b"BODY[]"].decode("utf-8", errors="ignore")

        print(f"\n--- Full Email Body ---")
        print(body)

if __name__ == "__main__":
    check_response_required_emails()
