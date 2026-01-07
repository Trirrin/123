FROM python:3.11-slim

# Install system dependencies for Playwright and kiro-cli
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    gnupg \
    ca-certificates \
    fonts-liberation \
    fonts-noto-cjk \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy kiro-cli binary from host (faster and more reliable than downloading)
COPY --chmod=755 kiro-cli /root/.local/bin/kiro-cli

# Add kiro-cli to PATH
ENV PATH="/root/.local/bin:${PATH}"

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only)
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application files
COPY register.py .
COPY config.example.json .
COPY test_docker.py .
COPY healthcheck.sh .

# Make healthcheck script executable
RUN chmod +x healthcheck.sh

# Create directory for kiro-cli data
RUN mkdir -p /root/.local/share/kiro-cli

# Set environment variables for headless operation
ENV DISPLAY=:99

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /app/healthcheck.sh

# Default command
CMD ["python", "register.py", "--headless"]
