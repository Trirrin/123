#!/bin/bash
# Health check script for Docker container

set -e

echo "Running health checks..."

# Check if kiro-cli is accessible
if ! command -v kiro-cli &> /dev/null; then
    echo "ERROR: kiro-cli not found"
    exit 1
fi

# Check if Python is working
if ! python --version &> /dev/null; then
    echo "ERROR: Python not working"
    exit 1
fi

# Check if required Python packages are installed
python -c "import playwright; import faker; import imapclient; import requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: Required Python packages not installed"
    exit 1
fi

# Check if Chromium browser is installed
if ! python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.chromium.executable_path; p.stop()" &> /dev/null; then
    echo "ERROR: Chromium browser not installed"
    exit 1
fi

echo "All health checks passed!"
exit 0
