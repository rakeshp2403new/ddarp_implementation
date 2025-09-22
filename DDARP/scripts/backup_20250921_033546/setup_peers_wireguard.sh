#!/bin/bash

# DDARP WireGuard Peer Setup Script
set -e

echo "Setting up DDARP peers with WireGuard IPs..."

# WireGuard IP addresses
NODE1_WG_IP="10.0.0.1"
NODE2_WG_IP="10.0.0.2"
BORDER1_WG_IP="10.0.0.3"

# API ports (unchanged)
NODE1_API="http://localhost:8001"
NODE2_API="http://localhost:8002"
BORDER1_API="http://localhost:8003"

# OWL port (unchanged)
OWL_PORT="8080"

# Wait for all nodes to be healthy
echo "Waiting for nodes to be ready..."
sleep 10

# Function to wait for node health
wait_for_node() {
    local api_url=$1
    local node_name=$2
    echo "Waiting for $node_name to be healthy..."

    for i in {1..30}; do
        if curl -s "$api_url/health" > /dev/null 2>&1; then
            echo "$node_name is healthy"
            return 0
        fi
        echo "Attempt $i/30: $node_name not ready yet..."
        sleep 2
    done

    echo "ERROR: $node_name failed to become healthy"
    return 1
}

# Wait for all nodes
wait_for_node "$NODE1_API" "Node1"
wait_for_node "$NODE2_API" "Node2"
wait_for_node "$BORDER1_API" "Border1"

echo ""
echo "All nodes are healthy. Setting up peer relationships with WireGuard IPs..."

# Configure Node1 peers (using WireGuard IPs)
echo "Configuring Node1 peers..."
curl -X POST "$NODE1_API/peers" \
  -H "Content-Type: application/json" \
  -d "{\"peer_id\": \"node2\", \"host\": \"$NODE2_WG_IP\", \"port\": $OWL_PORT}" \
  && echo "  ✓ Added node2 to node1"

curl -X POST "$NODE1_API/peers" \
  -H "Content-Type: application/json" \
  -d "{\"peer_id\": \"border1\", \"host\": \"$BORDER1_WG_IP\", \"port\": $OWL_PORT}" \
  && echo "  ✓ Added border1 to node1"

# Configure Node2 peers (using WireGuard IPs)
echo "Configuring Node2 peers..."
curl -X POST "$NODE2_API/peers" \
  -H "Content-Type: application/json" \
  -d "{\"peer_id\": \"node1\", \"host\": \"$NODE1_WG_IP\", \"port\": $OWL_PORT}" \
  && echo "  ✓ Added node1 to node2"

curl -X POST "$NODE2_API/peers" \
  -H "Content-Type: application/json" \
  -d "{\"peer_id\": \"border1\", \"host\": \"$BORDER1_WG_IP\", \"port\": $OWL_PORT}" \
  && echo "  ✓ Added border1 to node2"

# Configure Border1 peers (using WireGuard IPs)
echo "Configuring Border1 peers..."
curl -X POST "$BORDER1_API/peers" \
  -H "Content-Type: application/json" \
  -d "{\"peer_id\": \"node1\", \"host\": \"$NODE1_WG_IP\", \"port\": $OWL_PORT}" \
  && echo "  ✓ Added node1 to border1"

curl -X POST "$BORDER1_API/peers" \
  -H "Content-Type: application/json" \
  -d "{\"peer_id\": \"node2\", \"host\": \"$NODE2_WG_IP\", \"port\": $OWL_PORT}" \
  && echo "  ✓ Added node2 to border1"

echo ""
echo "Peer setup complete! All nodes are now configured to communicate over WireGuard."

# Verify peer configurations
echo ""
echo "Verifying peer configurations..."
echo "Node1 peers:"
curl -s "$NODE1_API/node_info" | python3 -c "import sys, json; data=json.load(sys.stdin); print(json.dumps(data.get('peers', []), indent=2))"

echo ""
echo "Node2 peers:"
curl -s "$NODE2_API/node_info" | python3 -c "import sys, json; data=json.load(sys.stdin); print(json.dumps(data.get('peers', []), indent=2))"

echo ""
echo "Border1 peers:"
curl -s "$BORDER1_API/node_info" | python3 -c "import sys, json; data=json.load(sys.stdin); print(json.dumps(data.get('peers', []), indent=2))"

echo ""
echo "Setup complete! DDARP nodes are now communicating through encrypted WireGuard tunnels."