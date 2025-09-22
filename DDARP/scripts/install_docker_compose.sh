#!/bin/bash

# =============================================================================
# Docker Compose Installation Script for DDARP
# =============================================================================
# This script installs Docker Compose if it's missing from the system
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Docker Compose Installation Script ===${NC}\n"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed!${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

echo -e "${GREEN}✓ Docker found: $(docker --version)${NC}"

# Check if Docker Compose is already installed
if docker compose version &> /dev/null; then
    echo -e "${GREEN}✓ Docker Compose V2 is already installed: $(docker compose version --short)${NC}"
    exit 0
elif command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}✓ Docker Compose V1 is already installed: $(docker-compose --version)${NC}"
    exit 0
fi

echo -e "${YELLOW}Docker Compose not found. Installing...${NC}\n"

# Detect OS and install appropriately
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if command -v apt-get &> /dev/null; then
        # Ubuntu/Debian
        echo "Installing Docker Compose on Ubuntu/Debian..."

        # Update package list
        sudo apt-get update -qq

        # Try to install the plugin first (recommended)
        if sudo apt-get install -y docker-compose-plugin 2>/dev/null; then
            echo -e "${GREEN}✓ Docker Compose plugin installed successfully${NC}"
        # Fallback to standalone docker-compose
        elif sudo apt-get install -y docker-compose 2>/dev/null; then
            echo -e "${GREEN}✓ Docker Compose standalone installed successfully${NC}"
        else
            # Manual installation
            echo "Package installation failed. Installing manually..."
            COMPOSE_VERSION="v2.20.0"
            sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            sudo chmod +x /usr/local/bin/docker-compose
            echo -e "${GREEN}✓ Docker Compose installed manually${NC}"
        fi

    elif command -v yum &> /dev/null; then
        # CentOS/RHEL
        echo "Installing Docker Compose on CentOS/RHEL..."
        sudo yum install -y docker-compose-plugin

    elif command -v dnf &> /dev/null; then
        # Fedora
        echo "Installing Docker Compose on Fedora..."
        sudo dnf install -y docker-compose-plugin

    else
        # Generic Linux - manual installation
        echo "Installing Docker Compose manually..."
        COMPOSE_VERSION="v2.20.0"
        sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi

elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "On macOS, Docker Compose is included with Docker Desktop."
    echo "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    exit 1

else
    echo -e "${RED}Unsupported operating system: $OSTYPE${NC}"
    echo "Please install Docker Compose manually: https://docs.docker.com/compose/install/"
    exit 1
fi

echo ""

# Verify installation
if docker compose version &> /dev/null; then
    echo -e "${GREEN}✓ Docker Compose V2 installation verified: $(docker compose version --short)${NC}"
elif command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}✓ Docker Compose V1 installation verified: $(docker-compose --version)${NC}"
else
    echo -e "${RED}✗ Installation failed. Please install Docker Compose manually.${NC}"
    echo ""
    echo "Manual installation options:"
    echo "1. For Ubuntu/Debian:"
    echo "   sudo apt install docker-compose-plugin"
    echo ""
    echo "2. For CentOS/RHEL:"
    echo "   sudo yum install docker-compose-plugin"
    echo ""
    echo "3. Manual download:"
    echo "   sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose"
    echo "   sudo chmod +x /usr/local/bin/docker-compose"
    echo ""
    echo "4. Official documentation:"
    echo "   https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "\n${GREEN}✓ Docker Compose installation completed successfully!${NC}"
echo "You can now run: ./ddarp.sh start"