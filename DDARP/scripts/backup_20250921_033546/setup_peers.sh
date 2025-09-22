#!/bin/bash

set -e

echo "Setting up DDARP peer relationships..."

# Wait for all nodes to be healthy
echo "Waiting for nodes to become healthy..."
for port in 8001 8002 8003; do
    echo "Checking node on port $port..."
    until curl -s "http://localhost:$port/health" | grep -q "healthy"; do
        echo "  Waiting for node on port $port to be healthy..."
        sleep 2
    done
    echo "  Node on port $port is healthy"
done

echo "All nodes are healthy. Setting up peer relationships..."

# Configure node1 peers (regular node)
echo "Configuring node1 peers..."
curl -X POST http://localhost:8001/peers \
  -H "Content-Type: application/json" \
  -d '{"peer_id": "node2", "peer_ip": "172.20.0.11", "peer_type": "regular"}'

curl -X POST http://localhost:8001/peers \
  -H "Content-Type: application/json" \
  -d '{"peer_id": "border1", "peer_ip": "172.20.0.12", "peer_type": "border"}'

# Configure node2 peers (regular node)
echo "Configuring node2 peers..."
curl -X POST http://localhost:8002/peers \
  -H "Content-Type: application/json" \
  -d '{"peer_id": "node1", "peer_ip": "172.20.0.10", "peer_type": "regular"}'

curl -X POST http://localhost:8002/peers \
  -H "Content-Type: application/json" \
  -d '{"peer_id": "border1", "peer_ip": "172.20.0.12", "peer_type": "border"}'

# Configure border1 peers (border node)
echo "Configuring border1 peers..."
curl -X POST http://localhost:8003/peers \
  -H "Content-Type: application/json" \
  -d '{"peer_id": "node1", "peer_ip": "172.20.0.10", "peer_type": "regular"}'

curl -X POST http://localhost:8003/peers \
  -H "Content-Type: application/json" \
  -d '{"peer_id": "node2", "peer_ip": "172.20.0.11", "peer_type": "regular"}'

echo "Peer relationships configured successfully!"
echo
echo "Waiting 10 seconds for OWL measurements to stabilize..."
sleep 10

echo "Checking node health and peer status..."
for port in 8001 8002 8003; do
    echo "Node on port $port:"
    curl -s "http://localhost:$port/health" | jq '.'
    echo
done

echo "Setup complete! You can now test the system with test_system.sh"