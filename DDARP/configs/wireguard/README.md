# WireGuard Configuration Directory

This directory contains WireGuard configuration templates and generated configs for DDARP nodes.

## Directory Structure
```
configs/wireguard/
├── node1/          # Node 1 WireGuard configs
├── node2/          # Node 2 WireGuard configs
├── node3/          # Node 3 WireGuard configs
└── README.md       # This file
```

## Configuration Management

WireGuard configurations are managed dynamically by the `TunnelOrchestrator` class:

1. **Key Generation**: Each node generates its own public/private key pair on startup
2. **Tunnel Creation**: Tunnels are created on-demand based on control plane decisions
3. **One-Peer-Per-Interface**: Each tunnel connects to exactly one peer
4. **IP Allocation**: Uses 10.100.0.0/16 network with /30 subnets for point-to-point links

## Usage

The tunnel orchestrator will:
- Generate keys automatically
- Create interface configs in `/etc/wireguard/` inside containers
- Mount this directory for persistent storage
- Manage tunnel lifecycle based on routing decisions

## Security

- Private keys are generated inside containers and never stored in this directory
- Key exchange happens through secure control plane communications
- Each tunnel uses unique key pairs for security isolation