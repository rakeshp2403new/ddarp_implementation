"""
Data Plane Manager

Integrates WireGuard tunnels, BIRD BGP routing, and DDARP control plane
to create a complete data forwarding solution. Handles:
- Tunnel lifecycle management based on routing decisions
- Route injection and forwarding table updates
- Data plane connectivity testing
- Integration between control plane, BGP, and tunnels
"""

import asyncio
import logging
import ipaddress
import json
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from pathlib import Path

from .bird_manager import BIRDManager, BGPPeer
from .tunnel_orchestrator import TunnelOrchestrator, TunnelEndpoint


@dataclass
class ForwardingEntry:
    """Data plane forwarding table entry"""
    destination: str
    next_hop: str
    interface: str
    tunnel_peer: Optional[str]
    metric: float
    last_updated: float


@dataclass
class DataPlaneRoute:
    """Combined routing information from control plane and BGP"""
    destination: str
    control_plane_path: List[str]
    bgp_next_hop: Optional[str]
    tunnel_interface: Optional[str]
    owl_metrics: Dict[str, float]
    active: bool = False


class DataPlaneManager:
    """Manages the complete data plane including tunnels, BGP, and forwarding"""

    def __init__(self, node_id: str, local_asn: int, router_id: str,
                 base_tunnel_port: int = 51820, tunnel_network: str = "10.100.0.0/16"):
        self.node_id = node_id
        self.local_asn = local_asn
        self.router_id = router_id

        # Initialize component managers
        self.bird_manager = BIRDManager(
            node_id=node_id,
            local_asn=local_asn,
            router_id=router_id
        )

        self.tunnel_orchestrator = TunnelOrchestrator(
            node_id=node_id,
            base_port=base_tunnel_port,
            tunnel_network=tunnel_network
        )

        # Forwarding state
        self.forwarding_table: Dict[str, ForwardingEntry] = {}
        self.active_routes: Dict[str, DataPlaneRoute] = {}
        self.peer_mappings: Dict[str, str] = {}  # peer_id -> tunnel_ip mapping

        # Configuration
        self.hysteresis_threshold = 0.20  # 20% improvement threshold
        self.tunnel_timeout = 300  # 5 minutes tunnel idle timeout
        self.route_refresh_interval = 30  # 30 seconds

        self.logger = logging.getLogger(f"data_plane_{node_id}")
        self.running = False

        # Background tasks
        self.maintenance_task: Optional[asyncio.Task] = None

    async def start(self):
        """Initialize the data plane manager"""
        self.logger.info(f"Starting data plane manager for {self.node_id}")

        try:
            # Start component managers
            await self.bird_manager.start()
            await self.tunnel_orchestrator.start()

            # Start background maintenance
            self.maintenance_task = asyncio.create_task(self._maintenance_loop())

            self.running = True
            self.logger.info("Data plane manager started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start data plane manager: {e}")
            await self.stop()
            raise

    async def stop(self):
        """Stop the data plane manager"""
        self.logger.info("Stopping data plane manager")
        self.running = False

        # Cancel background tasks
        if self.maintenance_task:
            self.maintenance_task.cancel()
            try:
                await self.maintenance_task
            except asyncio.CancelledError:
                pass

        # Stop component managers
        try:
            await self.bird_manager.stop()
        except Exception as e:
            self.logger.error(f"Error stopping BIRD manager: {e}")

        try:
            await self.tunnel_orchestrator.stop()
        except Exception as e:
            self.logger.error(f"Error stopping tunnel orchestrator: {e}")

    async def add_peer(self, peer_id: str, peer_ip: str, peer_asn: int,
                      peer_public_key: str, peer_endpoint: str) -> bool:
        """Add a new peer with BGP session and tunnel capability"""
        try:
            self.logger.info(f"Adding peer {peer_id} ({peer_ip}, AS{peer_asn})")

            # Add BGP peer
            bgp_success = await self.bird_manager.add_peer(peer_id, peer_ip, peer_asn)
            if not bgp_success:
                self.logger.error(f"Failed to add BGP peer {peer_id}")
                return False

            # Store peer mapping for tunnel creation
            self.peer_mappings[peer_id] = peer_ip

            self.logger.info(f"Successfully added peer {peer_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to add peer {peer_id}: {e}")
            return False

    async def remove_peer(self, peer_id: str) -> bool:
        """Remove a peer and cleanup associated tunnels"""
        try:
            self.logger.info(f"Removing peer {peer_id}")

            # Remove tunnel if exists
            await self.tunnel_orchestrator.remove_tunnel(peer_id)

            # Remove BGP peer
            bgp_success = await self.bird_manager.remove_peer(peer_id)

            # Clean up forwarding entries
            await self._cleanup_peer_routes(peer_id)

            # Remove peer mapping
            if peer_id in self.peer_mappings:
                del self.peer_mappings[peer_id]

            self.logger.info(f"Successfully removed peer {peer_id}")
            return bgp_success

        except Exception as e:
            self.logger.error(f"Failed to remove peer {peer_id}: {e}")
            return False

    async def update_route(self, destination: str, path: List[str],
                          owl_metrics: Dict[str, float]) -> bool:
        """Update routing based on control plane path decision"""
        try:
            if not path or len(path) < 2:
                self.logger.warning(f"Invalid path for destination {destination}: {path}")
                return False

            next_hop_peer = path[1]  # Next hop in the path

            self.logger.debug(f"Updating route to {destination} via {path}")

            # Create or update route entry
            route = DataPlaneRoute(
                destination=destination,
                control_plane_path=path,
                bgp_next_hop=None,
                tunnel_interface=None,
                owl_metrics=owl_metrics
            )

            # Check if we need to create a tunnel
            tunnel_needed = await self._evaluate_tunnel_requirement(
                destination, next_hop_peer, owl_metrics
            )

            if tunnel_needed:
                success = await self._setup_tunnel_route(route, next_hop_peer)
                if not success:
                    return False
            else:
                success = await self._setup_bgp_route(route, next_hop_peer)
                if not success:
                    return False

            # Update forwarding table
            await self._update_forwarding_table(route)

            # Inject route into BGP with OWL metrics
            await self._inject_bgp_route(destination, owl_metrics)

            self.active_routes[destination] = route
            route.active = True

            self.logger.info(f"Successfully updated route to {destination}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update route to {destination}: {e}")
            return False

    async def remove_route(self, destination: str) -> bool:
        """Remove a route from the data plane"""
        try:
            if destination not in self.active_routes:
                return True

            route = self.active_routes[destination]

            # Remove from forwarding table
            if destination in self.forwarding_table:
                del self.forwarding_table[destination]

            # Clean up tunnel if it was tunnel-only route
            if route.tunnel_interface:
                await self._cleanup_tunnel_route(route)

            # Remove from BGP
            # Note: BIRD doesn't have a simple route removal API
            # This would typically be handled by not re-advertising the route

            del self.active_routes[destination]
            route.active = False

            self.logger.info(f"Removed route to {destination}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to remove route to {destination}: {e}")
            return False

    async def test_forwarding(self, destination: str, packet_count: int = 3) -> Dict[str, Any]:
        """Test data plane forwarding to a destination"""
        try:
            test_result = {
                "destination": destination,
                "reachable": False,
                "method": "unknown",
                "latency_ms": None,
                "packet_loss": None,
                "path_used": None,
                "tunnel_interface": None
            }

            # Check if we have a route
            if destination not in self.active_routes:
                test_result["error"] = "No route to destination"
                return test_result

            route = self.active_routes[destination]
            test_result["path_used"] = route.control_plane_path

            # Test based on route type
            if route.tunnel_interface:
                # Test through tunnel
                test_result["method"] = "tunnel"
                test_result["tunnel_interface"] = route.tunnel_interface

                # Get tunnel peer
                tunnel_peer = None
                for peer_id, tunnel in self.tunnel_orchestrator.tunnels.items():
                    if tunnel.interface_name == route.tunnel_interface:
                        tunnel_peer = peer_id
                        break

                if tunnel_peer:
                    success = await self.tunnel_orchestrator.test_tunnel_connectivity(tunnel_peer)
                    test_result["reachable"] = success
                else:
                    test_result["error"] = "Tunnel peer not found"

            else:
                # Test through BGP/direct routing
                test_result["method"] = "bgp"
                success = await self._test_bgp_connectivity(destination, packet_count)
                test_result["reachable"] = success

            return test_result

        except Exception as e:
            self.logger.error(f"Failed to test forwarding to {destination}: {e}")
            return {"destination": destination, "error": str(e)}

    async def get_forwarding_table(self) -> Dict[str, Dict[str, Any]]:
        """Get the current forwarding table"""
        table = {}
        for dest, entry in self.forwarding_table.items():
            table[dest] = {
                "destination": entry.destination,
                "next_hop": entry.next_hop,
                "interface": entry.interface,
                "tunnel_peer": entry.tunnel_peer,
                "metric": entry.metric,
                "last_updated": entry.last_updated
            }
        return table

    async def get_tunnel_status(self) -> Dict[str, Any]:
        """Get tunnel status information"""
        return await self.tunnel_orchestrator.get_tunnel_statistics()

    async def get_bgp_status(self) -> Dict[str, Any]:
        """Get BGP status information"""
        return await self.bird_manager.get_status()

    async def _evaluate_tunnel_requirement(self, destination: str, next_hop_peer: str,
                                         owl_metrics: Dict[str, float]) -> bool:
        """Determine if a tunnel is required for this route"""
        # Create tunnel if:
        # 1. This is a new route that passes hysteresis check
        # 2. Route quality is significantly better than BGP-only route
        # 3. Direct connectivity to peer is available

        if destination not in self.active_routes:
            # New route - create tunnel if metrics are good
            latency = owl_metrics.get('latency_ms', float('inf'))
            loss = owl_metrics.get('packet_loss_percent', 100)

            # Create tunnel for low-latency, low-loss routes
            return latency < 10.0 and loss < 1.0

        # Existing route - apply hysteresis
        existing_route = self.active_routes[destination]
        existing_metrics = existing_route.owl_metrics

        # Calculate improvement
        latency_improvement = self._calculate_improvement(
            existing_metrics.get('latency_ms', float('inf')),
            owl_metrics.get('latency_ms', float('inf'))
        )

        loss_improvement = self._calculate_improvement(
            existing_metrics.get('packet_loss_percent', 100),
            owl_metrics.get('packet_loss_percent', 100)
        )

        # Require significant improvement to change tunnel status
        return (latency_improvement >= self.hysteresis_threshold or
                loss_improvement >= self.hysteresis_threshold)

    def _calculate_improvement(self, old_value: float, new_value: float) -> float:
        """Calculate percentage improvement between old and new values"""
        if old_value <= 0:
            return 0.0
        return max(0.0, (old_value - new_value) / old_value)

    async def _setup_tunnel_route(self, route: DataPlaneRoute, next_hop_peer: str) -> bool:
        """Set up a route through a WireGuard tunnel"""
        try:
            # Check if peer mapping exists
            if next_hop_peer not in self.peer_mappings:
                self.logger.error(f"No peer mapping for {next_hop_peer}")
                return False

            peer_ip = self.peer_mappings[next_hop_peer]

            # Create tunnel if it doesn't exist
            tunnel = await self.tunnel_orchestrator.get_tunnel_status(next_hop_peer)
            if not tunnel or tunnel.status != "up":
                # We need peer's public key and endpoint for tunnel creation
                # In practice, this would be obtained through key exchange
                self.logger.info(f"Creating tunnel to {next_hop_peer} for route {route.destination}")

                # For now, skip tunnel creation due to missing key exchange
                # In a complete implementation, key exchange would happen here
                return False

            route.tunnel_interface = tunnel.interface_name
            route.bgp_next_hop = tunnel.remote_ip

            self.logger.info(f"Set up tunnel route to {route.destination} via {tunnel.interface_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to setup tunnel route: {e}")
            return False

    async def _setup_bgp_route(self, route: DataPlaneRoute, next_hop_peer: str) -> bool:
        """Set up a route through BGP"""
        try:
            if next_hop_peer not in self.peer_mappings:
                self.logger.error(f"No peer mapping for {next_hop_peer}")
                return False

            route.bgp_next_hop = self.peer_mappings[next_hop_peer]

            self.logger.info(f"Set up BGP route to {route.destination} via {route.bgp_next_hop}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to setup BGP route: {e}")
            return False

    async def _update_forwarding_table(self, route: DataPlaneRoute):
        """Update the forwarding table with a new route"""
        import time

        interface = route.tunnel_interface if route.tunnel_interface else "eth0"
        next_hop = route.bgp_next_hop or route.control_plane_path[1] if len(route.control_plane_path) > 1 else ""

        entry = ForwardingEntry(
            destination=route.destination,
            next_hop=next_hop,
            interface=interface,
            tunnel_peer=route.control_plane_path[1] if len(route.control_plane_path) > 1 else None,
            metric=route.owl_metrics.get('latency_ms', 100.0),
            last_updated=time.time()
        )

        self.forwarding_table[route.destination] = entry

    async def _inject_bgp_route(self, destination: str, owl_metrics: Dict[str, float]):
        """Inject route into BGP with OWL metrics as communities"""
        try:
            # Use BIRD manager to inject route with communities
            next_hop = self.router_id  # Advertise ourselves as next hop

            await self.bird_manager.inject_route(destination, next_hop, owl_metrics)

            self.logger.debug(f"Injected BGP route for {destination} with OWL metrics")

        except Exception as e:
            self.logger.error(f"Failed to inject BGP route for {destination}: {e}")

    async def _cleanup_peer_routes(self, peer_id: str):
        """Clean up all routes associated with a peer"""
        routes_to_remove = []

        for dest, route in self.active_routes.items():
            if len(route.control_plane_path) > 1 and route.control_plane_path[1] == peer_id:
                routes_to_remove.append(dest)

        for dest in routes_to_remove:
            await self.remove_route(dest)

    async def _cleanup_tunnel_route(self, route: DataPlaneRoute):
        """Clean up tunnel-specific route components"""
        if route.tunnel_interface and len(route.control_plane_path) > 1:
            tunnel_peer = route.control_plane_path[1]

            # Check if any other routes use this tunnel
            tunnel_in_use = False
            for dest, other_route in self.active_routes.items():
                if (other_route != route and
                    other_route.tunnel_interface == route.tunnel_interface):
                    tunnel_in_use = True
                    break

            # Remove tunnel if not used by other routes
            if not tunnel_in_use:
                await self.tunnel_orchestrator.remove_tunnel(tunnel_peer)

    async def _test_bgp_connectivity(self, destination: str, packet_count: int) -> bool:
        """Test connectivity through BGP routing"""
        try:
            # Use ping to test connectivity
            process = await asyncio.create_subprocess_exec(
                "ping", "-c", str(packet_count), "-W", "5", destination,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            await process.communicate()
            return process.returncode == 0

        except Exception as e:
            self.logger.error(f"Failed to test BGP connectivity to {destination}: {e}")
            return False

    async def _maintenance_loop(self):
        """Background maintenance for tunnels and routes"""
        while self.running:
            try:
                await asyncio.sleep(self.route_refresh_interval)

                # Clean up idle tunnels
                await self._cleanup_idle_tunnels()

                # Refresh route advertisements
                await self._refresh_bgp_advertisements()

                # Monitor tunnel health
                await self._monitor_tunnel_health()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in maintenance loop: {e}")

    async def _cleanup_idle_tunnels(self):
        """Remove tunnels that haven't been used recently"""
        import time
        current_time = time.time()

        for peer_id, tunnel in list(self.tunnel_orchestrator.tunnels.items()):
            # Check if tunnel is referenced by any active route
            tunnel_in_use = False
            for route in self.active_routes.values():
                if route.tunnel_interface == tunnel.interface_name:
                    tunnel_in_use = True
                    break

            # Remove unused tunnels after timeout
            if not tunnel_in_use:
                # In practice, you'd check last activity time
                self.logger.debug(f"Tunnel to {peer_id} is idle but keeping for now")

    async def _refresh_bgp_advertisements(self):
        """Refresh BGP route advertisements with current metrics"""
        for destination, route in self.active_routes.items():
            if route.active:
                await self._inject_bgp_route(destination, route.owl_metrics)

    async def _monitor_tunnel_health(self):
        """Monitor tunnel health and recover if needed"""
        for peer_id in list(self.tunnel_orchestrator.tunnels.keys()):
            tunnel_status = await self.tunnel_orchestrator.get_tunnel_status(peer_id)
            if tunnel_status and tunnel_status.status == "down":
                self.logger.warning(f"Tunnel to {peer_id} is down - considering recovery")
                # In practice, implement tunnel recovery logic here

    async def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the entire data plane"""
        try:
            bird_status = await self.get_bgp_status()
            tunnel_status = await self.get_tunnel_status()
            forwarding_table = await self.get_forwarding_table()

            return {
                "running": self.running,
                "node_id": self.node_id,
                "router_id": self.router_id,
                "local_asn": self.local_asn,
                "bgp": bird_status,
                "tunnels": tunnel_status,
                "forwarding_table": forwarding_table,
                "active_routes": len(self.active_routes),
                "peer_mappings": self.peer_mappings
            }

        except Exception as e:
            self.logger.error(f"Failed to get comprehensive status: {e}")
            return {"error": str(e), "running": self.running}