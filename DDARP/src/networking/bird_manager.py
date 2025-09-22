"""
BIRD eBGP Integration Manager

Manages BIRD routing daemon integration for DDARP, including:
- BGP session management
- Route injection with OWL metrics as communities
- Configuration generation and updates
- BGP peer status monitoring
"""

import asyncio
import logging
import subprocess
import json
import os
import tempfile
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class BGPPeer:
    """BGP peer configuration"""
    peer_id: str
    peer_ip: str
    peer_asn: int
    local_asn: int
    session_state: str = "idle"
    routes_received: int = 0
    routes_sent: int = 0
    last_error: Optional[str] = None


@dataclass
class BGPRoute:
    """BGP route information"""
    prefix: str
    next_hop: str
    as_path: List[int]
    communities: List[str]
    local_pref: int
    origin: str
    med: int = 0


class BIRDManager:
    """Manages BIRD routing daemon for eBGP integration"""

    # BGP Communities for OWL metrics encoding
    COMMUNITY_LATENCY = 65000
    COMMUNITY_JITTER = 65001
    COMMUNITY_LOSS = 65002
    COMMUNITY_HYSTERESIS = 65003

    def __init__(self, node_id: str, local_asn: int, router_id: str,
                 config_dir: str = "/etc/bird", socket_path: str = "/var/run/bird/bird.ctl"):
        self.node_id = node_id
        self.local_asn = local_asn
        self.router_id = router_id
        self.config_dir = Path(config_dir)
        self.socket_path = socket_path
        self.config_file = self.config_dir / "bird.conf"
        self.peers: Dict[str, BGPPeer] = {}
        self.routes: Dict[str, BGPRoute] = {}
        self.logger = logging.getLogger(f"bird_manager_{node_id}")
        self.running = False

    async def start(self):
        """Initialize BIRD manager"""
        self.logger.info(f"Starting BIRD manager for {self.node_id}")

        # Create config directory
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Generate initial configuration
        await self.generate_config()

        # Start BIRD daemon
        await self.start_bird()

        self.running = True
        self.logger.info("BIRD manager started successfully")

    async def stop(self):
        """Stop BIRD manager"""
        self.logger.info("Stopping BIRD manager")
        self.running = False

        try:
            await self.execute_birdc("down")
        except Exception as e:
            self.logger.warning(f"Error stopping BIRD: {e}")

    async def start_bird(self):
        """Start BIRD daemon process"""
        try:
            # Kill any existing BIRD process
            await self.execute_command(["pkill", "-f", "bird"], check=False)
            await asyncio.sleep(1)

            # Start BIRD daemon
            cmd = [
                "bird",
                "-c", str(self.config_file),
                "-s", self.socket_path,
                "-P", f"/var/run/bird/bird.pid"
            ]

            self.logger.info(f"Starting BIRD with command: {' '.join(cmd)}")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait a moment for BIRD to start
            await asyncio.sleep(2)

            # Check if BIRD started successfully
            result = await self.execute_birdc("show status")
            if "BIRD" in result:
                self.logger.info("BIRD daemon started successfully")
            else:
                raise Exception("BIRD failed to start properly")

        except Exception as e:
            self.logger.error(f"Failed to start BIRD: {e}")
            raise

    async def generate_config(self):
        """Generate BIRD configuration file"""
        config_template = f"""
# BIRD configuration for DDARP node {self.node_id}
router id {self.router_id};

log syslog all;
debug protocols {{ events, states }};

# Define constants for OWL metrics communities
define COMMUNITY_LATENCY = ({self.COMMUNITY_LATENCY}, 1);
define COMMUNITY_JITTER = ({self.COMMUNITY_JITTER}, 1);
define COMMUNITY_LOSS = ({self.COMMUNITY_LOSS}, 1);
define COMMUNITY_HYSTERESIS = ({self.COMMUNITY_HYSTERESIS}, 1);

# Filter for importing routes with hysteresis logic
filter import_owl {{
    # Accept routes with performance communities
    if bgp_community ~ [({self.COMMUNITY_LATENCY}, *)] then {{
        # Extract latency from community (encoded as community value * 10)
        # Apply hysteresis: only accept if 20% better than existing
        accept;
    }}
    reject;
}}

# Filter for exporting routes with OWL metrics
filter export_owl {{
    # Add OWL metrics as BGP communities before advertising
    # This will be dynamically updated by the BIRD manager
    accept;
}}

# Device protocol for interface monitoring
protocol device {{
    scan time 10;
}}

# Kernel protocol for route synchronization
protocol kernel {{
    ipv4 {{
        import none;
        export where source = RTS_BGP;
    }};
}}

# Direct protocol for connected routes
protocol direct {{
    ipv4;
    interface "eth0", "wg*";
}}

# Static routes for local networks
protocol static static_routes {{
    ipv4;
    # Add static routes here
}}

"""

        # Add BGP peer configurations
        for peer_id, peer in self.peers.items():
            config_template += f"""
# BGP peer {peer_id}
protocol bgp bgp_{peer_id} {{
    local as {peer.local_asn};
    neighbor {peer.peer_ip} as {peer.peer_asn};

    ipv4 {{
        import filter import_owl;
        export filter export_owl;
        next hop self;
    }};

    # Enable communities for OWL metrics
    enable route refresh;

    # Connection parameters
    connect retry time 30;
    hold time 90;
    keepalive time 30;

    # Multi-hop eBGP support
    multihop 64;

    # Error handling
    error wait time 60, 300;
}}
"""

        # Write configuration to file
        try:
            with open(self.config_file, 'w') as f:
                f.write(config_template)
            self.logger.info(f"Generated BIRD configuration: {self.config_file}")
        except Exception as e:
            self.logger.error(f"Failed to write BIRD config: {e}")
            raise

    async def add_peer(self, peer_id: str, peer_ip: str, peer_asn: int) -> bool:
        """Add a new BGP peer"""
        try:
            peer = BGPPeer(
                peer_id=peer_id,
                peer_ip=peer_ip,
                peer_asn=peer_asn,
                local_asn=self.local_asn
            )

            self.peers[peer_id] = peer
            self.logger.info(f"Added BGP peer {peer_id} ({peer_ip}, AS{peer_asn})")

            # Regenerate and reload configuration
            await self.generate_config()
            await self.reload_config()

            return True

        except Exception as e:
            self.logger.error(f"Failed to add BGP peer {peer_id}: {e}")
            return False

    async def remove_peer(self, peer_id: str) -> bool:
        """Remove a BGP peer"""
        try:
            if peer_id in self.peers:
                # Disable BGP session first
                await self.execute_birdc(f"disable bgp_{peer_id}")

                del self.peers[peer_id]
                self.logger.info(f"Removed BGP peer {peer_id}")

                # Regenerate and reload configuration
                await self.generate_config()
                await self.reload_config()

                return True
            else:
                self.logger.warning(f"BGP peer {peer_id} not found")
                return False

        except Exception as e:
            self.logger.error(f"Failed to remove BGP peer {peer_id}: {e}")
            return False

    async def inject_route(self, prefix: str, next_hop: str, owl_metrics: Dict[str, float]) -> bool:
        """Inject a route with OWL metrics as BGP communities"""
        try:
            # Encode OWL metrics as community values (multiply by 10 for precision)
            latency_community = f"({self.COMMUNITY_LATENCY}, {int(owl_metrics.get('latency_ms', 0) * 10)})"
            jitter_community = f"({self.COMMUNITY_JITTER}, {int(owl_metrics.get('jitter_ms', 0) * 10)})"
            loss_community = f"({self.COMMUNITY_LOSS}, {int(owl_metrics.get('packet_loss_percent', 0) * 10)})"

            # Create static route with communities
            route_config = f"""
route {prefix} via {next_hop} {{
    bgp_community.add([{latency_community}, {jitter_community}, {loss_community}]);
    bgp_local_pref = {1000 - int(owl_metrics.get('latency_ms', 0))};
}};
"""

            # Add route via birdc
            cmd = f"configure soft \"{route_config}\""
            result = await self.execute_birdc(cmd)

            self.logger.info(f"Injected route {prefix} via {next_hop} with OWL metrics")
            return True

        except Exception as e:
            self.logger.error(f"Failed to inject route {prefix}: {e}")
            return False

    async def get_peer_status(self, peer_id: str) -> Optional[BGPPeer]:
        """Get BGP peer status"""
        try:
            if peer_id not in self.peers:
                return None

            # Query BIRD for peer status
            result = await self.execute_birdc(f"show protocols all bgp_{peer_id}")

            peer = self.peers[peer_id]

            # Parse BIRD output to update peer status
            if "Established" in result:
                peer.session_state = "established"
            elif "Connect" in result:
                peer.session_state = "connect"
            elif "OpenSent" in result:
                peer.session_state = "opensent"
            elif "OpenConfirm" in result:
                peer.session_state = "openconfirm"
            else:
                peer.session_state = "idle"

            # Extract route counts
            import re
            routes_pattern = r"Routes:\s+(\d+)\s+imported,\s+(\d+)\s+exported"
            match = re.search(routes_pattern, result)
            if match:
                peer.routes_received = int(match.group(1))
                peer.routes_sent = int(match.group(2))

            return peer

        except Exception as e:
            self.logger.error(f"Failed to get peer status for {peer_id}: {e}")
            return None

    async def get_bgp_routes(self) -> List[BGPRoute]:
        """Get all BGP routes"""
        try:
            result = await self.execute_birdc("show route all protocol bgp*")
            routes = []

            # Parse BIRD output to extract routes
            # This is a simplified parser - production code would be more robust
            current_route = None

            for line in result.split('\n'):
                line = line.strip()

                # New route entry
                if '/' in line and 'via' in line:
                    if current_route:
                        routes.append(current_route)

                    parts = line.split()
                    prefix = parts[0]
                    next_hop = parts[2] if len(parts) > 2 else ""

                    current_route = BGPRoute(
                        prefix=prefix,
                        next_hop=next_hop,
                        as_path=[],
                        communities=[],
                        local_pref=100,
                        origin="igp"
                    )

                # Parse route attributes
                elif current_route and line.startswith("BGP."):
                    if "as_path" in line:
                        # Parse AS path
                        pass
                    elif "community" in line:
                        # Parse communities
                        pass
                    elif "local_pref" in line:
                        # Parse local preference
                        pass

            if current_route:
                routes.append(current_route)

            return routes

        except Exception as e:
            self.logger.error(f"Failed to get BGP routes: {e}")
            return []

    async def reload_config(self):
        """Reload BIRD configuration"""
        try:
            await self.execute_birdc("configure")
            self.logger.info("BIRD configuration reloaded")
        except Exception as e:
            self.logger.error(f"Failed to reload BIRD config: {e}")
            raise

    async def execute_birdc(self, command: str) -> str:
        """Execute a birdc command"""
        try:
            cmd = ["birdc", "-s", self.socket_path, command]
            result = await self.execute_command(cmd)
            return result
        except Exception as e:
            self.logger.error(f"birdc command failed: {command} - {e}")
            raise

    async def execute_command(self, cmd: List[str], check: bool = True) -> str:
        """Execute a system command"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if check and process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode, cmd, stdout, stderr
                )

            return stdout.decode('utf-8')

        except Exception as e:
            self.logger.error(f"Command execution failed: {' '.join(cmd)} - {e}")
            raise

    def encode_owl_metrics_as_communities(self, metrics: Dict[str, float]) -> List[str]:
        """Encode OWL metrics as BGP community strings"""
        communities = []

        # Encode latency (multiply by 10 for 0.1ms precision)
        if 'latency_ms' in metrics:
            latency_val = int(metrics['latency_ms'] * 10)
            communities.append(f"{self.COMMUNITY_LATENCY}:{latency_val}")

        # Encode jitter
        if 'jitter_ms' in metrics:
            jitter_val = int(metrics['jitter_ms'] * 10)
            communities.append(f"{self.COMMUNITY_JITTER}:{jitter_val}")

        # Encode packet loss
        if 'packet_loss_percent' in metrics:
            loss_val = int(metrics['packet_loss_percent'] * 10)
            communities.append(f"{self.COMMUNITY_LOSS}:{loss_val}")

        return communities

    def decode_owl_metrics_from_communities(self, communities: List[str]) -> Dict[str, float]:
        """Decode OWL metrics from BGP communities"""
        metrics = {}

        for community in communities:
            if ':' not in community:
                continue

            try:
                asn, value = community.split(':')
                asn = int(asn)
                value = int(value)

                if asn == self.COMMUNITY_LATENCY:
                    metrics['latency_ms'] = value / 10.0
                elif asn == self.COMMUNITY_JITTER:
                    metrics['jitter_ms'] = value / 10.0
                elif asn == self.COMMUNITY_LOSS:
                    metrics['packet_loss_percent'] = value / 10.0

            except ValueError:
                continue

        return metrics

    async def apply_hysteresis_filter(self, new_route: BGPRoute, existing_route: Optional[BGPRoute]) -> bool:
        """Apply hysteresis logic to route updates"""
        if not existing_route:
            return True  # Accept new routes

        # Decode metrics from communities
        new_metrics = self.decode_owl_metrics_from_communities(new_route.communities)
        existing_metrics = self.decode_owl_metrics_from_communities(existing_route.communities)

        # Calculate improvement threshold (20%)
        threshold = 0.20

        # Check latency improvement
        if 'latency_ms' in new_metrics and 'latency_ms' in existing_metrics:
            improvement = (existing_metrics['latency_ms'] - new_metrics['latency_ms']) / existing_metrics['latency_ms']
            if improvement >= threshold:
                return True

        # Check packet loss improvement
        if 'packet_loss_percent' in new_metrics and 'packet_loss_percent' in existing_metrics:
            if existing_metrics['packet_loss_percent'] > 0:
                improvement = (existing_metrics['packet_loss_percent'] - new_metrics['packet_loss_percent']) / existing_metrics['packet_loss_percent']
                if improvement >= threshold:
                    return True

        return False  # No significant improvement

    async def get_status(self) -> Dict[str, Any]:
        """Get overall BIRD manager status"""
        try:
            status = {
                "running": self.running,
                "router_id": self.router_id,
                "local_asn": self.local_asn,
                "peers": {},
                "total_routes": 0,
                "bird_status": "unknown"
            }

            # Get BIRD daemon status
            try:
                bird_status = await self.execute_birdc("show status")
                if "BIRD" in bird_status:
                    status["bird_status"] = "running"
                else:
                    status["bird_status"] = "error"
            except:
                status["bird_status"] = "not_running"

            # Get peer statuses
            for peer_id in self.peers:
                peer_status = await self.get_peer_status(peer_id)
                if peer_status:
                    status["peers"][peer_id] = {
                        "state": peer_status.session_state,
                        "routes_received": peer_status.routes_received,
                        "routes_sent": peer_status.routes_sent
                    }

            # Get route count
            routes = await self.get_bgp_routes()
            status["total_routes"] = len(routes)

            return status

        except Exception as e:
            self.logger.error(f"Failed to get BIRD status: {e}")
            return {"running": False, "error": str(e)}