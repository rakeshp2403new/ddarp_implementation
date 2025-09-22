#!/bin/bash

# =============================================================================
# DDARP Stop Script
# =============================================================================
# Safely stops all DDARP services and cleans up resources
#
# Usage: ./scripts/ddarp_stop.sh
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

print_header() {
    echo -e "${CYAN}"
    echo "=========================================="
    echo "$1"
    echo "=========================================="
    echo -e "${NC}"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Determine docker-compose command
DOCKER_COMPOSE_CMD="docker-compose"
if [ -x "/tmp/docker-compose" ]; then
    DOCKER_COMPOSE_CMD="/tmp/docker-compose"
fi

stop_ddarp_system() {
    print_header "Stopping DDARP System"

    cd "$PROJECT_DIR"

    print_step "Stopping Docker containers..."
    $DOCKER_COMPOSE_CMD down -v 2>/dev/null || {
        print_warning "Failed to stop with docker-compose, trying direct container stop..."

        # Try to stop containers directly
        docker stop ddarp_node1 ddarp_node2 ddarp_border1 ddarp_prometheus 2>/dev/null || true
        docker rm ddarp_node1 ddarp_node2 ddarp_border1 ddarp_prometheus 2>/dev/null || true
    }

    print_step "Cleaning up Docker resources..."
    docker network rm ddarp_ddarp_network 2>/dev/null || true
    docker volume rm ddarp_prometheus_data 2>/dev/null || true

    print_step "Cleaning up temporary files..."
    rm -f /tmp/docker-compose 2>/dev/null || true

    print_success "DDARP system stopped and cleaned up"
}

main() {
    print_header "DDARP System Shutdown"

    stop_ddarp_system

    echo ""
    echo -e "${GREEN}✅ DDARP system has been completely stopped${NC}"
    echo -e "${BLUE}💡 To start again, run: ./scripts/ddarp_one_click_start.sh${NC}"
}

# Execute main function
main "$@"