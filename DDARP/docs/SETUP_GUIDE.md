# DDARP Setup Guide

Complete guide to set up, configure, and run the DDARP (Dynamic Distributed Routing Protocol) system from scratch.

## 🚀 Quick Start (3 Commands)

For experienced users who want to get started immediately:

```bash
./setup.sh          # Install prerequisites (first time only)
./ddarp.sh setup     # Configure DDARP system
./ddarp.sh start     # Start the system
```

## 📋 Prerequisites

### System Requirements
- **Operating System**: Linux (Ubuntu 20.04+), macOS, or WSL2
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Storage**: 2GB free space
- **Network**: Internet connection for downloading Docker images
- **Privileges**: sudo access for Docker installation

### Required Software
- **Docker**: Container runtime
- **Docker Compose**: Multi-container orchestration
- **WireGuard Tools**: For VPN tunnel management (optional but recommended)
- **curl**: For API testing
- **jq**: For JSON processing (optional)
- **Python 3**: For running components outside containers

## 🔧 Installation Steps

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd DDARP
```

### Step 2: Run Environment Setup

The setup script will automatically install all prerequisites:

```bash
./setup.sh
```

This script will:
- Detect your operating system
- Install Docker and Docker Compose
- Install WireGuard tools
- Install additional utilities (curl, jq, python3)
- Add your user to the docker group

**Note**: If Docker was just installed, you may need to log out and log back in for group changes to take effect.

### Step 3: Configure DDARP System

Run the DDARP setup to prepare configurations:

```bash
./ddarp.sh setup
```

This will:
- Create configuration directories
- Generate WireGuard keys and configurations
- Generate BIRD BGP configurations
- Build Docker images
- Set up volume mounts

### Step 4: Start the System

```bash
./ddarp.sh start
```

This will:
- Start all DDARP containers (node1, node2, border1, prometheus)
- Wait for services to be healthy
- Configure peer relationships automatically
- Display system status

## 🎮 Usage Commands

### Master Control Script (`ddarp.sh`)

```bash
./ddarp.sh <command>
```

| Command | Description |
|---------|-------------|
| `setup` | Initial system configuration (run once) |
| `start` | Start the DDARP system |
| `test` | Run comprehensive functionality tests |
| `stop` | Stop the DDARP system |
| `restart` | Restart the system (stop + start) |
| `status` | Show current system status |
| `logs` | Show system logs (add service name for specific logs) |
| `clean` | Complete cleanup (removes configs and images) |

### Examples

```bash
# Start the system
./ddarp.sh start

# Check system status
./ddarp.sh status

# View logs for a specific node
./ddarp.sh logs node1

# Run comprehensive tests
./ddarp.sh test

# Stop everything
./ddarp.sh stop
```

## 🔍 System Verification

### 1. Check Container Status

```bash
./ddarp.sh status
```

Expected output shows all containers as "Up" and all nodes as "HEALTHY".

### 2. Test API Endpoints

```bash
# Test basic health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health

# Test OWL metrics (wait ~30 seconds after start)
curl http://localhost:8001/metrics/owl

# Test data plane (enhanced deployment)
curl http://localhost:8001/data_plane/status
curl http://localhost:8001/bgp/peers
curl http://localhost:8001/tunnels
```

### 3. Monitor with Prometheus

Open http://localhost:9090 in your browser to access Prometheus monitoring.

### 4. Run Automated Tests

```bash
./ddarp.sh test
```

This runs comprehensive tests covering:
- Node health checks
- OWL measurement functionality
- Routing table population
- BGP peering status
- WireGuard tunnel status
- Data plane forwarding tests

## 🌐 System Access Points

### API Endpoints
- **node1**: http://localhost:8001
- **node2**: http://localhost:8002
- **border1**: http://localhost:8003
- **Prometheus**: http://localhost:9090

### Enhanced Deployment Ports
- **BGP**: 1791 (node1), 1792 (node2), 1793 (border1)
- **WireGuard**: 51821 (node1), 51822 (node2), 51823 (border1)

## 📊 API Reference

### Core DDARP Endpoints
- `GET /health` - Node health status
- `GET /metrics/owl` - OWL measurement matrix
- `GET /topology` - Network topology information
- `GET /path/{destination}` - Path to destination node
- `GET /routing_table` - Current routing table
- `GET /node_info` - Node configuration details

### Data Plane Endpoints
- `GET /bgp/peers` - BGP peering status
- `GET /bgp/routes` - BGP routing table
- `GET /tunnels` - List active WireGuard tunnels
- `POST /tunnels/{peer_id}` - Create tunnel to specific peer
- `DELETE /tunnels/{peer_id}` - Delete tunnel to specific peer
- `GET /forwarding/{destination}` - Test data plane forwarding
- `GET /data_plane/status` - Comprehensive data plane status

## 🏗️ Architecture Overview

### Deployment Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Network (172.20.0.0/16)              │
├─────────────────┬─────────────────┬─────────────────┬─────────────┤
│   node1         │   node2         │   border1       │ prometheus  │
│ 172.20.0.10     │ 172.20.0.11     │ 172.20.0.12     │172.20.0.20  │
│ API: 8001       │ API: 8002       │ API: 8003       │ Web: 9090   │
│ BGP: 1791       │ BGP: 1792       │ BGP: 1793       │             │
│ WG: 51821       │ WG: 51822       │ WG: 51823       │             │
└─────────────────┴─────────────────┴─────────────────┴─────────────┘
```

### Component Flow
```
OWL Engine → Control Plane → Data Plane Manager
     ↓             ↓              ↓
 UDP Pings    Dijkstra     BIRD eBGP Router
     ↓        Algorithm         ↓
Performance     ↓         BGP Communities
 Metrics    Route Calc.        ↓
     ↓             ↓      WireGuard Tunnels
     ↓             ↓            ↓
     └─── Integrated Decision Making ───┘
```

## 🛠️ Configuration

### Basic Configuration
The system works out-of-the-box with minimal configuration. Default settings:

- **OWL Frequency**: 1Hz ping measurements
- **Control Plane Updates**: Every 5 seconds
- **Hysteresis Threshold**: 20% improvement required
- **Route Expiry**: 120 seconds
- **Tunnel Thresholds**: <10ms latency, <1% packet loss

### Advanced Configuration

#### Environment Variables
Set in `docker-compose.enhanced.yml`:

```yaml
environment:
  - NODE_ID=node1
  - NODE_TYPE=regular
  - BIRD_ASN=65001
  - BIRD_ROUTER_ID=10.255.1.1
  - WG_IP=10.0.0.1
```

#### Network Configuration
- **Control Network**: 172.20.0.0/16 (Docker containers)
- **WireGuard Network**: 10.0.0.0/24 (Inter-node VPN)
- **Data Plane Network**: 10.100.0.0/16 (Tunnel allocation)

## 🔧 Troubleshooting

### Common Issues

#### 1. Permission Denied Errors
```bash
# Fix script permissions
chmod +x *.sh
chmod +x ddarp.sh
```

#### 2. Docker Permission Issues
```bash
# Add user to docker group and reboot
sudo usermod -aG docker $USER
# Then logout/login or reboot
```

#### 3. Port Already in Use
```bash
# Check what's using the ports
sudo netstat -tulpn | grep :800

# Stop conflicting services or change ports in docker-compose.yml
```

#### 4. Containers Won't Start
```bash
# Check Docker daemon
sudo systemctl status docker

# View detailed logs
./ddarp.sh logs

# Check system resources
docker system df
```

#### 5. WireGuard Issues
```bash
# Check if WireGuard kernel module is loaded
lsmod | grep wireguard

# On some systems, you may need to install linux-headers
sudo apt-get install linux-headers-$(uname -r)
```

### Debug Commands

```bash
# View all container logs
./ddarp.sh logs

# View specific container logs
./ddarp.sh logs node1

# Check container resources
docker stats

# Inspect network
docker network ls
docker network inspect ddarp_ddarp_network

# Check volumes
docker volume ls
```

### Performance Tuning

#### For Production Use
1. **Increase container resources** in docker-compose.yml
2. **Adjust measurement frequency** in OWL engine configuration
3. **Tune hysteresis thresholds** based on network characteristics
4. **Configure external BGP peering** for larger deployments

#### For Development
1. **Reduce container resource limits** for local testing
2. **Increase logging verbosity** for debugging
3. **Use shorter timeouts** for faster iteration

## 📁 File Structure

```
DDARP/
├── ddarp.sh                     # Master control script
├── setup.sh                     # Environment setup script
├── SETUP_GUIDE.md              # This guide
├── README.md                    # Project documentation
├── docker-compose.enhanced.yml  # Full deployment configuration
├── src/                         # Source code
│   ├── core/                   # Core DDARP components
│   └── networking/             # Data plane components
├── configs/                     # Configuration templates
│   ├── bird/                   # BIRD BGP configurations
│   ├── wireguard/              # WireGuard configurations
│   └── prometheus.yml          # Monitoring configuration
├── docker/                      # Docker build files
├── scripts/                     # Additional scripts
└── requirements.txt            # Python dependencies
```

## 🤝 Support

### Getting Help
1. **Check logs**: `./ddarp.sh logs`
2. **Run diagnostics**: `./ddarp.sh status`
3. **Review this guide**: Most issues are covered in troubleshooting
4. **Check prerequisites**: Ensure all required software is installed

### Reporting Issues
When reporting issues, please include:
1. Output of `./ddarp.sh status`
2. Output of `./ddarp.sh logs`
3. Your operating system and version
4. Docker version (`docker --version`)
5. Steps to reproduce the issue

## 🎯 Next Steps

Once your DDARP system is running:

1. **Explore the API**: Use curl or a REST client to interact with endpoints
2. **Monitor Performance**: Check Prometheus dashboards at http://localhost:9090
3. **Test Data Plane**: Create custom tunnels and test forwarding
4. **Scale the System**: Add more nodes by modifying docker-compose.yml
5. **Integrate with External Networks**: Configure BGP peering with real routers

## 📚 Additional Resources

- **Project Repository**: [Link to repository]
- **API Documentation**: See README.md for complete API reference
- **Performance Metrics**: Available in Prometheus at http://localhost:9090
- **BGP Configuration**: BIRD configurations in `configs/bird/`
- **WireGuard Setup**: Configurations in `configs/wireguard/`