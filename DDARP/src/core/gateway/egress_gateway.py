"""
DDARP Egress Gateway

Handles outbound traffic processing, path selection, and traffic optimization
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


class PathSelectionAlgorithm(Enum):
    """Path selection algorithms"""
    SHORTEST_PATH = "shortest_path"
    LOWEST_LATENCY = "lowest_latency"
    HIGHEST_BANDWIDTH = "highest_bandwidth"
    LOAD_BALANCED = "load_balanced"
    COST_OPTIMIZED = "cost_optimized"


@dataclass
class OutboundPath:
    """Represents an outbound path"""
    path_id: str
    destination: str
    next_hops: List[str]
    path_cost: float
    latency_ms: float
    bandwidth_mbps: float
    reliability: float  # 0.0 - 1.0
    last_used: float = field(default_factory=time.time)
    success_count: int = 0
    failure_count: int = 0


@dataclass
class TrafficPolicy:
    """Traffic shaping and QoS policy"""
    name: str
    traffic_types: List[str]
    priority: int  # 1-10, 1 is highest
    bandwidth_limit_mbps: Optional[float] = None
    latency_requirement_ms: Optional[float] = None
    reliability_requirement: Optional[float] = None
    path_selection_algorithm: PathSelectionAlgorithm = PathSelectionAlgorithm.SHORTEST_PATH


class EgressGateway:
    """DDARP Egress Gateway for outbound traffic management"""

    def __init__(self, node_id: str, config: Optional[Dict[str, Any]] = None):
        self.node_id = node_id
        self.config = config or {}
        self.logger = logging.getLogger(f"egress_gateway_{node_id}")

        # Gateway state
        self.running = False
        self.status = ComponentStatus.STOPPED

        # Path management
        self.available_paths: Dict[str, List[OutboundPath]] = {}
        self.path_metrics: Dict[str, Dict[str, Any]] = {}
        self.traffic_policies: Dict[str, TrafficPolicy] = {}

        # Traffic queues and prioritization
        self.priority_queues: Dict[int, asyncio.Queue] = {}
        self.traffic_shapers: Dict[str, Dict[str, Any]] = {}

        # Performance metrics
        self.bytes_sent = 0
        self.packets_sent = 0
        self.failed_transmissions = 0
        self.path_switches = 0

        # Connection pools
        self.connection_pools: Dict[str, List[Any]] = {}

        # Initialize default configuration
        self._init_default_config()

        self.logger.info(f"Egress Gateway initialized for node {node_id}")

    def _init_default_config(self):
        """Initialize default gateway configuration"""
        # Initialize priority queues (1-10, 1 is highest priority)
        for priority in range(1, 11):
            self.priority_queues[priority] = asyncio.Queue(maxsize=500)

        # Default traffic policies
        self.traffic_policies["control_traffic"] = TrafficPolicy(
            name="control_traffic",
            traffic_types=["control", "bgp"],
            priority=1,
            latency_requirement_ms=100,
            reliability_requirement=0.99,
            path_selection_algorithm=PathSelectionAlgorithm.LOWEST_LATENCY
        )

        self.traffic_policies["data_traffic"] = TrafficPolicy(
            name="data_traffic",
            traffic_types=["data"],
            priority=5,
            bandwidth_limit_mbps=100,
            path_selection_algorithm=PathSelectionAlgorithm.HIGHEST_BANDWIDTH
        )

        self.traffic_policies["owl_traffic"] = TrafficPolicy(
            name="owl_traffic",
            traffic_types=["owl"],
            priority=2,
            latency_requirement_ms=50,
            path_selection_algorithm=PathSelectionAlgorithm.LOWEST_LATENCY
        )

        self.traffic_policies["management_traffic"] = TrafficPolicy(
            name="management_traffic",
            traffic_types=["management"],
            priority=8,
            bandwidth_limit_mbps=10,
            path_selection_algorithm=PathSelectionAlgorithm.SHORTEST_PATH
        )

    async def start(self):
        """Start the egress gateway"""
        self.logger.info("Starting Egress Gateway")
        self.status = ComponentStatus.STARTING

        try:
            # Start traffic processing tasks
            await self._start_traffic_processors()

            # Start path monitoring
            asyncio.create_task(self._path_monitoring_loop())

            # Start performance monitoring
            asyncio.create_task(self._performance_monitoring_loop())

            # Start connection pool management
            asyncio.create_task(self._connection_pool_management_loop())

            self.running = True
            self.status = ComponentStatus.HEALTHY

            self.logger.info("Egress Gateway started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start Egress Gateway: {e}")
            self.status = ComponentStatus.ERROR
            raise

    async def stop(self):
        """Stop the egress gateway"""
        self.logger.info("Stopping Egress Gateway")
        self.status = ComponentStatus.STOPPING

        self.running = False

        # Close all connections in pools
        for destination, connections in self.connection_pools.items():
            for conn in connections:
                try:
                    if hasattr(conn, 'close'):
                        conn.close()
                except Exception as e:
                    self.logger.warning(f"Error closing connection to {destination}: {e}")

        self.status = ComponentStatus.STOPPED
        self.logger.info("Egress Gateway stopped")

    async def _start_traffic_processors(self):
        """Start traffic processing tasks for each priority level"""
        for priority in range(1, 11):
            task_name = f"process_priority_{priority}_traffic"
            asyncio.create_task(
                self._process_priority_queue(priority),
                name=task_name
            )
            self.logger.debug(f"Started traffic processor for priority {priority}")

    async def _process_priority_queue(self, priority: int):
        """Process traffic queue for specific priority level"""
        queue = self.priority_queues[priority]

        while self.running:
            try:
                # Get next traffic item with timeout
                try:
                    traffic_item = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Process the traffic item
                await self._process_outbound_traffic(traffic_item)
                queue.task_done()

            except Exception as e:
                self.logger.error(f"Error processing priority {priority} traffic: {e}")
                self.failed_transmissions += 1

    async def _process_outbound_traffic(self, traffic_item: Dict[str, Any]):
        """Process individual outbound traffic item"""
        try:
            destination = traffic_item.get("destination")
            data = traffic_item.get("data", b"")
            traffic_type = traffic_item.get("traffic_type", "data")
            requirements = traffic_item.get("requirements", {})

            # Select best path based on traffic policy
            path = await self._select_optimal_path(destination, traffic_type, requirements)
            if not path:
                self.logger.warning(f"No available path to {destination}")
                self.failed_transmissions += 1
                return

            # Apply traffic shaping
            if not await self._apply_traffic_shaping(traffic_type, len(data)):
                self.logger.debug(f"Traffic shaped for {traffic_type}")
                # Re-queue with delay
                await asyncio.sleep(0.1)
                policy = self._get_traffic_policy(traffic_type)
                priority = policy.priority if policy else 5
                await self.priority_queues[priority].put(traffic_item)
                return

            # Send traffic via selected path
            success = await self._send_via_path(path, data, traffic_item)

            # Update path metrics
            await self._update_path_metrics(path, success, len(data))

            # Update gateway metrics
            if success:
                self.bytes_sent += len(data)
                self.packets_sent += 1
            else:
                self.failed_transmissions += 1

        except Exception as e:
            self.logger.error(f"Error processing outbound traffic: {e}")
            self.failed_transmissions += 1

    async def _select_optimal_path(self, destination: str, traffic_type: str,
                                 requirements: Dict[str, Any]) -> Optional[OutboundPath]:
        """Select optimal path based on traffic policy and requirements"""
        available_paths = self.available_paths.get(destination, [])
        if not available_paths:
            return None

        # Get traffic policy
        policy = self._get_traffic_policy(traffic_type)
        if not policy:
            # Default to shortest path
            return min(available_paths, key=lambda p: p.path_cost)

        # Filter paths based on requirements
        suitable_paths = []
        for path in available_paths:
            if self._path_meets_requirements(path, policy, requirements):
                suitable_paths.append(path)

        if not suitable_paths:
            # Fallback to any available path
            suitable_paths = available_paths

        # Select path based on algorithm
        return self._apply_path_selection_algorithm(suitable_paths, policy.path_selection_algorithm)

    def _path_meets_requirements(self, path: OutboundPath, policy: TrafficPolicy,
                               requirements: Dict[str, Any]) -> bool:
        """Check if path meets policy and explicit requirements"""
        # Check policy requirements
        if policy.latency_requirement_ms and path.latency_ms > policy.latency_requirement_ms:
            return False

        if policy.reliability_requirement and path.reliability < policy.reliability_requirement:
            return False

        # Check explicit requirements
        if "max_latency_ms" in requirements and path.latency_ms > requirements["max_latency_ms"]:
            return False

        if "min_bandwidth_mbps" in requirements and path.bandwidth_mbps < requirements["min_bandwidth_mbps"]:
            return False

        if "min_reliability" in requirements and path.reliability < requirements["min_reliability"]:
            return False

        return True

    def _apply_path_selection_algorithm(self, paths: List[OutboundPath],
                                      algorithm: PathSelectionAlgorithm) -> OutboundPath:
        """Apply path selection algorithm"""
        if algorithm == PathSelectionAlgorithm.SHORTEST_PATH:
            return min(paths, key=lambda p: p.path_cost)

        elif algorithm == PathSelectionAlgorithm.LOWEST_LATENCY:
            return min(paths, key=lambda p: p.latency_ms)

        elif algorithm == PathSelectionAlgorithm.HIGHEST_BANDWIDTH:
            return max(paths, key=lambda p: p.bandwidth_mbps)

        elif algorithm == PathSelectionAlgorithm.LOAD_BALANCED:
            # Simple round-robin based on usage
            return min(paths, key=lambda p: p.success_count + p.failure_count)

        elif algorithm == PathSelectionAlgorithm.COST_OPTIMIZED:
            # Optimize for cost-effectiveness (low cost, reasonable performance)
            return min(paths, key=lambda p: p.path_cost * (1 + p.latency_ms / 1000))

        else:
            return paths[0]  # Default fallback

    def _get_traffic_policy(self, traffic_type: str) -> Optional[TrafficPolicy]:
        """Get traffic policy for traffic type"""
        for policy in self.traffic_policies.values():
            if traffic_type in policy.traffic_types:
                return policy
        return None

    async def _apply_traffic_shaping(self, traffic_type: str, data_size: int) -> bool:
        """Apply traffic shaping rules"""
        policy = self._get_traffic_policy(traffic_type)
        if not policy or not policy.bandwidth_limit_mbps:
            return True

        # Simple token bucket implementation
        if traffic_type not in self.traffic_shapers:
            self.traffic_shapers[traffic_type] = {
                "tokens": policy.bandwidth_limit_mbps * 1024 * 1024,  # Convert to bytes
                "last_refill": time.time(),
                "rate": policy.bandwidth_limit_mbps * 1024 * 1024  # bytes per second
            }

        shaper = self.traffic_shapers[traffic_type]
        current_time = time.time()

        # Refill tokens
        time_passed = current_time - shaper["last_refill"]
        tokens_to_add = time_passed * shaper["rate"]
        shaper["tokens"] = min(shaper["rate"], shaper["tokens"] + tokens_to_add)
        shaper["last_refill"] = current_time

        # Check if we have enough tokens
        if shaper["tokens"] >= data_size:
            shaper["tokens"] -= data_size
            return True
        else:
            return False

    async def _send_via_path(self, path: OutboundPath, data: bytes,
                           traffic_item: Dict[str, Any]) -> bool:
        """Send data via selected path"""
        try:
            # In a real implementation, this would send data via the actual path
            # For now, we'll simulate the transmission
            next_hop = path.next_hops[0] if path.next_hops else None
            if not next_hop:
                return False

            # Simulate network transmission delay based on latency
            await asyncio.sleep(path.latency_ms / 1000)

            # Log the transmission
            self.logger.debug(
                f"Sent {len(data)} bytes to {path.destination} via {next_hop} "
                f"(latency: {path.latency_ms}ms)"
            )

            return True

        except Exception as e:
            self.logger.error(f"Error sending via path {path.path_id}: {e}")
            return False

    async def _update_path_metrics(self, path: OutboundPath, success: bool, bytes_sent: int):
        """Update path performance metrics"""
        if success:
            path.success_count += 1
        else:
            path.failure_count += 1

        path.last_used = time.time()

        # Update reliability
        total_attempts = path.success_count + path.failure_count
        path.reliability = path.success_count / total_attempts if total_attempts > 0 else 1.0

        # Store detailed metrics
        path_id = path.path_id
        if path_id not in self.path_metrics:
            self.path_metrics[path_id] = {
                "bytes_sent": 0,
                "packets_sent": 0,
                "last_updated": time.time()
            }

        metrics = self.path_metrics[path_id]
        metrics["bytes_sent"] += bytes_sent
        metrics["packets_sent"] += 1
        metrics["last_updated"] = time.time()

    async def send_traffic(self, destination: str, data: bytes, traffic_type: str = "data",
                         priority: Optional[int] = None, requirements: Optional[Dict[str, Any]] = None):
        """Send traffic through the egress gateway"""
        try:
            # Determine priority
            if priority is None:
                policy = self._get_traffic_policy(traffic_type)
                priority = policy.priority if policy else 5

            # Create traffic item
            traffic_item = {
                "destination": destination,
                "data": data,
                "traffic_type": traffic_type,
                "requirements": requirements or {},
                "timestamp": time.time()
            }

            # Queue for processing
            queue = self.priority_queues[priority]
            try:
                queue.put_nowait(traffic_item)
                return True
            except asyncio.QueueFull:
                self.logger.warning(f"Priority {priority} queue full")
                return False

        except Exception as e:
            self.logger.error(f"Error queueing traffic: {e}")
            return False

    def update_paths(self, destination: str, paths: List[OutboundPath]):
        """Update available paths for destination"""
        self.available_paths[destination] = paths
        self.logger.debug(f"Updated {len(paths)} paths for destination {destination}")

    def add_traffic_policy(self, policy: TrafficPolicy):
        """Add or update traffic policy"""
        self.traffic_policies[policy.name] = policy
        self.logger.info(f"Added traffic policy: {policy.name}")

    async def _path_monitoring_loop(self):
        """Monitor path performance and availability"""
        while self.running:
            try:
                await self._monitor_path_performance()
                await asyncio.sleep(30)  # Monitor every 30 seconds
            except Exception as e:
                self.logger.error(f"Error in path monitoring loop: {e}")

    async def _monitor_path_performance(self):
        """Monitor and update path performance metrics"""
        current_time = time.time()

        for destination, paths in self.available_paths.items():
            for path in paths:
                # Age-out old metrics
                if current_time - path.last_used > 300:  # 5 minutes
                    # Gradually decrease reliability for unused paths
                    path.reliability *= 0.95

                # Update path metrics based on external measurements
                # This would integrate with the OWL engine and BGP
                pass

    async def _performance_monitoring_loop(self):
        """Monitor gateway performance"""
        while self.running:
            try:
                metrics = self.get_metrics()
                self.logger.debug(f"Egress gateway metrics: {metrics}")
                await asyncio.sleep(60)  # Monitor every minute
            except Exception as e:
                self.logger.error(f"Error in performance monitoring loop: {e}")

    async def _connection_pool_management_loop(self):
        """Manage connection pools"""
        while self.running:
            try:
                await self._cleanup_idle_connections()
                await asyncio.sleep(120)  # Cleanup every 2 minutes
            except Exception as e:
                self.logger.error(f"Error in connection pool management: {e}")

    async def _cleanup_idle_connections(self):
        """Clean up idle connections"""
        # Placeholder for connection pool cleanup
        pass

    def get_metrics(self) -> Dict[str, Any]:
        """Get gateway performance metrics"""
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "bytes_sent": self.bytes_sent,
            "packets_sent": self.packets_sent,
            "failed_transmissions": self.failed_transmissions,
            "path_switches": self.path_switches,
            "available_destinations": len(self.available_paths),
            "total_paths": sum(len(paths) for paths in self.available_paths.values()),
            "queue_sizes": {
                f"priority_{priority}": queue.qsize()
                for priority, queue in self.priority_queues.items()
            },
            "traffic_policies": len(self.traffic_policies),
            "active_shapers": len(self.traffic_shapers)
        }

    def get_status(self) -> ComponentStatus:
        """Get current gateway status"""
        return self.status

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        health_status = {
            "healthy": self.status == ComponentStatus.HEALTHY,
            "status": self.status.value,
            "error_rate": self.failed_transmissions / max(self.packets_sent + self.failed_transmissions, 1),
            "queue_health": all(
                queue.qsize() < queue.maxsize * 0.8
                for queue in self.priority_queues.values()
            ),
            "path_availability": len(self.available_paths) > 0
        }

        return health_status