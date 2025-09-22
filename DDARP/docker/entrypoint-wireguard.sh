#!/bin/bash

set -e

echo "Starting DDARP Node with WireGuard: $NODE_ID (Type: $NODE_TYPE)"
echo "OWL Port: $OWL_PORT, API Port: $API_PORT, WireGuard IP: $WG_IP"

# Wait a moment for the container to fully initialize
sleep 2

# Check if WireGuard configuration exists
if [ -f "/etc/wireguard/wg0.conf" ]; then
    echo "Setting up WireGuard interface..."

    # Enable IP forwarding
    echo 1 > /proc/sys/net/ipv4/ip_forward

    # Start WireGuard interface
    wg-quick up wg0

    echo "WireGuard interface wg0 is up"

    # Show WireGuard status
    wg show

    # Test WireGuard connectivity
    echo "Testing WireGuard connectivity..."
    ping -c 1 -W 2 10.0.0.1 &>/dev/null && echo "Can reach 10.0.0.1" || echo "Cannot reach 10.0.0.1"
    ping -c 1 -W 2 10.0.0.2 &>/dev/null && echo "Can reach 10.0.0.2" || echo "Cannot reach 10.0.0.2"
    ping -c 1 -W 2 10.0.0.3 &>/dev/null && echo "Can reach 10.0.0.3" || echo "Cannot reach 10.0.0.3"
else
    echo "WARNING: WireGuard configuration not found at /etc/wireguard/wg0.conf"
    echo "DDARP will run without WireGuard encryption"
fi

echo "Starting DDARP composite node..."

# Start the composite node
cd /app
exec python -m src.core.composite_node