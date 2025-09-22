FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    bird2 \
    wireguard-tools \
    iproute2 \
    iptables \
    curl \
    netcat-openbsd \
    iputils-ping \
    procps \
    net-tools \
    gcc \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Create necessary directories
RUN mkdir -p /var/log/ddarp /etc/ddarp /etc/wireguard /var/run/bird

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create a simple requirements.txt if it doesn't exist
RUN if [ ! -f requirements.txt ]; then \
    echo "fastapi==0.104.1" > requirements.txt && \
    echo "uvicorn[standard]==0.24.0" >> requirements.txt && \
    echo "prometheus-client==0.19.0" >> requirements.txt && \
    echo "websockets==12.0" >> requirements.txt && \
    echo "aiohttp==3.9.1" >> requirements.txt && \
    echo "asyncio-mqtt==0.13.0" >> requirements.txt && \
    pip install --no-cache-dir -r requirements.txt; \
fi

# Set environment variables
ENV PYTHONPATH=/app
ENV NODE_ID=node1
ENV PEERS=node2,node3
ENV LOG_LEVEL=INFO
ENV PROMETHEUS_PORT=9090
ENV WEBSOCKET_PORT=8765

# Expose ports
EXPOSE 8080 9090 8765 51820/udp 179

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Create startup script
RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'set -e' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo 'echo "Starting DDARP Node: $NODE_ID"' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Create log directory' >> /app/start.sh && \
    echo 'mkdir -p /var/log/ddarp' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Configure BIRD if config exists' >> /app/start.sh && \
    echo 'if [ -f /etc/bird/bird.conf ]; then' >> /app/start.sh && \
    echo '    echo "Starting BIRD BGP daemon..."' >> /app/start.sh && \
    echo '    bird -c /etc/bird/bird.conf -s /var/run/bird/bird.ctl &' >> /app/start.sh && \
    echo 'fi' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Configure WireGuard if config exists' >> /app/start.sh && \
    echo 'if [ -f /etc/wireguard/wg0.conf ]; then' >> /app/start.sh && \
    echo '    echo "Setting up WireGuard interface..."' >> /app/start.sh && \
    echo '    ip link add wg0 type wireguard 2>/dev/null || true' >> /app/start.sh && \
    echo '    wg setconf wg0 /etc/wireguard/wg0.conf 2>/dev/null || true' >> /app/start.sh && \
    echo '    ip link set wg0 up 2>/dev/null || true' >> /app/start.sh && \
    echo 'fi' >> /app/start.sh && \
    echo '' >> /app/start.sh && \
    echo '# Start the DDARP application' >> /app/start.sh && \
    echo 'echo "Starting DDARP application..."' >> /app/start.sh && \
    echo 'exec python -m src.main' >> /app/start.sh && \
    chmod +x /app/start.sh

# Run the startup script
CMD ["/app/start.sh"]