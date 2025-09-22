#!/bin/bash

set -e

echo "Starting DDARP System"
echo "===================="

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose >/dev/null 2>&1; then
    echo "Error: docker-compose is not installed or not in PATH."
    exit 1
fi

# Clean up any existing containers
echo "Cleaning up existing containers..."
docker-compose down -v 2>/dev/null || true

# Build and start the system
echo "Building Docker images..."
docker-compose build

echo "Starting DDARP nodes and Prometheus..."
docker-compose up -d

echo "Waiting for services to start..."
sleep 10

# Check container status
echo "Container status:"
docker-compose ps

echo
echo "DDARP System started successfully!"
echo
echo "Services available:"
echo "- node1 API: http://localhost:8001"
echo "- node2 API: http://localhost:8002"
echo "- border1 API: http://localhost:8003"
echo "- Prometheus: http://localhost:9090"
echo
echo "Next steps:"
echo "1. Run './scripts/setup_peers.sh' to configure peer relationships"
echo "2. Run './scripts/test_system.sh' to test the system functionality"
echo
echo "To stop the system: docker-compose down"