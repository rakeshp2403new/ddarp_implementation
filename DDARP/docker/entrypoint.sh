#!/bin/bash

set -e

echo "Starting DDARP Node: $NODE_ID (Type: $NODE_TYPE)"
echo "OWL Port: $OWL_PORT, API Port: $API_PORT"

# Start the composite node
cd /app
exec python -m src.core.composite_node