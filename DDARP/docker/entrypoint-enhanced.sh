#!/bin/bash

set -e

echo "Starting Enhanced DDARP Node: $NODE_ID (Type: $NODE_TYPE)"
echo "OWL Port: $OWL_PORT, API Port: $API_PORT, BGP ASN: $BIRD_ASN"
echo "WireGuard IP: $WG_IP, BIRD Router ID: $BIRD_ROUTER_ID"

# Wait a moment for the container to fully initialize
sleep 2

# Enable IP forwarding
echo "Enabling IP forwarding..."
echo 1 > /proc/sys/net/ipv4/ip_forward
echo 1 > /proc/sys/net/ipv6/conf/all/forwarding

# Check if WireGuard configuration exists
if [ -f "/etc/wireguard/wg0.conf" ]; then
    echo "Setting up WireGuard interface..."
    wg-quick up wg0
    echo "WireGuard interface wg0 is up"
    wg show
else
    echo "WARNING: WireGuard configuration not found at /etc/wireguard/wg0.conf"
    echo "DDARP will run without WireGuard tunnels"
fi

# Initialize BIRD configuration directory
echo "Preparing BIRD routing daemon..."
mkdir -p /var/run/bird
mkdir -p /var/log/bird

# Create minimal BIRD configuration if none exists
if [ ! -f "/etc/bird/bird.conf" ]; then
    echo "Creating default BIRD configuration..."
    cat > /etc/bird/bird.conf << EOF
# Default BIRD configuration for DDARP node $NODE_ID
router id $BIRD_ROUTER_ID;

log syslog all;
debug protocols { events, states };

# Device protocol for interface monitoring
protocol device {
    scan time 10;
}

# Kernel protocol for route synchronization
protocol kernel {
    ipv4 {
        import none;
        export where source = RTS_BGP;
    };
}

# Direct protocol for connected routes
protocol direct {
    ipv4;
    interface "eth0", "wg*";
}

# Static routes protocol
protocol static static_routes {
    ipv4;
}
EOF
fi

# Start BIRD daemon in background
echo "Starting BIRD routing daemon..."
bird -c /etc/bird/bird.conf -s /var/run/bird/bird.ctl -P /var/run/bird/bird.pid &

# Wait for BIRD to start
sleep 3

# Test BIRD status
if birdc -s /var/run/bird/bird.ctl show status > /dev/null 2>&1; then
    echo "BIRD daemon started successfully"
else
    echo "WARNING: BIRD daemon failed to start - BGP functionality will be limited"
fi

# Test network connectivity
echo "Testing network connectivity..."
ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1 && echo "External connectivity: OK" || echo "External connectivity: FAILED"

echo "Starting DDARP composite node..."

# Start the composite node
cd /app
exec python -m src.core.composite_node