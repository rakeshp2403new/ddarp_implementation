# Docker Compose Installation Guide

## 🚨 Docker Compose is Required

Your system has Docker but is missing Docker Compose, which is required to run DDARP monitoring.

## 🔧 Quick Installation Options

### Option 1: Ubuntu/Debian (Recommended)
```bash
# Update package list
sudo apt update

# Install Docker Compose plugin (recommended)
sudo apt install docker-compose-plugin

# Alternative: Install standalone docker-compose
sudo apt install docker-compose
```

### Option 2: Using the Installation Script
```bash
# Run our automated installer
sudo ./install_docker_compose.sh
```

### Option 3: Manual Download
```bash
# Download latest Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Make it executable
sudo chmod +x /usr/local/bin/docker-compose
```

## ✅ Verify Installation

After installation, verify it works:

```bash
# Check Docker Compose V2 (preferred)
docker compose version

# Or check Docker Compose V1 (legacy)
docker-compose --version
```

## 🚀 After Installation

Once Docker Compose is installed, you can run:

```bash
# Start DDARP with monitoring
./ddarp.sh start

# Or use the install command
./ddarp.sh install-compose
```

## 📋 System Requirements

- **Docker**: ✅ Installed (version 27.5.1)
- **Docker Compose**: ❌ Missing (required)
- **sudo access**: Required for installation

## 🆘 Troubleshooting

### "Permission denied" errors:
```bash
# Add your user to docker group
sudo usermod -aG docker $USER

# Logout and login again, or run:
newgrp docker
```

### "Command not found" after installation:
```bash
# Check installation location
which docker-compose
which docker

# Restart terminal or run:
source ~/.bashrc
```

### Still having issues?
1. Restart your terminal
2. Try: `sudo systemctl restart docker`
3. Check Docker daemon: `docker info`

## 🌐 Official Documentation

For more installation options, visit:
- [Docker Compose Installation](https://docs.docker.com/compose/install/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Compose)