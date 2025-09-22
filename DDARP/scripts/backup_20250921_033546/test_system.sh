#!/bin/bash

set -e

echo "Testing DDARP System Functionality"
echo "=================================="

# Function to make API calls and display results
test_endpoint() {
    local node_port=$1
    local endpoint=$2
    local node_name=$3
    
    echo
    echo "[$node_name] Testing $endpoint"
    echo "----------------------------------------"
    
    response=$(curl -s "http://localhost:$node_port$endpoint")
    if [ $? -eq 0 ]; then
        echo "$response" | jq '.' 2>/dev/null || echo "$response"
    else
        echo "Error: Failed to connect to $node_name"
    fi
}

# Test health endpoints
echo "1. Testing Node Health"
test_endpoint 8001 "/health" "node1"
test_endpoint 8002 "/health" "node2"
test_endpoint 8003 "/health" "border1"

# Test node info
echo
echo "2. Testing Node Information"
test_endpoint 8001 "/node_info" "node1"
test_endpoint 8002 "/node_info" "node2"
test_endpoint 8003 "/node_info" "border1"

# Wait for some OWL measurements
echo
echo "3. Waiting for OWL measurements (15 seconds)..."
sleep 15

# Test OWL metrics
echo
echo "4. Testing OWL Metrics"
test_endpoint 8001 "/metrics/owl" "node1"
test_endpoint 8002 "/metrics/owl" "node2"
test_endpoint 8003 "/metrics/owl" "border1"

# Test topology
echo
echo "5. Testing Topology Information"
test_endpoint 8001 "/topology" "node1"
test_endpoint 8002 "/topology" "node2"
test_endpoint 8003 "/topology" "border1"

# Test routing tables
echo
echo "6. Testing Routing Tables"
test_endpoint 8001 "/routing_table" "node1"
test_endpoint 8002 "/routing_table" "node2"
test_endpoint 8003 "/routing_table" "border1"

# Test path queries
echo
echo "7. Testing Path Queries"
echo
echo "[node1] Path to node2:"
test_endpoint 8001 "/path/node2" "node1"

echo
echo "[node1] Path to border1:"
test_endpoint 8001 "/path/border1" "node1"

echo
echo "[node2] Path to node1:"
test_endpoint 8002 "/path/node1" "node2"

echo
echo "[node2] Path to border1:"
test_endpoint 8002 "/path/border1" "node2"

echo
echo "[border1] Path to node1:"
test_endpoint 8003 "/path/node1" "border1"

echo
echo "[border1] Path to node2:"
test_endpoint 8003 "/path/node2" "border1"

echo
echo "=================================="
echo "System test completed!"
echo
echo "You can also check:"
echo "- Prometheus metrics: http://localhost:9090"
echo "- Individual node APIs:"
echo "  - node1: http://localhost:8001"
echo "  - node2: http://localhost:8002"
echo "  - border1: http://localhost:8003"