# Quick Start Guide - Docker Deployment

## Prerequisites

- Docker (20.10+)
- Docker Compose (1.29+)
- 2GB+ available RAM

## Setup (3 Steps)

### 1. Configure

```bash
cd script/
cp config.example.json config.json
nano config.json  # Edit with your settings
```

Required settings in `config.json`:
- `imap`: Your email server credentials
- `email_domain`: Domain for generated emails
- `backend_url`: Your kiro-proxy backend URL
- `admin_password`: Backend admin password

### 2. Build

```bash
make build
# Or: docker-compose build
```

This will:
- Download Python 3.11 base image
- Install system dependencies
- Download kiro-cli binary
- Install Playwright + Chromium
- Build the final image (~1.5GB)

### 3. Run

```bash
make run
# Or: docker-compose up
```

The script will:
1. Generate random identity
2. Register AWS Builder ID
3. Complete device authorization
4. Extract tokens from kiro-cli
5. Add account to backend

## Verification

Test the environment before running:

```bash
make test
# Or: docker run --rm kiro-register:latest python test_docker.py
```

Expected output:
```
Testing kiro-cli...
✓ kiro-cli found: kiro-cli version x.x.x

Testing Playwright + Chromium...
✓ Playwright working, page title: Google

All tests passed! Environment is ready.
```

## Troubleshooting

### Build fails at kiro-cli download

**Problem**: `wget: unable to resolve host address`

**Solution**: Check network connectivity or manually download:
```bash
wget https://github.com/Hzzy2O/kiro-cli/releases/latest/download/kiro-cli-linux-x64
# Then modify Dockerfile to COPY instead of wget
```

### Browser crashes in container

**Problem**: `Browser closed unexpectedly`

**Solutions**:
1. Increase shared memory (already set to 2GB in docker-compose.yml)
2. Increase memory limit:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 4G
   ```
3. Check Docker daemon has enough resources

### IMAP connection timeout

**Problem**: `TimeoutError: No verification code received`

**Solutions**:
1. Verify IMAP credentials in config.json
2. Test IMAP from host first:
   ```bash
   telnet mail.example.com 143
   ```
3. Check firewall rules for Docker network

### Config file not found

**Problem**: `Error: config.json not found`

**Solution**: Ensure config.json exists in the same directory as docker-compose.yml

## Advanced Usage

### Run with custom config path

```bash
docker run --rm \
  -v /path/to/config.json:/app/config.json:ro \
  kiro-register:latest
```

### Debug mode (interactive shell)

```bash
make shell
# Or: docker run --rm -it kiro-register:latest /bin/bash
```

Inside container:
```bash
python test_docker.py  # Test environment
python register.py --headless  # Run registration
kiro-cli --version  # Check kiro-cli
```

### View logs

```bash
make logs
# Or: docker-compose logs -f
```

### Clean up

```bash
make clean
# Or: docker-compose down -v && docker rmi kiro-register:latest
```

## Production Deployment

For automated registration (e.g., cron job):

```bash
# Run every 6 hours
0 */6 * * * cd /path/to/script && docker-compose up >> /var/log/kiro-register.log 2>&1
```

Or use a loop script:

```bash
#!/bin/bash
while true; do
    cd /path/to/script
    docker-compose up
    sleep 21600  # 6 hours
done
```

## Security Notes

- config.json contains sensitive credentials (IMAP password, admin password)
- Mount config.json as read-only (`:ro`)
- Don't commit config.json to git
- Use environment variables for secrets in production:
  ```yaml
  environment:
    - IMAP_PASSWORD=${IMAP_PASSWORD}
    - ADMIN_PASSWORD=${ADMIN_PASSWORD}
  ```

## Performance

- First run: ~5-10 minutes (image build + registration)
- Subsequent runs: ~2-3 minutes (registration only)
- Image size: ~1.5GB
- Memory usage: ~1-1.5GB during execution

## Support

If you encounter issues:
1. Check logs: `docker-compose logs`
2. Test environment: `make test`
3. Run in debug mode: `make shell`
4. Check error screenshots: `error_*.png` files
