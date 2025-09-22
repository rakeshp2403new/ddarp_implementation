#!/bin/bash

echo "Stopping DDARP System"
echo "====================="

# Stop and remove all containers
docker-compose down -v

echo "DDARP System stopped successfully!"
echo
echo "To start again: ./scripts/start_system.sh"