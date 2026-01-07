# Kiro Auto Register - Docker Deployment

This Docker image packages the Kiro auto-registration script with all dependencies (Playwright, kiro-cli) for headless operation.

## Prerequisites

- Docker and Docker Compose installed
- A valid `config.json` file (copy from `config.example.json`)

## Quick Start

### 1. Prepare Configuration

```bash
cp config.example.json config.json
# Edit config.json with your settings:
# - IMAP credentials
# - Email domain
# - Backend URL
# - Admin password
```

### 2. Build the Image

```bash
docker-compose build
```

Or build manually:

```bash
docker build -t kiro-register:latest .
```

### 3. Run Registration

Using docker-compose:

```bash
docker-compose up
```

Or run manually:

```bash
docker run --rm \
  -v $(pwd)/config.json:/app/config.json:ro \
  -v $(pwd)/last_identity.json:/app/last_identity.json \
  kiro-register:latest
```

## Configuration

### Environment Variables

- `PLAYWRIGHT_BROWSERS_PATH`: Browser installation path (default: `/ms-playwright`)
- `DISPLAY`: X11 display (set to `:99` for headless)

### Volumes

- `/app/config.json`: Configuration file (required, read-only)
- `/root/.local/share/kiro-cli`: kiro-cli data directory (persisted)
- `/app/last_identity.json`: Last generated identity (optional, for debugging)

## Headless Mode

The script runs in headless mode by default when using Docker. The Dockerfile includes all necessary dependencies for headless Chromium operation:

- X11 libraries
- Font packages
- GPU acceleration libraries
- Audio libraries (for completeness)

## Troubleshooting

### Browser Launch Fails

If you see errors like "Browser closed unexpectedly":

1. Check Docker has enough memory (recommend 2GB+)
2. Verify `/dev/shm` size: `docker run --rm --shm-size=2g ...`
3. Add `--no-sandbox` flag (already included in Dockerfile)

### kiro-cli Not Found

The Dockerfile downloads the latest kiro-cli from GitHub releases. If download fails:

1. Check network connectivity
2. Manually download and place in image:
   ```dockerfile
   COPY kiro-cli /usr/local/bin/kiro-cli
   RUN chmod +x /usr/local/bin/kiro-cli
   ```

### IMAP Connection Issues

If IMAP connection fails:

1. Verify credentials in `config.json`
2. Check firewall rules (Docker network)
3. Test IMAP connection from host first

## Advanced Usage

### Run with Custom Command

```bash
docker run --rm \
  -v $(pwd)/config.json:/app/config.json:ro \
  kiro-register:latest \
  python register.py --headless
```

### Interactive Shell (Debugging)

```bash
docker run --rm -it \
  -v $(pwd)/config.json:/app/config.json:ro \
  kiro-register:latest \
  /bin/bash
```

### Increase Shared Memory

For better browser stability:

```bash
docker run --rm --shm-size=2g \
  -v $(pwd)/config.json:/app/config.json:ro \
  kiro-register:latest
```

Or in docker-compose.yml:

```yaml
services:
  kiro-register:
    shm_size: '2gb'
```

## Image Size

The final image is approximately 1.5-2GB due to:
- Python base image: ~150MB
- Chromium browser: ~300MB
- System dependencies: ~200MB
- Python packages: ~100MB

## Security Notes

- `config.json` is mounted read-only
- Container runs as root (required for Playwright)
- No exposed ports (outbound connections only)
- Credentials stored in mounted volume only

## License

Same as parent project.
