"""
DDARP Ingress Gateway

Handles incoming traffic processing, load balancing, and traffic shaping
for the DDARP composite node architecture.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import socket

from ..monitoring.enhanced_prometheus_exporter import ComponentStatus


class TrafficType(Enum):
    """Types of traffic handled by the gateway"""
    CONTROL = "control"
    DATA = "data"
    OWL = "owl"
    BGP = "bgp"
    MANAGEMENT = "management"


@dataclass
class TrafficFlow:
    """Represents a traffic flow through the gateway"""
    flow_id: str
    source_addr: str
    dest_addr: str
    traffic_type: TrafficType
    protocol: str
    port: int
    bytes_processed: int = 0
    packets_processed: int = 0
    start_time: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    priority: int = 5  # 1-10, 1 is highest priority


@dataclass
class LoadBalancingRule:
    """Load balancing configuration for traffic flows"""
    name: str
    traffic_type: TrafficType
    algorithm: str  # "round_robin", "least_connections", "weighted"
    backend_servers: List[str]
    weights: Optional[List[int]] = None
    health_check_enabled: bool = True


class IngressGateway:
    """DDARP Ingress Gateway for traffic management"""

    def __init__(self, node_id: str, config: Optional[Dict[str, Any]] = None):
        self.node_id = node_id
        self.config = config or {}
        self.logger = logging.getLogger(f"ingress_gateway_{node_id}")

        # Gateway state
        self.running = False
        self.status = ComponentStatus.STOPPED

        # Traffic management
        self.active_flows: Dict[str, TrafficFlow] = {}
        self.load_balancing_rules: Dict[str, LoadBalancingRule] = {}
        self.backend_health: Dict[str, bool] = {}

        # Traffic shaping
        self.rate_limits: Dict[str, Dict[str, Any]] = {}
        self.traffic_queues: Dict[TrafficType, asyncio.Queue] = {}

        # Metrics
        self.bytes_processed = 0
        self.packets_processed = 0
        self.connections_active = 0
        self.errors_count = 0

        # Listeners
        self.listeners: Dict[str, asyncio.Server] = {}

        # Initialize default configuration
        self._init_default_config()

        self.logger.info(f"Ingress Gateway initialized for node {node_id}")

    def _init_default_config(self):
        """Initialize default gateway configuration"""
        # Default traffic queues
        for traffic_type in TrafficType:
            self.traffic_queues[traffic_type] = asyncio.Queue(maxsize=1000)

        # Default load balancing rules
        self.load_balancing_rules["owl_traffic"] = LoadBalancingRule(
            name="owl_traffic",
            traffic_type=TrafficType.OWL,
            algorithm="round_robin",
            backend_servers=["localhost:8080"]
        )

        self.load_balancing_rules["control_traffic"] = LoadBalancingRule(
            name="control_traffic",
            traffic_type=TrafficType.CONTROL,
            algorithm="least_connections",
            backend_servers=["localhost:8000"]
        )

        # Default rate limits (bytes per second)
        self.rate_limits = {
            "control": {"rate": 1024 * 1024, "burst": 2048 * 1024},  # 1MB/s, 2MB burst
            "data": {"rate": 10 * 1024 * 1024, "burst": 20 * 1024 * 1024},  # 10MB/s, 20MB burst
            "owl": {"rate": 512 * 1024, "burst": 1024 * 1024},  # 512KB/s, 1MB burst
            "management": {"rate": 256 * 1024, "burst": 512 * 1024}  # 256KB/s, 512KB burst
        }

    async def start(self):
        """Start the ingress gateway"""
        self.logger.info("Starting Ingress Gateway")
        self.status = ComponentStatus.STARTING

        try:
            # Start traffic processing tasks
            await self._start_traffic_processors()

            # Start health monitoring
            asyncio.create_task(self._health_monitor_loop())

            # Start flow cleanup
            asyncio.create_task(self._flow_cleanup_loop())

            # Start metrics collection
            asyncio.create_task(self._metrics_collection_loop())

            self.running = True
            self.status = ComponentStatus.HEALTHY

            self.logger.info("Ingress Gateway started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start Ingress Gateway: {e}")
            self.status = ComponentStatus.ERROR
            raise

    async def stop(self):
        """Stop the ingress gateway"""
        self.logger.info("Stopping Ingress Gateway")
        self.status = ComponentStatus.STOPPING

        self.running = False

        # Stop all listeners
        for name, server in self.listeners.items():
            self.logger.info(f"Stopping listener {name}")
            server.close()
            await server.wait_closed()

        self.status = ComponentStatus.STOPPED
        self.logger.info("Ingress Gateway stopped")

    async def _start_traffic_processors(self):
        """Start traffic processing tasks for each traffic type"""
        for traffic_type in TrafficType:
            task_name = f"process_{traffic_type.value}_traffic"
            asyncio.create_task(
                self._process_traffic_queue(traffic_type),
                name=task_name
            )
            self.logger.debug(f"Started traffic processor for {traffic_type.value}")

    async def _process_traffic_queue(self, traffic_type: TrafficType):
        """Process traffic queue for specific traffic type"""
        queue = self.traffic_queues[traffic_type]

        while self.running:
            try:
                # Get next traffic item with timeout
                try:
                    traffic_item = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Process the traffic item
                await self._process_traffic_item(traffic_item, traffic_type)
                queue.task_done()

            except Exception as e:
                self.logger.error(f"Error processing {traffic_type.value} traffic: {e}")
                self.errors_count += 1

    async def _process_traffic_item(self, traffic_item: Dict[str, Any], traffic_type: TrafficType):
        """Process individual traffic item"""
        try:
            flow_id = traffic_item.get("flow_id")
            data = traffic_item.get("data", b"")
            source_addr = traffic_item.get("source_addr")

            # Update flow statistics
            if flow_id in self.active_flows:
                flow = self.active_flows[flow_id]
                flow.bytes_processed += len(data)
                flow.packets_processed += 1
                flow.last_seen = time.time()

            # Apply rate limiting
            if not await self._check_rate_limit(traffic_type, len(data)):
                self.logger.warning(f"Rate limit exceeded for {traffic_type.value} traffic")
                return

            # Load balance the traffic
            backend = await self._select_backend(traffic_type)
            if backend:
                await self._forward_traffic(traffic_item, backend)

            # Update metrics
            self.bytes_processed += len(data)
            self.packets_processed += 1

        except Exception as e:
            self.logger.error(f"Error processing traffic item: {e}")
            self.errors_count += 1

    async def _check_rate_limit(self, traffic_type: TrafficType, data_size: int) -> bool:
        """Check if traffic is within rate limits"""
        rate_limit_key = traffic_type.value
        if rate_limit_key not in self.rate_limits:
            return True

        # Simple rate limiting implementation
        # In production, this would use a token bucket or sliding window
        rate_limit = self.rate_limits[rate_limit_key]

        # For now, always allow (placeholder for actual rate limiting logic)
        return True

    async def _select_backend(self, traffic_type: TrafficType) -> Optional[str]:
        """Select backend server using load balancing algorithm"""
        rule_name = f"{traffic_type.value}_traffic"
        if rule_name not in self.load_balancing_rules:
            return None

        rule = self.load_balancing_rules[rule_name]
        healthy_backends = [
            backend for backend in rule.backend_servers
            if self.backend_health.get(backend, True)
        ]

        if not healthy_backends:
            return None

        # Simple round-robin for now
        # In production, this would implement various algorithms
        backend_index = self.packets_processed % len(healthy_backends)
        return healthy_backends[backend_index]

    async def _forward_traffic(self, traffic_item: Dict[str, Any], backend: str):
        """Forward traffic to selected backend"""
        try:
            # Extract backend address and port
            if ":" in backend:
                host, port = backend.split(":", 1)
                port = int(port)
            else:
                host = backend
                port = 8080  # Default port

            # In a real implementation, this would maintain persistent connections
            # or use a connection pool. For now, we'll just log the forwarding.
            self.logger.debug(f"Forwarding traffic to {host}:{port}")

        except Exception as e:
            self.logger.error(f"Error forwarding traffic to {backend}: {e}")

    async def process_inbound_traffic(self, data: bytes, source_addr: str,
                                    traffic_type: TrafficType, protocol: str = "UDP",
                                    port: int = 0) -> bool:
        """Process inbound traffic through the gateway"""
        try:
            # Create or update flow
            flow_id = f"{source_addr}:{protocol}:{port}"

            if flow_id not in self.active_flows:
                self.active_flows[flow_id] = TrafficFlow(
                    flow_id=flow_id,
                    source_addr=source_addr,
                    dest_addr=self.node_id,
                    traffic_type=traffic_type,
                    protocol=protocol,
                    port=port
                )
                self.connections_active += 1

            # Queue traffic for processing
            traffic_item = {
                "flow_id": flow_id,
                "data": data,
                "source_addr": source_addr,
                "protocol": protocol,
                "port": port,
                "timestamp": time.time()
            }

            queue = self.traffic_queues[traffic_type]
            try:
                queue.put_nowait(traffic_item)
                return True
            except asyncio.QueueFull:
                self.logger.warning(f"Traffic queue full for {traffic_type.value}")
                return False

        except Exception as e:
            self.logger.error(f"Error processing inbound traffic: {e}")
            return False

    async def _health_monitor_loop(self):
        """Monitor backend health"""
        while self.running:
            try:
                await self._check_backend_health()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                self.logger.error(f"Error in health monitor loop: {e}")

    async def _check_backend_health(self):
        """Check health of all backend servers"""
        for rule in self.load_balancing_rules.values():
            for backend in rule.backend_servers:
                if rule.health_check_enabled:
                    healthy = await self._ping_backend(backend)
                    self.backend_health[backend] = healthy

                    if not healthy:
                        self.logger.warning(f"Backend {backend} is unhealthy")
                else:
                    self.backend_health[backend] = True

    async def _ping_backend(self, backend: str) -> bool:
        """Ping backend to check health"""
        try:
            if ":" in backend:
                host, port = backend.split(":", 1)
                port = int(port)
            else:
                host = backend
                port = 80

            # Simple TCP connection test
            future = asyncio.open_connection(host, port)
            try:
                reader, writer = await asyncio.wait_for(future, timeout=5.0)
                writer.close()
                await writer.wait_closed()
                return True
            except asyncio.TimeoutError:
                return False

        except Exception:
            return False

    async def _flow_cleanup_loop(self):
        """Clean up inactive flows"""
        while self.running:
            try:
                current_time = time.time()
                inactive_flows = []

                for flow_id, flow in self.active_flows.items():
                    if current_time - flow.last_seen > 300:  # 5 minutes
                        inactive_flows.append(flow_id)

                for flow_id in inactive_flows:
                    del self.active_flows[flow_id]
                    self.connections_active -= 1

                if inactive_flows:
                    self.logger.debug(f"Cleaned up {len(inactive_flows)} inactive flows")

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                self.logger.error(f"Error in flow cleanup loop: {e}")

    async def _metrics_collection_loop(self):
        """Collect and log gateway metrics"""
        while self.running:
            try:
                metrics = self.get_metrics()
                self.logger.debug(f"Gateway metrics: {metrics}")
                await asyncio.sleep(30)  # Collect every 30 seconds
            except Exception as e:
                self.logger.error(f"Error in metrics collection loop: {e}")

    def add_load_balancing_rule(self, rule: LoadBalancingRule):
        """Add or update load balancing rule"""
        self.load_balancing_rules[rule.name] = rule
        self.logger.info(f"Added load balancing rule: {rule.name}")

    def update_rate_limits(self, traffic_type: str, rate: int, burst: int):
        """Update rate limits for traffic type"""
        self.rate_limits[traffic_type] = {"rate": rate, "burst": burst}
        self.logger.info(f"Updated rate limits for {traffic_type}: {rate} bps, {burst} burst")

    def get_metrics(self) -> Dict[str, Any]:
        """Get gateway performance metrics"""
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "bytes_processed": self.bytes_processed,
            "packets_processed": self.packets_processed,
            "connections_active": self.connections_active,
            "errors_count": self.errors_count,
            "active_flows": len(self.active_flows),
            "queue_sizes": {
                traffic_type.value: queue.qsize()
                for traffic_type, queue in self.traffic_queues.items()
            },
            "backend_health": self.backend_health.copy(),
            "load_balancing_rules": len(self.load_balancing_rules)
        }

    def get_status(self) -> ComponentStatus:
        """Get current gateway status"""
        return self.status

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        health_status = {
            "healthy": self.status == ComponentStatus.HEALTHY,
            "status": self.status.value,
            "uptime": time.time() - getattr(self, '_start_time', time.time()),
            "error_rate": self.errors_count / max(self.packets_processed, 1),
            "queue_health": all(
                queue.qsize() < queue.maxsize * 0.8
                for queue in self.traffic_queues.values()
            )
        }

        return health_status