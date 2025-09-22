"""
WireGuard Tunnel Orchestrator

Manages WireGuard VPN tunnels for DDARP data plane, including:
- Dynamic tunnel creation and teardown
- Key generation and management
- Interface configuration and routing
- One-peer-per-interface tunnel architecture
- Integration with control plane path decisions
"""

import asyncio
import logging
import subprocess
import json
import os
import secrets
import ipaddress
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WireGuardKey:
    """WireGuard cryptographic keys"""
    private_key: str
    public_key: str


@dataclass
class TunnelEndpoint:
    """WireGuard tunnel endpoint configuration"""
    peer_id: str
    interface_name: str
    local_ip: str
    remote_ip: str
    peer_public_key: str
    peer_endpoint: str
    listen_port: int
    status: str = "down"  # down, up, error
    last_handshake: Optional[str] = None
    bytes_sent: int = 0
    bytes_received: int = 0


class TunnelOrchestrator:
    """Manages WireGuard tunnels for DDARP data plane"""

    def __init__(self, node_id: str, base_port: int = 51820,
                 tunnel_network: str = "10.100.0.0/16",
                 config_dir: str = "/etc/wireguard"):
        self.node_id = node_id
        self.base_port = base_port
        self.tunnel_network = ipaddress.IPv4Network(tunnel_network)
        self.config_dir = Path(config_dir)
        self.tunnels: Dict[str, TunnelEndpoint] = {}
        self.node_keys = self._generate_node_keys()
        self.logger = logging.getLogger(f"tunnel_orchestrator_{node_id}")
        self.running = False
        self.next_port = base_port
        self.tunnel_counter = 0

        # IP allocation tracking
        self.allocated_ips: Dict[str, str] = {}
        self.ip_counter = 1

    def _generate_node_keys(self) -> WireGuardKey:
        """Generate WireGuard keys for this node"""
        try:
            # Generate private key
            private_key = self._execute_wg_command(["genkey"]).strip()

            # Generate public key from private key
            process = subprocess.run(
                ["wg", "pubkey"],
                input=private_key,
                text=True,
                capture_output=True,
                check=True
            )
            public_key = process.stdout.strip()

            return WireGuardKey(private_key=private_key, public_key=public_key)

        except Exception as e:
            self.logger.error(f"Failed to generate WireGuard keys: {e}")
            raise

    async def start(self):
        """Initialize tunnel orchestrator"""
        self.logger.info(f"Starting tunnel orchestrator for {self.node_id}")

        # Create config directory
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Enable IP forwarding
        await self._enable_ip_forwarding()

        self.running = True
        self.logger.info(f"Tunnel orchestrator started with public key: {self.node_keys.public_key}")

    async def stop(self):
        """Stop tunnel orchestrator and cleanup tunnels"""
        self.logger.info("Stopping tunnel orchestrator")
        self.running = False

        # Bring down all tunnels
        for peer_id in list(self.tunnels.keys()):
            await self.remove_tunnel(peer_id)

    async def create_tunnel(self, peer_id: str, peer_public_key: str,
                          peer_endpoint: str, peer_ip: str) -> Optional[TunnelEndpoint]:
        """Create a new WireGuard tunnel to a peer"""
        try:
            if peer_id in self.tunnels:
                self.logger.warning(f"Tunnel to {peer_id} already exists")
                return self.tunnels[peer_id]

            # Generate interface name
            interface_name = f"wg-{peer_id}"

            # Allocate IP addresses for tunnel
            local_ip = self._allocate_tunnel_ip(peer_id, local=True)
            remote_ip = self._allocate_tunnel_ip(peer_id, local=False)

            # Get next available port
            listen_port = self._get_next_port()

            # Create tunnel endpoint
            tunnel = TunnelEndpoint(
                peer_id=peer_id,
                interface_name=interface_name,
                local_ip=local_ip,
                remote_ip=remote_ip,
                peer_public_key=peer_public_key,
                peer_endpoint=peer_endpoint,
                listen_port=listen_port
            )

            # Generate WireGuard configuration
            config_content = self._generate_tunnel_config(tunnel)

            # Write configuration file
            config_file = self.config_dir / f"{interface_name}.conf"
            with open(config_file, 'w') as f:
                f.write(config_content)

            # Bring up the tunnel
            await self._bring_up_tunnel(tunnel)

            self.tunnels[peer_id] = tunnel
            self.logger.info(f"Created tunnel to {peer_id} on {interface_name} ({local_ip} -> {remote_ip})")

            return tunnel

        except Exception as e:
            self.logger.error(f"Failed to create tunnel to {peer_id}: {e}")
            return None

    async def remove_tunnel(self, peer_id: str) -> bool:
        """Remove a WireGuard tunnel"""
        try:
            if peer_id not in self.tunnels:
                self.logger.warning(f"Tunnel to {peer_id} does not exist")
                return False

            tunnel = self.tunnels[peer_id]

            # Bring down the tunnel
            await self._bring_down_tunnel(tunnel)

            # Remove configuration file
            config_file = self.config_dir / f"{tunnel.interface_name}.conf"
            if config_file.exists():
                config_file.unlink()

            # Deallocate IP addresses
            self._deallocate_tunnel_ip(peer_id)

            del self.tunnels[peer_id]
            self.logger.info(f"Removed tunnel to {peer_id}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to remove tunnel to {peer_id}: {e}")
            return False

    async def get_tunnel_status(self, peer_id: str) -> Optional[TunnelEndpoint]:
        """Get status of a specific tunnel"""
        if peer_id not in self.tunnels:
            return None

        tunnel = self.tunnels[peer_id]

        try:
            # Query WireGuard for interface status
            result = await self._execute_wg_command_async(["show", tunnel.interface_name])

            # Parse output to update tunnel status
            if "latest handshake" in result:
                tunnel.status = "up"
                # Extract handshake time and transfer stats
                lines = result.split('\n')
                for line in lines:
                    line = line.strip()
                    if "latest handshake" in line:
                        tunnel.last_handshake = line.split(': ')[1]
                    elif "transfer" in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            tunnel.bytes_received = self._parse_bytes(parts[1])
                            tunnel.bytes_sent = self._parse_bytes(parts[3])
            else:
                tunnel.status = "down"

        except Exception as e:
            self.logger.error(f"Failed to get tunnel status for {peer_id}: {e}")
            tunnel.status = "error"

        return tunnel

    async def list_tunnels(self) -> List[TunnelEndpoint]:
        """List all active tunnels"""
        tunnels = []
        for peer_id in self.tunnels:
            tunnel_status = await self.get_tunnel_status(peer_id)
            if tunnel_status:
                tunnels.append(tunnel_status)
        return tunnels

    async def update_tunnel_route(self, peer_id: str, destination: str, next_hop: str) -> bool:
        """Update routing for a tunnel based on control plane decisions"""
        try:
            if peer_id not in self.tunnels:
                self.logger.error(f"Tunnel to {peer_id} does not exist")
                return False

            tunnel = self.tunnels[peer_id]

            # Add route through tunnel interface
            await self._execute_command([
                "ip", "route", "add", destination, "via", next_hop, "dev", tunnel.interface_name
            ])

            self.logger.info(f"Added route {destination} via {next_hop} through tunnel {tunnel.interface_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update tunnel route for {peer_id}: {e}")
            return False

    async def test_tunnel_connectivity(self, peer_id: str, timeout: int = 5) -> bool:
        """Test connectivity through a tunnel"""
        try:
            if peer_id not in self.tunnels:
                return False

            tunnel = self.tunnels[peer_id]

            # Ping remote endpoint through tunnel
            process = await asyncio.create_subprocess_exec(
                "ping", "-c", "3", "-W", str(timeout), tunnel.remote_ip,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            await process.communicate()
            return process.returncode == 0

        except Exception as e:
            self.logger.error(f"Failed to test tunnel connectivity for {peer_id}: {e}")
            return False

    def _generate_tunnel_config(self, tunnel: TunnelEndpoint) -> str:
        """Generate WireGuard configuration for a tunnel"""
        config = f"""[Interface]
PrivateKey = {self.node_keys.private_key}
Address = {tunnel.local_ip}/30
ListenPort = {tunnel.listen_port}
MTU = 1420

[Peer]
PublicKey = {tunnel.peer_public_key}
Endpoint = {tunnel.peer_endpoint}
AllowedIPs = {tunnel.remote_ip}/32
PersistentKeepalive = 25
"""
        return config

    def _allocate_tunnel_ip(self, peer_id: str, local: bool) -> str:
        """Allocate IP addresses for tunnel endpoints"""
        if peer_id in self.allocated_ips:
            return self.allocated_ips[peer_id]

        # Use /30 subnets for point-to-point tunnels
        subnet_size = 4  # /30 = 4 IPs (network, local, remote, broadcast)
        subnet_offset = self.tunnel_counter * subnet_size

        # Calculate subnet base
        subnet_base = int(self.tunnel_network.network_address) + subnet_offset + 1

        # Local IP is always first usable IP, remote is second
        if local:
            ip = str(ipaddress.IPv4Address(subnet_base))
        else:
            ip = str(ipaddress.IPv4Address(subnet_base + 1))

        if local:
            self.allocated_ips[peer_id] = ip
            self.tunnel_counter += 1

        return ip

    def _deallocate_tunnel_ip(self, peer_id: str):
        """Deallocate IP addresses for a tunnel"""
        if peer_id in self.allocated_ips:
            del self.allocated_ips[peer_id]

    def _get_next_port(self) -> int:
        """Get next available port for WireGuard"""
        port = self.next_port
        self.next_port += 1
        return port

    async def _bring_up_tunnel(self, tunnel: TunnelEndpoint):
        """Bring up a WireGuard tunnel interface"""
        try:
            # Create and configure interface
            await self._execute_command(["wg-quick", "up", tunnel.interface_name])

            # Add specific routes if needed
            await self._configure_tunnel_routing(tunnel)

            tunnel.status = "up"
            self.logger.info(f"Brought up tunnel interface {tunnel.interface_name}")

        except Exception as e:
            tunnel.status = "error"
            raise Exception(f"Failed to bring up tunnel {tunnel.interface_name}: {e}")

    async def _bring_down_tunnel(self, tunnel: TunnelEndpoint):
        """Bring down a WireGuard tunnel interface"""
        try:
            await self._execute_command(["wg-quick", "down", tunnel.interface_name])
            tunnel.status = "down"
            self.logger.info(f"Brought down tunnel interface {tunnel.interface_name}")

        except Exception as e:
            self.logger.error(f"Failed to bring down tunnel {tunnel.interface_name}: {e}")

    async def _configure_tunnel_routing(self, tunnel: TunnelEndpoint):
        """Configure routing for tunnel interface"""
        try:
            # Add route to peer through tunnel
            await self._execute_command([
                "ip", "route", "add", f"{tunnel.remote_ip}/32", "dev", tunnel.interface_name
            ])

        except subprocess.CalledProcessError as e:
            # Route might already exist
            if "File exists" not in str(e):
                raise

    async def _enable_ip_forwarding(self):
        """Enable IP forwarding for packet routing"""
        try:
            await self._execute_command([
                "sysctl", "-w", "net.ipv4.ip_forward=1"
            ])
            await self._execute_command([
                "sysctl", "-w", "net.ipv6.conf.all.forwarding=1"
            ])
            self.logger.info("Enabled IP forwarding")

        except Exception as e:
            self.logger.error(f"Failed to enable IP forwarding: {e}")

    def _execute_wg_command(self, args: List[str]) -> str:
        """Execute a WireGuard command synchronously"""
        try:
            cmd = ["wg"] + args
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout

        except subprocess.CalledProcessError as e:
            raise Exception(f"WireGuard command failed: {' '.join(cmd)} - {e}")

    async def _execute_wg_command_async(self, args: List[str]) -> str:
        """Execute a WireGuard command asynchronously"""
        try:
            cmd = ["wg"] + args
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode, cmd, stdout, stderr
                )

            return stdout.decode('utf-8')

        except Exception as e:
            raise Exception(f"WireGuard command failed: {' '.join(cmd)} - {e}")

    async def _execute_command(self, cmd: List[str]):
        """Execute a system command asynchronously"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode, cmd, stdout, stderr
                )

        except Exception as e:
            self.logger.error(f"Command execution failed: {' '.join(cmd)} - {e}")
            raise

    def _parse_bytes(self, byte_str: str) -> int:
        """Parse byte count from WireGuard output"""
        try:
            # Handle units like KiB, MiB, GiB
            if byte_str.endswith('KiB'):
                return int(float(byte_str[:-3]) * 1024)
            elif byte_str.endswith('MiB'):
                return int(float(byte_str[:-3]) * 1024 * 1024)
            elif byte_str.endswith('GiB'):
                return int(float(byte_str[:-3]) * 1024 * 1024 * 1024)
            elif byte_str.endswith('B'):
                return int(byte_str[:-1])
            else:
                return int(byte_str)

        except (ValueError, IndexError):
            return 0

    def get_public_key(self) -> str:
        """Get the public key for this node"""
        return self.node_keys.public_key

    async def exchange_keys_with_peer(self, peer_id: str, peer_endpoint: str) -> Optional[str]:
        """Exchange public keys with a peer (placeholder for key exchange protocol)"""
        # In a real implementation, this would implement a secure key exchange
        # For now, we assume keys are exchanged out-of-band
        self.logger.info(f"Key exchange with {peer_id} at {peer_endpoint} - implement secure exchange")
        return None

    async def get_tunnel_statistics(self) -> Dict[str, Any]:
        """Get comprehensive tunnel statistics"""
        try:
            stats = {
                "total_tunnels": len(self.tunnels),
                "active_tunnels": 0,
                "total_bytes_sent": 0,
                "total_bytes_received": 0,
                "tunnels": {}
            }

            for peer_id in self.tunnels:
                tunnel_status = await self.get_tunnel_status(peer_id)
                if tunnel_status:
                    if tunnel_status.status == "up":
                        stats["active_tunnels"] += 1

                    stats["total_bytes_sent"] += tunnel_status.bytes_sent
                    stats["total_bytes_received"] += tunnel_status.bytes_received

                    stats["tunnels"][peer_id] = {
                        "interface": tunnel_status.interface_name,
                        "status": tunnel_status.status,
                        "local_ip": tunnel_status.local_ip,
                        "remote_ip": tunnel_status.remote_ip,
                        "bytes_sent": tunnel_status.bytes_sent,
                        "bytes_received": tunnel_status.bytes_received,
                        "last_handshake": tunnel_status.last_handshake
                    }

            return stats

        except Exception as e:
            self.logger.error(f"Failed to get tunnel statistics: {e}")
            return {"error": str(e)}

    async def get_status(self) -> Dict[str, Any]:
        """Get overall tunnel orchestrator status"""
        return {
            "running": self.running,
            "node_id": self.node_id,
            "public_key": self.node_keys.public_key,
            "base_port": self.base_port,
            "tunnel_network": str(self.tunnel_network),
            "total_tunnels": len(self.tunnels),
            "allocated_ips": len(self.allocated_ips)
        }