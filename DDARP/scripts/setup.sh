#!/bin/bash

# =============================================================================
# DDARP Environment Setup Script
# =============================================================================
# Prepares the environment and installs prerequisites for DDARP
#
# Usage: ./setup.sh
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get &> /dev/null; then
            OS="ubuntu"
        elif command -v yum &> /dev/null; then
            OS="centos"
        else
            OS="linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    else
        OS="unknown"
    fi

    log_info "Detected OS: $OS"
}

# Install Docker
install_docker() {
    log_info "Installing Docker..."

    case "$OS" in
        ubuntu)
            # Update package index
            sudo apt-get update

            # Install prerequisites
            sudo apt-get install -y \
                ca-certificates \
                curl \
                gnupg \
                lsb-release

            # Add Docker's official GPG key
            sudo mkdir -p /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

            # Set up the repository
            echo \
                "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
                $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

            # Install Docker Engine
            sudo apt-get update
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

            # Add user to docker group
            sudo usermod -aG docker $USER
            ;;

        centos)
            # Install using yum
            sudo yum install -y yum-utils
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            sudo systemctl start docker
            sudo systemctl enable docker
            sudo usermod -aG docker $USER
            ;;

        macos)
            if command -v brew &> /dev/null; then
                brew install --cask docker
                log_info "Docker Desktop installed. Please start it manually."
            else
                log_error "Homebrew not found. Please install Docker Desktop manually from https://www.docker.com/products/docker-desktop"
                exit 1
            fi
            ;;

        *)
            log_error "Unsupported OS. Please install Docker manually."
            exit 1
            ;;
    esac

    log_success "Docker installation completed"
}

# Install WireGuard tools
install_wireguard() {
    log_info "Installing WireGuard tools..."

    case "$OS" in
        ubuntu)
            sudo apt-get update
            sudo apt-get install -y wireguard-tools
            ;;

        centos)
            sudo yum install -y epel-release
            sudo yum install -y wireguard-tools
            ;;

        macos)
            if command -v brew &> /dev/null; then
                brew install wireguard-tools
            else
                log_warning "Homebrew not found. Please install WireGuard tools manually."
            fi
            ;;

        *)
            log_warning "Cannot install WireGuard tools automatically. Please install manually."
            ;;
    esac

    if command -v wg &> /dev/null; then
        log_success "WireGuard tools installed successfully"
    else
        log_warning "WireGuard tools installation may have failed"
    fi
}

# Install additional tools
install_tools() {
    log_info "Installing additional tools..."

    case "$OS" in
        ubuntu)
            sudo apt-get install -y curl jq python3 python3-pip
            ;;

        centos)
            sudo yum install -y curl jq python3 python3-pip
            ;;

        macos)
            if command -v brew &> /dev/null; then
                brew install curl jq python3
            fi
            ;;

        *)
            log_warning "Cannot install tools automatically"
            ;;
    esac

    log_success "Additional tools installed"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=()

    # Check Docker
    if ! command -v docker &> /dev/null; then
        missing+=("docker")
    fi

    # Check Docker Compose
    if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
        missing+=("docker-compose")
    fi

    # Check curl
    if ! command -v curl &> /dev/null; then
        missing+=("curl")
    fi

    # Check python3
    if ! command -v python3 &> /dev/null; then
        missing+=("python3")
    fi

    if [[ ${#missing[@]} -eq 0 ]]; then
        log_success "All prerequisites are installed"
        return 0
    else
        log_warning "Missing prerequisites: ${missing[*]}"
        return 1
    fi
}

# Main setup process
main() {
    echo "=============================================="
    echo "         DDARP Environment Setup"
    echo "=============================================="
    echo ""

    detect_os

    # Check if already installed
    if check_prerequisites; then
        log_info "All prerequisites already installed. Nothing to do."
        echo ""
        log_info "You can now run: ./ddarp.sh setup"
        exit 0
    fi

    # Ask for confirmation
    echo ""
    log_warning "This script will install Docker, WireGuard, and other tools."
    read -p "Do you want to continue? (y/N): " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Installation cancelled."
        exit 0
    fi

    # Install prerequisites
    if ! command -v docker &> /dev/null; then
        install_docker
    fi

    install_wireguard
    install_tools

    # Final check
    if check_prerequisites; then
        echo ""
        log_success "Setup completed successfully!"
        echo ""
        log_info "Next steps:"
        echo "  1. If Docker was just installed, you may need to log out and log back in"
        echo "  2. Run: ./ddarp.sh setup"
        echo "  3. Run: ./ddarp.sh start"
        echo ""
    else
        log_error "Setup completed with some issues. Please check the output above."
        exit 1
    fi
}

# Run main function
main "$@"