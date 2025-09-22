import asyncio
import logging
import json
import os
import time
from typing import Dict, Optional, List
from aiohttp import web, ClientSession
from aiohttp.web import Application, Request, Response, json_response
from prometheus_client import CollectorRegistry, Gauge, generate_latest

from .owl_engine import OwlEngine
from .control_plane import ControlPlane, NodeType
from ..networking.data_plane import DataPlaneManager
from .gateway.ingress_gateway import IngressGateway
from .gateway.egress_gateway import EgressGateway
from .control.distributed_control_plane import DistributedControlPlane
from .owl.enhanced_owl_engine import EnhancedOwlEngine
from .networking.wireguard_orchestrator import WireGuardOrchestrator
from .dataplane.vpp_integration import VPPIntegration
from .resource.process_manager import ProcessManager

class CompositeNode:
    def __init__(self, node_id: str, node_type: str, owl_port: int = 8080, api_port: int = 8000, secret_key: str = "default_secret"):
        self.node_id = node_id
        self.node_type = NodeType.BORDER if node_type.lower() == "border" else NodeType.REGULAR
        self.owl_port = owl_port
        self.api_port = api_port

        # Initialize legacy components for backward compatibility
        self.owl_engine = OwlEngine(node_id, owl_port, secret_key)
        self.control_plane = ControlPlane(node_id, self.node_type)

        # Initialize data plane with ASN and router ID from environment or defaults
        local_asn = int(os.getenv('BGP_ASN', str(65000 + hash(node_id) % 1000)))
        router_id = os.getenv('ROUTER_ID', f"10.255.{(hash(node_id) % 254) + 1}.1")
        self.data_plane = DataPlaneManager(node_id, local_asn, router_id)

        # Initialize enhanced components
        self.ingress_gateway = IngressGateway(node_id)
        self.egress_gateway = EgressGateway(node_id)
        self.distributed_control_plane = DistributedControlPlane(node_id, self.node_type)
        self.enhanced_owl_engine = EnhancedOwlEngine(node_id, owl_port)
        self.wireguard_orchestrator = WireGuardOrchestrator(node_id)
        self.vpp_integration = VPPIntegration(node_id)
        self.process_manager = ProcessManager(node_id)

        # Setup Prometheus metrics
        self._setup_prometheus_metrics()

        # Web application
        self.app = web.Application()
        self._setup_routes()

        # State
        self.running = False
        self.logger = logging.getLogger(f"composite_node_{node_id}")

        # Component health status
        self.component_health: Dict[str, bool] = {}

        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def _setup_prometheus_metrics(self):
        """Setup Prometheus metrics for this node."""
        self.prometheus_registry = CollectorRegistry()

        # OWL Metrics
        self.owl_latency_gauge = Gauge(
            'ddarp_owl_latency_ms',
            'OWL latency in milliseconds',
            ['source_node', 'dest_node'],
            registry=self.prometheus_registry
        )

        self.owl_jitter_gauge = Gauge(
            'ddarp_owl_jitter_ms',
            'OWL jitter in milliseconds',
            ['source_node', 'dest_node'],
            registry=self.prometheus_registry
        )

        self.owl_packet_loss_gauge = Gauge(
            'ddarp_owl_packet_loss_percent',
            'OWL packet loss percentage',
            ['source_node', 'dest_node'],
            registry=self.prometheus_registry
        )

        # Node Health Metrics
        self.node_health_gauge = Gauge(
            'ddarp_node_health',
            'Node health status (1=healthy, 0=unhealthy)',
            ['node_id', 'node_type'],
            registry=self.prometheus_registry
        )

        # Topology Metrics
        self.topology_nodes_gauge = Gauge(
            'ddarp_topology_nodes_total',
            'Total number of nodes in topology',
            ['node_id'],
            registry=self.prometheus_registry
        )

        self.topology_edges_gauge = Gauge(
            'ddarp_topology_edges_total',
            'Total number of edges in topology',
            ['node_id'],
            registry=self.prometheus_registry
        )

        # Routing Metrics
        self.routing_table_size_gauge = Gauge(
            'ddarp_routing_table_size',
            'Number of routes in routing table',
            ['node_id'],
            registry=self.prometheus_registry
        )
    
    def _setup_routes(self):
        self.app.router.add_get('/health', self.health_handler)
        self.app.router.add_get('/metrics/owl', self.owl_metrics_handler)
        self.app.router.add_get('/metrics', self.prometheus_metrics_handler)
        self.app.router.add_get('/topology', self.topology_handler)
        self.app.router.add_get('/path/{destination}', self.path_handler)
        self.app.router.add_post('/peers', self.add_peer_handler)
        self.app.router.add_delete('/peers/{peer_id}', self.remove_peer_handler)
        self.app.router.add_get('/routing_table', self.routing_table_handler)
        self.app.router.add_get('/node_info', self.node_info_handler)

        # Data plane API endpoints
        self.app.router.add_get('/bgp/peers', self.bgp_peers_handler)
        self.app.router.add_get('/bgp/routes', self.bgp_routes_handler)
        self.app.router.add_get('/tunnels', self.tunnels_handler)
        self.app.router.add_post('/tunnels/{peer_id}', self.create_tunnel_handler)
        self.app.router.add_delete('/tunnels/{peer_id}', self.delete_tunnel_handler)
        self.app.router.add_get('/forwarding/{destination}', self.test_forwarding_handler)
        self.app.router.add_get('/data_plane/status', self.data_plane_status_handler)
    
    async def health_handler(self, request: Request) -> Response:
        # Check health of all components
        await self._update_component_health()

        overall_status = "healthy" if all(self.component_health.values()) else "degraded"

        return json_response({
            "status": overall_status,
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "components": {
                "owl_engine": self.component_health.get("owl_engine", False),
                "control_plane": self.component_health.get("control_plane", False),
                "enhanced_owl_engine": self.component_health.get("enhanced_owl_engine", False),
                "distributed_control_plane": self.component_health.get("distributed_control_plane", False),
                "ingress_gateway": self.component_health.get("ingress_gateway", False),
                "egress_gateway": self.component_health.get("egress_gateway", False),
                "wireguard_orchestrator": self.component_health.get("wireguard_orchestrator", False),
                "vpp_integration": self.component_health.get("vpp_integration", False),
                "process_manager": self.component_health.get("process_manager", False),
                "data_plane": self.component_health.get("data_plane", False)
            },
            "peer_count": len(self.owl_engine.peers),
            "enhanced_peers": len(self.enhanced_owl_engine.peers) if hasattr(self.enhanced_owl_engine, 'peers') else 0,
            "tunnel_count": len(self.wireguard_orchestrator.tunnels) if hasattr(self.wireguard_orchestrator, 'tunnels') else 0,
            "uptime": "N/A"
        })
    
    async def owl_metrics_handler(self, request: Request) -> Response:
        try:
            metrics = self.owl_engine.get_metrics_matrix()
            return json_response({
                "node_id": self.node_id,
                "metrics_matrix": metrics,
                "timestamp": asyncio.get_event_loop().time()
            })
        except Exception as e:
            self.logger.error(f"Error getting OWL metrics: {e}")
            return json_response(
                {"error": "Failed to retrieve OWL metrics"},
                status=500
            )
    
    async def topology_handler(self, request: Request) -> Response:
        try:
            topology_info = self.control_plane.get_topology_info()
            return json_response({
                "node_id": self.node_id,
                "topology": topology_info,
                "timestamp": asyncio.get_event_loop().time()
            })
        except Exception as e:
            self.logger.error(f"Error getting topology: {e}")
            return json_response(
                {"error": "Failed to retrieve topology"},
                status=500
            )
    
    async def path_handler(self, request: Request) -> Response:
        destination = request.match_info['destination']
        
        try:
            path = self.control_plane.get_path_to_destination(destination)
            next_hop = self.control_plane.get_next_hop(destination)
            reachable = self.control_plane.is_reachable(destination)
            
            return json_response({
                "source": self.node_id,
                "destination": destination,
                "path": path,
                "next_hop": next_hop,
                "reachable": reachable,
                "timestamp": asyncio.get_event_loop().time()
            })
        except Exception as e:
            self.logger.error(f"Error getting path to {destination}: {e}")
            return json_response(
                {"error": f"Failed to compute path to {destination}"},
                status=500
            )
    
    async def add_peer_handler(self, request: Request) -> Response:
        try:
            data = await request.json()
            peer_id = data.get('peer_id')
            peer_ip = data.get('peer_ip')
            peer_type = data.get('peer_type', 'regular')
            
            if not peer_id or not peer_ip:
                return json_response(
                    {"error": "peer_id and peer_ip are required"},
                    status=400
                )
            
            # Add to both OWL engine and control plane
            self.owl_engine.add_peer(peer_id, peer_ip)
            peer_node_type = NodeType.BORDER if peer_type.lower() == "border" else NodeType.REGULAR
            self.control_plane.add_peer(peer_id, peer_node_type, peer_ip)
            
            self.logger.info(f"Added peer {peer_id} ({peer_ip}) as {peer_type}")
            
            return json_response({
                "status": "success",
                "message": f"Added peer {peer_id}",
                "peer_id": peer_id,
                "peer_ip": peer_ip,
                "peer_type": peer_type
            })
            
        except Exception as e:
            self.logger.error(f"Error adding peer: {e}")
            return json_response(
                {"error": "Failed to add peer"},
                status=500
            )
    
    async def remove_peer_handler(self, request: Request) -> Response:
        peer_id = request.match_info['peer_id']
        
        try:
            self.owl_engine.remove_peer(peer_id)
            self.control_plane.remove_peer(peer_id)
            
            self.logger.info(f"Removed peer {peer_id}")
            
            return json_response({
                "status": "success",
                "message": f"Removed peer {peer_id}",
                "peer_id": peer_id
            })
            
        except Exception as e:
            self.logger.error(f"Error removing peer {peer_id}: {e}")
            return json_response(
                {"error": f"Failed to remove peer {peer_id}"},
                status=500
            )
    
    async def routing_table_handler(self, request: Request) -> Response:
        try:
            routing_table = self.control_plane.get_routing_table()
            return json_response({
                "node_id": self.node_id,
                "routing_table": routing_table,
                "timestamp": asyncio.get_event_loop().time()
            })
        except Exception as e:
            self.logger.error(f"Error getting routing table: {e}")
            return json_response(
                {"error": "Failed to retrieve routing table"},
                status=500
            )
    
    async def node_info_handler(self, request: Request) -> Response:
        return json_response({
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "owl_port": self.owl_port,
            "api_port": self.api_port,
            "peers": list(self.owl_engine.peers.keys()),
            "border_nodes": self.control_plane.get_border_nodes()
        })

    # Data Plane API Handlers
    async def bgp_peers_handler(self, request: Request) -> Response:
        """Show BGP peering status"""
        try:
            bgp_status = await self.data_plane.get_bgp_status()
            return json_response({
                "node_id": self.node_id,
                "bgp_peers": bgp_status.get("peers", {}),
                "timestamp": asyncio.get_event_loop().time()
            })
        except Exception as e:
            self.logger.error(f"Error getting BGP peers: {e}")
            return json_response({"error": "Failed to retrieve BGP peers"}, status=500)

    async def bgp_routes_handler(self, request: Request) -> Response:
        """Display BGP routing table"""
        try:
            bgp_status = await self.data_plane.get_bgp_status()
            return json_response({
                "node_id": self.node_id,
                "bgp_routes": bgp_status.get("total_routes", 0),
                "bird_status": bgp_status.get("bird_status", "unknown"),
                "timestamp": asyncio.get_event_loop().time()
            })
        except Exception as e:
            self.logger.error(f"Error getting BGP routes: {e}")
            return json_response({"error": "Failed to retrieve BGP routes"}, status=500)

    async def tunnels_handler(self, request: Request) -> Response:
        """List active WireGuard tunnels"""
        try:
            tunnel_status = await self.data_plane.get_tunnel_status()
            return json_response({
                "node_id": self.node_id,
                "tunnels": tunnel_status,
                "timestamp": asyncio.get_event_loop().time()
            })
        except Exception as e:
            self.logger.error(f"Error getting tunnels: {e}")
            return json_response({"error": "Failed to retrieve tunnels"}, status=500)

    async def create_tunnel_handler(self, request: Request) -> Response:
        """Create tunnel to specific peer"""
        peer_id = request.match_info['peer_id']
        try:
            data = await request.json()
            peer_ip = data.get('peer_ip')
            peer_asn = data.get('peer_asn', 65001)
            peer_public_key = data.get('peer_public_key', '')
            peer_endpoint = data.get('peer_endpoint', f"{peer_ip}:51820")

            success = await self.data_plane.add_peer(
                peer_id, peer_ip, peer_asn, peer_public_key, peer_endpoint
            )

            if success:
                return json_response({
                    "status": "success",
                    "message": f"Created tunnel to {peer_id}",
                    "peer_id": peer_id
                })
            else:
                return json_response({
                    "error": f"Failed to create tunnel to {peer_id}"
                }, status=500)
        except Exception as e:
            self.logger.error(f"Error creating tunnel to {peer_id}: {e}")
            return json_response({
                "error": f"Failed to create tunnel to {peer_id}"
            }, status=500)

    async def delete_tunnel_handler(self, request: Request) -> Response:
        """Delete tunnel to specific peer"""
        peer_id = request.match_info['peer_id']
        try:
            success = await self.data_plane.remove_peer(peer_id)
            if success:
                return json_response({
                    "status": "success",
                    "message": f"Deleted tunnel to {peer_id}",
                    "peer_id": peer_id
                })
            else:
                return json_response({
                    "error": f"Failed to delete tunnel to {peer_id}"
                }, status=500)
        except Exception as e:
            self.logger.error(f"Error deleting tunnel to {peer_id}: {e}")
            return json_response({
                "error": f"Failed to delete tunnel to {peer_id}"
            }, status=500)

    async def test_forwarding_handler(self, request: Request) -> Response:
        """Test data plane forwarding"""
        destination = request.match_info['destination']
        try:
            test_result = await self.data_plane.test_forwarding(destination)
            return json_response({
                "node_id": self.node_id,
                "test_result": test_result,
                "timestamp": asyncio.get_event_loop().time()
            })
        except Exception as e:
            self.logger.error(f"Error testing forwarding to {destination}: {e}")
            return json_response({
                "error": f"Failed to test forwarding to {destination}"
            }, status=500)

    async def data_plane_status_handler(self, request: Request) -> Response:
        """Get comprehensive data plane status"""
        try:
            status = await self.data_plane.get_comprehensive_status()
            return json_response({
                "node_id": self.node_id,
                "data_plane": status,
                "timestamp": asyncio.get_event_loop().time()
            })
        except Exception as e:
            self.logger.error(f"Error getting data plane status: {e}")
            return json_response({
                "error": "Failed to retrieve data plane status"
            }, status=500)

    async def prometheus_metrics_handler(self, request: Request) -> Response:
        """Serve Prometheus-format metrics."""
        try:
            # Update metrics before serving
            self._update_prometheus_metrics()

            # Generate Prometheus format output
            output = generate_latest(self.prometheus_registry)
            return Response(
                body=output,
                content_type='text/plain; version=0.0.4'
            )
        except Exception as e:
            self.logger.error(f"Error generating Prometheus metrics: {e}")
            return Response(
                text=f"Error generating metrics: {e}",
                status=500
            )

    def _update_prometheus_metrics(self):
        """Update Prometheus metrics with current data."""
        try:
            # Update OWL metrics
            owl_metrics = self.owl_engine.get_metrics_matrix()
            for src_node, destinations in owl_metrics.items():
                for dest_node, metrics in destinations.items():
                    self.owl_latency_gauge.labels(
                        source_node=src_node,
                        dest_node=dest_node
                    ).set(metrics.get('latency_ms', 0))

                    self.owl_jitter_gauge.labels(
                        source_node=src_node,
                        dest_node=dest_node
                    ).set(metrics.get('jitter_ms', 0))

                    self.owl_packet_loss_gauge.labels(
                        source_node=src_node,
                        dest_node=dest_node
                    ).set(metrics.get('packet_loss_percent', 0))

            # Update node health
            self.node_health_gauge.labels(
                node_id=self.node_id,
                node_type=self.node_type.value
            ).set(1)  # Always 1 if we can update metrics

            # Update topology metrics
            topology_info = self.control_plane.get_topology_info()
            self.topology_nodes_gauge.labels(node_id=self.node_id).set(
                topology_info.get('node_count', 0)
            )
            self.topology_edges_gauge.labels(node_id=self.node_id).set(
                topology_info.get('edge_count', 0)
            )

            # Update routing table size
            routing_table = self.control_plane.get_routing_table()
            self.routing_table_size_gauge.labels(node_id=self.node_id).set(
                len(routing_table)
            )

        except Exception as e:
            self.logger.error(f"Error updating Prometheus metrics: {e}")

    async def _update_component_health(self):
        """Update health status for all components."""
        try:
            self.component_health["owl_engine"] = getattr(self.owl_engine, 'running', False)
            self.component_health["control_plane"] = getattr(self.control_plane, 'running', False)
            self.component_health["enhanced_owl_engine"] = await self.enhanced_owl_engine.is_healthy()
            self.component_health["distributed_control_plane"] = await self.distributed_control_plane.is_healthy()
            self.component_health["ingress_gateway"] = await self.ingress_gateway.is_healthy()
            self.component_health["egress_gateway"] = await self.egress_gateway.is_healthy()
            self.component_health["wireguard_orchestrator"] = await self.wireguard_orchestrator.is_healthy()
            self.component_health["vpp_integration"] = await self.vpp_integration.is_healthy()
            self.component_health["process_manager"] = await self.process_manager.is_healthy()
            self.component_health["data_plane"] = True  # Simplified for now
        except Exception as e:
            self.logger.error(f"Error updating component health: {e}")

    async def start(self):
        self.logger.info(f"Starting Enhanced Composite Node {self.node_id}")

        # Set running flag first so background tasks can start
        self.running = True

        # Start process manager first for resource isolation
        try:
            await self.process_manager.start()
            self.logger.info("Process manager started successfully")
        except Exception as e:
            self.logger.warning(f"Process manager failed to start: {e}")

        # Start VPP integration
        try:
            await self.vpp_integration.start()
            self.logger.info("VPP integration started successfully")
        except Exception as e:
            self.logger.warning(f"VPP integration failed to start: {e}")

        # Start WireGuard orchestrator
        try:
            await self.wireguard_orchestrator.start()
            self.logger.info("WireGuard orchestrator started successfully")
        except Exception as e:
            self.logger.warning(f"WireGuard orchestrator failed to start: {e}")

        # Start enhanced OWL engine
        try:
            await self.enhanced_owl_engine.start()
            self.logger.info("Enhanced OWL engine started successfully")
        except Exception as e:
            self.logger.warning(f"Enhanced OWL engine failed to start: {e}")

        # Start distributed control plane
        try:
            await self.distributed_control_plane.start()
            self.logger.info("Distributed control plane started successfully")
        except Exception as e:
            self.logger.warning(f"Distributed control plane failed to start: {e}")

        # Start gateways
        try:
            await self.ingress_gateway.start()
            self.logger.info("Ingress gateway started successfully")
        except Exception as e:
            self.logger.warning(f"Ingress gateway failed to start: {e}")

        try:
            await self.egress_gateway.start()
            self.logger.info("Egress gateway started successfully")
        except Exception as e:
            self.logger.warning(f"Egress gateway failed to start: {e}")

        # Start legacy components for backward compatibility
        await self.owl_engine.start()
        await self.control_plane.start()

        # Start data plane
        try:
            await self.data_plane.start()
            self.logger.info("Data plane started successfully")
        except Exception as e:
            self.logger.warning(f"Data plane failed to start: {e}")
            self.logger.info("Continuing without data plane functionality")

        # Start background loops
        self.logger.info("Starting background loops")
        asyncio.create_task(self._metrics_update_loop())
        asyncio.create_task(self._data_plane_integration_loop())
        asyncio.create_task(self._enhanced_component_coordination_loop())
        asyncio.create_task(self._health_monitoring_loop())

        # Start web server
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', self.api_port)
        await site.start()

        self.logger.info(f"Enhanced Composite Node {self.node_id} started successfully")
        self.logger.info(f"OWL Engine listening on UDP port {self.owl_port}")
        self.logger.info(f"REST API listening on HTTP port {self.api_port}")
        self.logger.info("All enhanced components initialized")
    
    async def stop(self):
        self.logger.info(f"Stopping Enhanced Composite Node {self.node_id}")

        self.running = False

        # Stop enhanced components
        try:
            await self.ingress_gateway.stop()
            await self.egress_gateway.stop()
            await self.distributed_control_plane.stop()
            await self.enhanced_owl_engine.stop()
            await self.wireguard_orchestrator.stop()
            await self.vpp_integration.stop()
            await self.process_manager.stop()
        except Exception as e:
            self.logger.error(f"Error stopping enhanced components: {e}")

        # Stop legacy components
        await self.owl_engine.stop()
        await self.control_plane.stop()

        # Stop data plane
        try:
            await self.data_plane.stop()
        except Exception as e:
            self.logger.error(f"Error stopping data plane: {e}")

        self.logger.info(f"Enhanced Composite Node {self.node_id} stopped")
    
    async def _metrics_update_loop(self):
        self.logger.info("Metrics update loop started")
        while self.running:
            try:
                # Get latest OWL metrics and update control plane topology
                owl_metrics = self.owl_engine.get_metrics_matrix()
                self.logger.info(f"Metrics update loop iteration - running: {self.running}")
                self.logger.info(f"Updating topology with metrics: {len(owl_metrics)} sources - {list(owl_metrics.keys())}")

                # Debug: show sample metrics
                if owl_metrics:
                    for src, dests in owl_metrics.items():
                        self.logger.info(f"  Source {src} has {len(dests)} destinations: {list(dests.keys())}")
                        for dest, metrics in dests.items():
                            latency = metrics.get('latency_ms', 'none')
                            self.logger.info(f"    -> {dest}: latency={latency}ms")

                self.control_plane.update_topology(owl_metrics)
                self.logger.info("Topology update completed")
            except Exception as e:
                self.logger.error(f"Error updating topology with OWL metrics: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")

            await asyncio.sleep(5.0)  # Update every 5 seconds

    async def _data_plane_integration_loop(self):
        """Integrate control plane decisions with data plane routing"""
        self.logger.info("Data plane integration loop started")
        while self.running:
            try:
                # Get current routing table from control plane
                routing_table = self.control_plane.get_routing_table()

                # Get current OWL metrics
                owl_metrics = self.owl_engine.get_metrics_matrix()

                # Update data plane routes based on control plane decisions
                for destination, route_info in routing_table.items():
                    if destination in self.owl_engine.peers:
                        continue  # Skip direct peers

                    path = route_info.get('path', [])
                    if len(path) >= 2:
                        next_hop = path[1]

                        # Get metrics for this destination
                        dest_metrics = {}
                        if self.node_id in owl_metrics and destination in owl_metrics[self.node_id]:
                            dest_metrics = owl_metrics[self.node_id][destination]

                        # Update route in data plane
                        await self.data_plane.update_route(destination, path, dest_metrics)

                self.logger.debug(f"Updated {len(routing_table)} routes in data plane")

            except Exception as e:
                self.logger.error(f"Error in data plane integration loop: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")

            await asyncio.sleep(10.0)  # Update every 10 seconds

    async def _enhanced_component_coordination_loop(self):
        """Coordinate between enhanced components for optimal performance"""
        self.logger.info("Enhanced component coordination loop started")
        while self.running:
            try:
                # Get current network state from enhanced OWL
                owl_matrix = await self.enhanced_owl_engine.get_enhanced_metrics()

                # Update distributed control plane with enhanced metrics
                await self.distributed_control_plane.update_network_state(owl_matrix)

                # Get optimized paths from distributed control plane
                routing_decisions = await self.distributed_control_plane.get_routing_decisions()

                # Update gateways with routing decisions
                await self.ingress_gateway.update_routing_rules(routing_decisions)
                await self.egress_gateway.update_path_selection(routing_decisions)

                # Update WireGuard tunnels based on active paths
                active_peers = set()
                for decision in routing_decisions.values():
                    if 'next_hop' in decision:
                        active_peers.add(decision['next_hop'])

                await self.wireguard_orchestrator.optimize_tunnels(active_peers)

                self.logger.debug("Enhanced component coordination completed")

            except Exception as e:
                self.logger.error(f"Error in enhanced component coordination: {e}")

            await asyncio.sleep(15.0)  # Coordinate every 15 seconds

    async def _health_monitoring_loop(self):
        """Monitor health of all components and take corrective actions"""
        self.logger.info("Health monitoring loop started")
        while self.running:
            try:
                await self._update_component_health()

                # Check for unhealthy components and attempt recovery
                for component_name, is_healthy in self.component_health.items():
                    if not is_healthy:
                        self.logger.warning(f"Component {component_name} is unhealthy, attempting recovery")
                        await self._attempt_component_recovery(component_name)

                # Log overall health status periodically
                healthy_count = sum(1 for health in self.component_health.values() if health)
                total_count = len(self.component_health)
                self.logger.info(f"Component health: {healthy_count}/{total_count} components healthy")

            except Exception as e:
                self.logger.error(f"Error in health monitoring loop: {e}")

            await asyncio.sleep(30.0)  # Check health every 30 seconds

    async def _attempt_component_recovery(self, component_name: str):
        """Attempt to recover a failed component"""
        try:
            component = getattr(self, component_name, None)
            if component and hasattr(component, 'restart'):
                self.logger.info(f"Attempting to restart {component_name}")
                await component.restart()
            elif component and hasattr(component, 'start'):
                self.logger.info(f"Attempting to start {component_name}")
                await component.start()
        except Exception as e:
            self.logger.error(f"Failed to recover component {component_name}: {e}")

async def create_node_from_env():
    node_id = os.getenv('NODE_ID', 'node1')
    node_type = os.getenv('NODE_TYPE', 'regular')
    owl_port = int(os.getenv('OWL_PORT', '8080'))
    api_port = int(os.getenv('API_PORT', '8000'))
    secret_key = os.getenv('SECRET_KEY', 'ddarp_secret_key_2024')
    
    node = CompositeNode(node_id, node_type, owl_port, api_port, secret_key)
    return node

async def main():
    node = await create_node_from_env()
    
    try:
        await node.start()
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        await node.stop()

if __name__ == "__main__":
    asyncio.run(main())