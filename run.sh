#!/bin/bash
set -e

# Kiro Auto Register - Docker Runner Script

echo "==================================="
echo "Kiro Auto Register - Docker Runner"
echo "==================================="

# Check if config.json exists
if [ ! -f "config.json" ]; then
    echo "Error: config.json not found!"
    echo "Please copy config.example.json to config.json and fill in your settings."
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running!"
    exit 1
fi

# Build image if not exists or --build flag is passed
if [ "$1" == "--build" ] || ! docker images | grep -q "kiro-register"; then
    echo "Building Docker image..."
    docker-compose build
fi

# Run registration
echo "Starting registration process..."
docker-compose up

# Show last identity if exists
if [ -f "last_identity.json" ]; then
    echo ""
    echo "==================================="
    echo "Last Generated Identity:"
    echo "==================================="
    cat last_identity.json | python -m json.tool
fi

echo ""
echo "Done!"
