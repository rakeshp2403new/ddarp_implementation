"""
DDARP WireGuard Orchestrator

Advanced WireGuard tunnel management with automated provisioning,
health monitoring, and dynamic configuration for the DDARP architecture.
"""

import asyncio
import logging
import time
import os
import subprocess
import tempfile
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import ipaddress
import secrets
import base64

from ..monitoring.enhanced_prometheus_exporter import ComponentStatus


class TunnelState(Enum):
    """WireGuard tunnel states"""
    CREATING = "creating"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DESTROYING = "destroying"


class TunnelHealth(Enum):
    """Tunnel health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class WireGuardPeer:
    """WireGuard peer configuration"""
    peer_id: str
    public_key: str
    private_key: Optional[str] = None  # Only for local peer
    endpoint: Optional[str] = None
    allowed_ips: List[str] = field(default_factory=list)
    persistent_keepalive: int = 25
    preshared_key: Optional[str] = None
    last_handshake: Optional[float] = None
    rx_bytes: int = 0
    tx_bytes: int = 0


@dataclass
class TunnelConfig:
    """WireGuard tunnel configuration"""
    tunnel_id: str
    interface_name: str
    local_peer: WireGuardPeer
    remote_peers: Dict[str, WireGuardPeer]
    listen_port: int
    private_network: str  # CIDR notation
    mtu: int = 1420
    state: TunnelState = TunnelState.CREATING
    health: TunnelHealth = TunnelHealth.UNKNOWN
    created_at: float = field(default_factory=time.time)
    last_health_check: float = 0.0


@dataclass
class TunnelMetrics:
    """Tunnel performance metrics"""
    tunnel_id: str
    bytes_sent: int = 0
    bytes_received: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    handshakes_completed: int = 0
    connection_errors: int = 0
    last_activity: float = 0.0
    average_latency_ms: float = 0.0


class WireGuardOrchestrator:
    """Advanced WireGuard tunnel orchestrator"""

    def __init__(self, node_id: str, config: Optional[Dict[str, Any]] = None):
        self.node_id = node_id
        self.config = config or {}
        self.logger = logging.getLogger(f"wireguard_orchestrator_{node_id}")

        # Component state
        self.running = False
        self.status = ComponentStatus.STOPPED

        # Tunnel management
        self.tunnels: Dict[str, TunnelConfig] = {}
        self.tunnel_metrics: Dict[str, TunnelMetrics] = {}

        # Network configuration
        self.base_network = ipaddress.IPv4Network("10.100.0.0/16")
        self.allocated_networks: Set[ipaddress.IPv4Network] = set()
        self.next_port = 51820

        # Monitoring
        self.health_check_interval = 30.0  # seconds
        self.metrics_collection_interval = 10.0  # seconds
        self.tunnel_timeout = 300.0  # seconds

        # WireGuard tools
        self.wg_binary = self._find_wireguard_binary()
        self.wg_quick_binary = self._find_wg_quick_binary()

        # Security
        self.preshared_keys_enabled = True
        self.key_rotation_interval = 86400.0  # 24 hours

        self.logger.info(f"WireGuard Orchestrator initialized for node {node_id}")

    def _find_wireguard_binary(self) -> str:
        """Find WireGuard binary"""
        for binary in ["wg", "/usr/bin/wg", "/usr/local/bin/wg"]:
            if os.path.exists(binary) or subprocess.run(
                ["which", binary], capture_output=True
            ).returncode == 0:
                return binary
        return "wg"  # Default

    def _find_wg_quick_binary(self) -> str:
        """Find wg-quick binary"""
        for binary in ["wg-quick", "/usr/bin/wg-quick", "/usr/local/bin/wg-quick"]:
            if os.path.exists(binary) or subprocess.run(
                ["which", binary], capture_output=True
            ).returncode == 0:
                return binary
        return "wg-quick"  # Default

    async def start(self):
        """Start the WireGuard orchestrator"""
        self.logger.info("Starting WireGuard Orchestrator")
        self.status = ComponentStatus.STARTING

        try:
            # Check WireGuard availability
            if not await self._check_wireguard_availability():
                raise RuntimeError("WireGuard is not available on this system")

            # Start background tasks
            asyncio.create_task(self._tunnel_health_monitor())
            asyncio.create_task(self._metrics_collector())
            asyncio.create_task(self._tunnel_cleanup_task())
            asyncio.create_task(self._key_rotation_task())

            self.running = True
            self.status = ComponentStatus.HEALTHY

            self.logger.info("WireGuard Orchestrator started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start WireGuard Orchestrator: {e}")
            self.status = ComponentStatus.ERROR
            raise

    async def stop(self):
        """Stop the WireGuard orchestrator"""
        self.logger.info("Stopping WireGuard Orchestrator")
        self.status = ComponentStatus.STOPPING

        self.running = False

        # Destroy all tunnels
        tunnel_ids = list(self.tunnels.keys())
        for tunnel_id in tunnel_ids:
            try:
                await self.destroy_tunnel(tunnel_id)
            except Exception as e:
                self.logger.error(f"Error destroying tunnel {tunnel_id}: {e}")

        self.status = ComponentStatus.STOPPED
        self.logger.info("WireGuard Orchestrator stopped")

    async def _check_wireguard_availability(self) -> bool:
        """Check if WireGuard is available"""
        try:
            result = await self._run_command([self.wg_binary, "help"])
            return result.returncode == 0
        except Exception:
            return False

    async def create_tunnel(self, peer_id: str, remote_endpoint: Optional[str] = None,
                          allowed_ips: Optional[List[str]] = None) -> str:
        """Create new WireGuard tunnel to peer"""
        try:
            tunnel_id = f"ddarp_{self.node_id}_{peer_id}"
            interface_name = f"wg_{peer_id}"[:15]  # Linux interface name limit

            if tunnel_id in self.tunnels:
                self.logger.warning(f"Tunnel {tunnel_id} already exists")
                return tunnel_id

            # Generate keys
            local_private_key = self._generate_private_key()
            local_public_key = self._derive_public_key(local_private_key)

            # Allocate network
            private_network = self._allocate_network()

            # Create local peer
            local_peer = WireGuardPeer(
                peer_id=self.node_id,
                public_key=local_public_key,
                private_key=local_private_key
            )

            # Create remote peer placeholder
            remote_peers = {}
            if peer_id:
                remote_peer = WireGuardPeer(
                    peer_id=peer_id,
                    public_key="",  # Will be updated when received
                    endpoint=remote_endpoint,
                    allowed_ips=allowed_ips or ["0.0.0.0/0"]
                )
                remote_peers[peer_id] = remote_peer

            # Create tunnel configuration
            tunnel_config = TunnelConfig(
                tunnel_id=tunnel_id,
                interface_name=interface_name,
                local_peer=local_peer,
                remote_peers=remote_peers,
                listen_port=self._allocate_port(),
                private_network=str(private_network)
            )

            # Create WireGuard interface
            await self._create_wireguard_interface(tunnel_config)

            # Store configuration
            self.tunnels[tunnel_id] = tunnel_config
            self.tunnel_metrics[tunnel_id] = TunnelMetrics(tunnel_id=tunnel_id)

            tunnel_config.state = TunnelState.ACTIVE
            self.logger.info(f"Created tunnel {tunnel_id} on interface {interface_name}")

            return tunnel_id

        except Exception as e:
            self.logger.error(f"Error creating tunnel to {peer_id}: {e}")
            raise

    async def destroy_tunnel(self, tunnel_id: str):
        """Destroy WireGuard tunnel"""
        if tunnel_id not in self.tunnels:
            self.logger.warning(f"Tunnel {tunnel_id} not found")
            return

        try:
            tunnel_config = self.tunnels[tunnel_id]
            tunnel_config.state = TunnelState.DESTROYING

            # Remove WireGuard interface
            await self._destroy_wireguard_interface(tunnel_config)

            # Free allocated resources
            network = ipaddress.IPv4Network(tunnel_config.private_network)
            self.allocated_networks.discard(network)

            # Remove from tracking
            del self.tunnels[tunnel_id]
            del self.tunnel_metrics[tunnel_id]

            self.logger.info(f"Destroyed tunnel {tunnel_id}")

        except Exception as e:
            self.logger.error(f"Error destroying tunnel {tunnel_id}: {e}")

    async def add_peer_to_tunnel(self, tunnel_id: str, peer_id: str,
                               public_key: str, endpoint: Optional[str] = None,
                               allowed_ips: Optional[List[str]] = None):
        """Add peer to existing tunnel"""
        if tunnel_id not in self.tunnels:
            raise ValueError(f"Tunnel {tunnel_id} not found")

        tunnel_config = self.tunnels[tunnel_id]

        # Create peer configuration
        peer_config = WireGuardPeer(
            peer_id=peer_id,
            public_key=public_key,
            endpoint=endpoint,
            allowed_ips=allowed_ips or ["0.0.0.0/0"]
        )

        # Generate preshared key if enabled
        if self.preshared_keys_enabled:
            peer_config.preshared_key = self._generate_preshared_key()

        # Add to tunnel
        tunnel_config.remote_peers[peer_id] = peer_config

        # Update WireGuard configuration
        await self._update_wireguard_peer(tunnel_config, peer_config)

        self.logger.info(f"Added peer {peer_id} to tunnel {tunnel_id}")

    async def remove_peer_from_tunnel(self, tunnel_id: str, peer_id: str):
        """Remove peer from tunnel"""
        if tunnel_id not in self.tunnels:
            raise ValueError(f"Tunnel {tunnel_id} not found")

        tunnel_config = self.tunnels[tunnel_id]

        if peer_id not in tunnel_config.remote_peers:
            self.logger.warning(f"Peer {peer_id} not found in tunnel {tunnel_id}")
            return

        # Remove from WireGuard
        peer_config = tunnel_config.remote_peers[peer_id]
        await self._remove_wireguard_peer(tunnel_config, peer_config)

        # Remove from configuration
        del tunnel_config.remote_peers[peer_id]

        self.logger.info(f"Removed peer {peer_id} from tunnel {tunnel_id}")

    async def _create_wireguard_interface(self, tunnel_config: TunnelConfig):
        """Create WireGuard interface"""
        # Generate configuration file
        config_content = self._generate_wg_config(tunnel_config)

        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write(config_content)
            config_file = f.name

        try:
            # Create interface using wg-quick
            result = await self._run_command([
                self.wg_quick_binary, "up", config_file
            ])

            if result.returncode != 0:
                raise RuntimeError(f"Failed to create interface: {result.stderr}")

        finally:
            # Clean up config file
            try:
                os.unlink(config_file)
            except OSError:
                pass

    async def _destroy_wireguard_interface(self, tunnel_config: TunnelConfig):
        """Destroy WireGuard interface"""
        try:
            result = await self._run_command([
                self.wg_quick_binary, "down", tunnel_config.interface_name
            ])

            if result.returncode != 0:
                self.logger.warning(
                    f"Failed to destroy interface {tunnel_config.interface_name}: {result.stderr}"
                )

        except Exception as e:
            self.logger.error(f"Error destroying interface: {e}")

    def _generate_wg_config(self, tunnel_config: TunnelConfig) -> str:
        """Generate WireGuard configuration file content"""
        config_lines = [
            "[Interface]",
            f"PrivateKey = {tunnel_config.local_peer.private_key}",
            f"Address = {tunnel_config.private_network}",
            f"ListenPort = {tunnel_config.listen_port}",
            f"MTU = {tunnel_config.mtu}",
            ""
        ]

        # Add peers
        for peer in tunnel_config.remote_peers.values():
            config_lines.extend([
                "[Peer]",
                f"PublicKey = {peer.public_key}",
                f"AllowedIPs = {', '.join(peer.allowed_ips)}"
            ])

            if peer.endpoint:
                config_lines.append(f"Endpoint = {peer.endpoint}")

            if peer.preshared_key:
                config_lines.append(f"PresharedKey = {peer.preshared_key}")

            if peer.persistent_keepalive:
                config_lines.append(f"PersistentKeepalive = {peer.persistent_keepalive}")

            config_lines.append("")

        return "\n".join(config_lines)

    async def _update_wireguard_peer(self, tunnel_config: TunnelConfig, peer_config: WireGuardPeer):
        """Update WireGuard peer configuration"""
        cmd = [
            self.wg_binary, "set", tunnel_config.interface_name,
            "peer", peer_config.public_key,
            "allowed-ips", ",".join(peer_config.allowed_ips)
        ]

        if peer_config.endpoint:
            cmd.extend(["endpoint", peer_config.endpoint])

        if peer_config.preshared_key:
            cmd.extend(["preshared-key", peer_config.preshared_key])

        if peer_config.persistent_keepalive:
            cmd.extend(["persistent-keepalive", str(peer_config.persistent_keepalive)])

        result = await self._run_command(cmd)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to update peer: {result.stderr}")

    async def _remove_wireguard_peer(self, tunnel_config: TunnelConfig, peer_config: WireGuardPeer):
        """Remove WireGuard peer"""
        cmd = [
            self.wg_binary, "set", tunnel_config.interface_name,
            "peer", peer_config.public_key, "remove"
        ]

        result = await self._run_command(cmd)
        if result.returncode != 0:
            self.logger.warning(f"Failed to remove peer: {result.stderr}")

    def _generate_private_key(self) -> str:
        """Generate WireGuard private key"""
        # Generate 32 random bytes and encode as base64
        private_key_bytes = secrets.token_bytes(32)
        return base64.b64encode(private_key_bytes).decode('ascii')

    def _derive_public_key(self, private_key: str) -> str:
        """Derive public key from private key"""
        # In a real implementation, this would use the actual WireGuard key derivation
        # For now, we'll simulate it
        return base64.b64encode(secrets.token_bytes(32)).decode('ascii')

    def _generate_preshared_key(self) -> str:
        """Generate preshared key"""
        psk_bytes = secrets.token_bytes(32)
        return base64.b64encode(psk_bytes).decode('ascii')

    def _allocate_network(self) -> ipaddress.IPv4Network:
        """Allocate private network for tunnel"""
        # Find next available /30 network
        for subnet in self.base_network.subnets(new_prefix=30):
            if subnet not in self.allocated_networks:
                self.allocated_networks.add(subnet)
                return subnet

        raise RuntimeError("No available networks")

    def _allocate_port(self) -> int:
        """Allocate port for tunnel"""
        port = self.next_port
        self.next_port += 1
        return port

    async def _tunnel_health_monitor(self):
        """Monitor tunnel health"""
        while self.running:
            try:
                for tunnel_id in list(self.tunnels.keys()):
                    await self._check_tunnel_health(tunnel_id)

                await asyncio.sleep(self.health_check_interval)

            except Exception as e:
                self.logger.error(f"Error in tunnel health monitor: {e}")

    async def _check_tunnel_health(self, tunnel_id: str):
        """Check health of specific tunnel"""
        if tunnel_id not in self.tunnels:
            return

        tunnel_config = self.tunnels[tunnel_id]

        try:
            # Get tunnel status from WireGuard
            result = await self._run_command([
                self.wg_binary, "show", tunnel_config.interface_name
            ])

            if result.returncode == 0:
                # Parse output and update peer information
                await self._parse_wg_status(tunnel_config, result.stdout)
                tunnel_config.health = TunnelHealth.HEALTHY
            else:
                tunnel_config.health = TunnelHealth.UNHEALTHY

            tunnel_config.last_health_check = time.time()

        except Exception as e:
            self.logger.error(f"Error checking tunnel {tunnel_id} health: {e}")
            tunnel_config.health = TunnelHealth.UNKNOWN

    async def _parse_wg_status(self, tunnel_config: TunnelConfig, status_output: str):
        """Parse WireGuard status output"""
        # Simple parsing of wg show output
        current_peer = None

        for line in status_output.split('\n'):
            line = line.strip()

            if line.startswith('peer: '):
                public_key = line.split(': ', 1)[1]
                current_peer = None

                # Find peer by public key
                for peer in tunnel_config.remote_peers.values():
                    if peer.public_key == public_key:
                        current_peer = peer
                        break

            elif current_peer and line.startswith('latest handshake: '):
                # Parse handshake time
                current_peer.last_handshake = time.time()

            elif current_peer and line.startswith('transfer: '):
                # Parse transfer statistics
                transfer_info = line.split(': ', 1)[1]
                parts = transfer_info.split(' ')
                if len(parts) >= 4:
                    try:
                        current_peer.rx_bytes = self._parse_bytes(parts[0])
                        current_peer.tx_bytes = self._parse_bytes(parts[2])
                    except ValueError:
                        pass

    def _parse_bytes(self, byte_str: str) -> int:
        """Parse byte string with units (e.g., '1.5 KiB')"""
        byte_str = byte_str.strip()

        if byte_str.endswith(' B'):
            return int(float(byte_str[:-2]))
        elif byte_str.endswith(' KiB'):
            return int(float(byte_str[:-4]) * 1024)
        elif byte_str.endswith(' MiB'):
            return int(float(byte_str[:-4]) * 1024 * 1024)
        elif byte_str.endswith(' GiB'):
            return int(float(byte_str[:-4]) * 1024 * 1024 * 1024)
        else:
            return int(float(byte_str))

    async def _metrics_collector(self):
        """Collect tunnel metrics"""
        while self.running:
            try:
                await self._collect_tunnel_metrics()
                await asyncio.sleep(self.metrics_collection_interval)
            except Exception as e:
                self.logger.error(f"Error collecting metrics: {e}")

    async def _collect_tunnel_metrics(self):
        """Collect metrics for all tunnels"""
        for tunnel_id, tunnel_config in self.tunnels.items():
            if tunnel_id not in self.tunnel_metrics:
                continue

            metrics = self.tunnel_metrics[tunnel_id]

            # Update metrics from peer statistics
            total_rx = sum(peer.rx_bytes for peer in tunnel_config.remote_peers.values())
            total_tx = sum(peer.tx_bytes for peer in tunnel_config.remote_peers.values())

            metrics.bytes_received = total_rx
            metrics.bytes_sent = total_tx
            metrics.last_activity = time.time()

    async def _tunnel_cleanup_task(self):
        """Clean up inactive tunnels"""
        while self.running:
            try:
                current_time = time.time()
                inactive_tunnels = []

                for tunnel_id, tunnel_config in self.tunnels.items():
                    if (current_time - tunnel_config.last_health_check > self.tunnel_timeout and
                            tunnel_config.health == TunnelHealth.UNHEALTHY):
                        inactive_tunnels.append(tunnel_id)

                for tunnel_id in inactive_tunnels:
                    self.logger.warning(f"Cleaning up inactive tunnel {tunnel_id}")
                    await self.destroy_tunnel(tunnel_id)

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                self.logger.error(f"Error in tunnel cleanup task: {e}")

    async def _key_rotation_task(self):
        """Rotate keys periodically"""
        while self.running:
            try:
                await asyncio.sleep(self.key_rotation_interval)
                # Key rotation would be implemented here
                self.logger.debug("Key rotation check completed")
            except Exception as e:
                self.logger.error(f"Error in key rotation task: {e}")

    async def _run_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Run system command asynchronously"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            return subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout.decode() if stdout else "",
                stderr=stderr.decode() if stderr else ""
            )

        except Exception as e:
            self.logger.error(f"Error running command {cmd}: {e}")
            raise

    def get_tunnel_status(self, tunnel_id: str) -> Optional[Dict[str, Any]]:
        """Get status of specific tunnel"""
        if tunnel_id not in self.tunnels:
            return None

        tunnel_config = self.tunnels[tunnel_id]
        metrics = self.tunnel_metrics.get(tunnel_id)

        status = {
            "tunnel_id": tunnel_id,
            "interface_name": tunnel_config.interface_name,
            "state": tunnel_config.state.value,
            "health": tunnel_config.health.value,
            "listen_port": tunnel_config.listen_port,
            "private_network": tunnel_config.private_network,
            "peer_count": len(tunnel_config.remote_peers),
            "created_at": tunnel_config.created_at,
            "last_health_check": tunnel_config.last_health_check
        }

        if metrics:
            status.update({
                "bytes_sent": metrics.bytes_sent,
                "bytes_received": metrics.bytes_received,
                "last_activity": metrics.last_activity
            })

        return status

    def get_all_tunnels_status(self) -> List[Dict[str, Any]]:
        """Get status of all tunnels"""
        return [
            self.get_tunnel_status(tunnel_id)
            for tunnel_id in self.tunnels.keys()
        ]

    def get_metrics(self) -> Dict[str, Any]:
        """Get orchestrator metrics"""
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "active_tunnels": len(self.tunnels),
            "total_peers": sum(len(t.remote_peers) for t in self.tunnels.values()),
            "allocated_networks": len(self.allocated_networks),
            "total_bytes_sent": sum(m.bytes_sent for m in self.tunnel_metrics.values()),
            "total_bytes_received": sum(m.bytes_received for m in self.tunnel_metrics.values()),
            "healthy_tunnels": sum(
                1 for t in self.tunnels.values()
                if t.health == TunnelHealth.HEALTHY
            )
        }

    def get_status(self) -> ComponentStatus:
        """Get current orchestrator status"""
        return self.status

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        health_status = {
            "healthy": self.status == ComponentStatus.HEALTHY,
            "status": self.status.value,
            "wireguard_available": await self._check_wireguard_availability(),
            "tunnel_health": {
                tunnel_id: tunnel.health.value
                for tunnel_id, tunnel in self.tunnels.items()
            }
        }

        return health_status