"""
Enhanced Prometheus Metrics Exporter for DDARP

Provides comprehensive metrics collection and export for all DDARP components
including OWL measurements, BGP operations, tunnel management, algorithm
performance, and system health monitoring.
"""

import asyncio
import logging
import time
import psutil
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from prometheus_client import (
    CollectorRegistry, Counter, Gauge, Histogram, Info, Summary,
    generate_latest, CONTENT_TYPE_LATEST
)


@dataclass
class MetricLabels:
    """Standard labels for DDARP metrics"""
    node_id: str
    peer_id: Optional[str] = None
    algorithm_type: Optional[str] = None
    tunnel_id: Optional[str] = None
    bgp_peer: Optional[str] = None


class DDARPPrometheusExporter:
    """Enhanced Prometheus metrics exporter for DDARP system"""

    def __init__(self, node_id: str, registry: Optional[CollectorRegistry] = None):
        self.node_id = node_id
        self.registry = registry or CollectorRegistry()
        self.logger = logging.getLogger(f"prometheus_exporter_{node_id}")

        # Initialize all metrics
        self._init_owl_metrics()
        self._init_bgp_metrics()
        self._init_tunnel_metrics()
        self._init_algorithm_metrics()
        self._init_system_metrics()
        self._init_info_metrics()

    def _init_owl_metrics(self):
        """Initialize OWL (One-Way Latency) metrics"""

        # Latency metrics with histogram for percentiles
        self.owl_latency = Histogram(
            'ddarp_latency_milliseconds',
            'OWL latency measurements in milliseconds',
            ['node_id', 'peer_id'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, float('inf')],
            registry=self.registry
        )

        # Current latency gauge for real-time monitoring
        self.owl_latency_current = Gauge(
            'ddarp_latency_current_milliseconds',
            'Current OWL latency in milliseconds',
            ['node_id', 'peer_id'],
            registry=self.registry
        )

        # Jitter metrics
        self.owl_jitter = Histogram(
            'ddarp_jitter_milliseconds',
            'OWL jitter measurements in milliseconds',
            ['node_id', 'peer_id'],
            buckets=[0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float('inf')],
            registry=self.registry
        )

        self.owl_jitter_current = Gauge(
            'ddarp_jitter_current_milliseconds',
            'Current OWL jitter in milliseconds',
            ['node_id', 'peer_id'],
            registry=self.registry
        )

        # Packet loss metrics
        self.owl_packet_loss = Gauge(
            'ddarp_packet_loss_ratio',
            'Packet loss ratio (0.0 to 1.0)',
            ['node_id', 'peer_id'],
            registry=self.registry
        )

        # Measurement statistics
        self.owl_measurements_total = Counter(
            'ddarp_owl_measurements_total',
            'Total number of OWL measurements',
            ['node_id', 'peer_id', 'status'],
            registry=self.registry
        )

        # Measurement quality
        self.owl_measurement_quality = Gauge(
            'ddarp_owl_measurement_quality_score',
            'OWL measurement quality score (0.0 to 1.0)',
            ['node_id', 'peer_id'],
            registry=self.registry
        )

    def _init_bgp_metrics(self):
        """Initialize BGP metrics"""

        # BGP session status
        self.bgp_sessions_up = Gauge(
            'ddarp_bgp_sessions_up',
            'Number of BGP sessions in established state',
            ['node_id'],
            registry=self.registry
        )

        # BGP session state per peer
        self.bgp_session_state = Gauge(
            'ddarp_bgp_session_state',
            'BGP session state (0=idle, 1=connect, 2=established)',
            ['node_id', 'bgp_peer', 'peer_asn'],
            registry=self.registry
        )

        # Routes advertised and received
        self.bgp_routes_advertised = Gauge(
            'ddarp_bgp_routes_advertised',
            'Number of BGP routes advertised to peer',
            ['node_id', 'bgp_peer'],
            registry=self.registry
        )

        self.bgp_routes_received = Gauge(
            'ddarp_bgp_routes_received',
            'Number of BGP routes received from peer',
            ['node_id', 'bgp_peer'],
            registry=self.registry
        )

        # BGP convergence time
        self.bgp_convergence_duration = Histogram(
            'ddarp_bgp_convergence_seconds',
            'BGP convergence time in seconds',
            ['node_id', 'bgp_peer'],
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, float('inf')],
            registry=self.registry
        )

        # Community metrics
        self.bgp_communities_sent = Counter(
            'ddarp_bgp_communities_sent_total',
            'Total BGP communities sent',
            ['node_id', 'community_type'],
            registry=self.registry
        )

        # Route updates
        self.bgp_route_updates = Counter(
            'ddarp_bgp_route_updates_total',
            'Total BGP route updates',
            ['node_id', 'bgp_peer', 'update_type'],
            registry=self.registry
        )

    def _init_tunnel_metrics(self):
        """Initialize WireGuard tunnel metrics"""

        # Tunnel status
        self.tunnel_status = Gauge(
            'ddarp_tunnel_status',
            'Tunnel status (0=down, 1=up, 2=error)',
            ['node_id', 'tunnel_id', 'peer_id'],
            registry=self.registry
        )

        # Tunnel throughput
        self.tunnel_throughput_bytes = Gauge(
            'ddarp_tunnel_throughput_bytes',
            'Tunnel throughput in bytes per second',
            ['node_id', 'tunnel_id', 'direction'],
            registry=self.registry
        )

        # Tunnel setup duration
        self.tunnel_setup_duration = Histogram(
            'ddarp_tunnel_setup_duration_seconds',
            'Time to establish tunnel in seconds',
            ['node_id', 'tunnel_id'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, float('inf')],
            registry=self.registry
        )

        # Tunnel data transfer
        self.tunnel_bytes_transferred = Counter(
            'ddarp_tunnel_bytes_total',
            'Total bytes transferred through tunnel',
            ['node_id', 'tunnel_id', 'direction'],
            registry=self.registry
        )

        # Tunnel handshakes
        self.tunnel_handshakes = Counter(
            'ddarp_tunnel_handshakes_total',
            'Total tunnel handshakes',
            ['node_id', 'tunnel_id', 'status'],
            registry=self.registry
        )

        # Active tunnels
        self.tunnels_active = Gauge(
            'ddarp_tunnels_active',
            'Number of active tunnels',
            ['node_id'],
            registry=self.registry
        )

    def _init_algorithm_metrics(self):
        """Initialize routing algorithm metrics"""

        # Path computation duration
        self.path_computation_duration = Histogram(
            'ddarp_path_computation_duration_seconds',
            'Time to compute paths in seconds',
            ['node_id', 'algorithm_type'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, float('inf')],
            registry=self.registry
        )

        # Path changes
        self.path_changes_total = Counter(
            'ddarp_path_changes_total',
            'Total number of path changes',
            ['node_id', 'destination_id', 'change_reason'],
            registry=self.registry
        )

        # Hysteresis events
        self.hysteresis_events = Counter(
            'ddarp_hysteresis_events_total',
            'Total hysteresis events',
            ['node_id', 'event_type'],
            registry=self.registry
        )

        # Topology size
        self.topology_nodes = Gauge(
            'ddarp_topology_nodes',
            'Number of nodes in topology',
            ['node_id'],
            registry=self.registry
        )

        self.topology_edges = Gauge(
            'ddarp_topology_edges',
            'Number of edges in topology',
            ['node_id'],
            registry=self.registry
        )

        # Routing table size
        self.routing_table_size = Gauge(
            'ddarp_routing_table_entries',
            'Number of entries in routing table',
            ['node_id'],
            registry=self.registry
        )

        # Algorithm selection frequency
        self.algorithm_selection = Counter(
            'ddarp_algorithm_selection_total',
            'Algorithm selection frequency',
            ['node_id', 'algorithm_type'],
            registry=self.registry
        )

    def _init_system_metrics(self):
        """Initialize system health metrics"""

        # CPU usage
        self.cpu_usage_percent = Gauge(
            'ddarp_cpu_usage_percent',
            'CPU usage percentage',
            ['node_id'],
            registry=self.registry
        )

        # Memory usage
        self.memory_usage_bytes = Gauge(
            'ddarp_memory_usage_bytes',
            'Memory usage in bytes',
            ['node_id', 'memory_type'],
            registry=self.registry
        )

        # Disk usage
        self.disk_usage_bytes = Gauge(
            'ddarp_disk_usage_bytes',
            'Disk usage in bytes',
            ['node_id', 'mount_point'],
            registry=self.registry
        )

        # Network interface statistics
        self.network_bytes = Counter(
            'ddarp_network_bytes_total',
            'Network bytes transferred',
            ['node_id', 'interface', 'direction'],
            registry=self.registry
        )

        # Process information
        self.process_threads = Gauge(
            'ddarp_process_threads',
            'Number of process threads',
            ['node_id'],
            registry=self.registry
        )

        self.process_fds = Gauge(
            'ddarp_process_file_descriptors',
            'Number of open file descriptors',
            ['node_id'],
            registry=self.registry
        )

        # Container health
        self.container_health = Gauge(
            'ddarp_container_health',
            'Container health status (0=unhealthy, 1=healthy)',
            ['node_id', 'container_name'],
            registry=self.registry
        )

    def _init_info_metrics(self):
        """Initialize info metrics"""

        # Version information
        self.version_info = Info(
            'ddarp_version_info',
            'DDARP version information',
            registry=self.registry
        )

        # Node information
        self.node_info = Info(
            'ddarp_node_info',
            'DDARP node information',
            registry=self.registry
        )

    # OWL Metrics Update Methods
    def update_owl_metrics(self, peer_id: str, latency_ms: float, jitter_ms: float,
                          packet_loss_ratio: float, measurement_quality: float = 1.0):
        """Update OWL measurement metrics"""
        labels = [self.node_id, peer_id]

        # Update histograms and current values
        self.owl_latency.labels(*labels).observe(latency_ms)
        self.owl_latency_current.labels(*labels).set(latency_ms)

        self.owl_jitter.labels(*labels).observe(jitter_ms)
        self.owl_jitter_current.labels(*labels).set(jitter_ms)

        self.owl_packet_loss.labels(*labels).set(packet_loss_ratio)
        self.owl_measurement_quality.labels(*labels).set(measurement_quality)

        # Update measurement counters
        status = "success" if measurement_quality > 0.8 else "degraded"
        self.owl_measurements_total.labels(self.node_id, peer_id, status).inc()

    def record_owl_measurement_failure(self, peer_id: str):
        """Record failed OWL measurement"""
        self.owl_measurements_total.labels(self.node_id, peer_id, "failed").inc()

    # BGP Metrics Update Methods
    def update_bgp_session_state(self, peer_id: str, peer_asn: str, state: str,
                                routes_sent: int = 0, routes_received: int = 0):
        """Update BGP session metrics"""
        state_map = {"idle": 0, "connect": 1, "established": 2}
        state_value = state_map.get(state.lower(), 0)

        self.bgp_session_state.labels(self.node_id, peer_id, peer_asn).set(state_value)
        self.bgp_routes_advertised.labels(self.node_id, peer_id).set(routes_sent)
        self.bgp_routes_received.labels(self.node_id, peer_id).set(routes_received)

        # Update total sessions up
        # This would need to be calculated from all sessions

    def record_bgp_convergence(self, peer_id: str, duration_seconds: float):
        """Record BGP convergence time"""
        self.bgp_convergence_duration.labels(self.node_id, peer_id).observe(duration_seconds)

    def record_bgp_route_update(self, peer_id: str, update_type: str):
        """Record BGP route update"""
        self.bgp_route_updates.labels(self.node_id, peer_id, update_type).inc()

    def record_bgp_community_sent(self, community_type: str):
        """Record BGP community sent"""
        self.bgp_communities_sent.labels(self.node_id, community_type).inc()

    # Tunnel Metrics Update Methods
    def update_tunnel_status(self, tunnel_id: str, peer_id: str, status: str,
                           throughput_tx: float = 0, throughput_rx: float = 0):
        """Update tunnel metrics"""
        status_map = {"down": 0, "up": 1, "error": 2}
        status_value = status_map.get(status.lower(), 0)

        self.tunnel_status.labels(self.node_id, tunnel_id, peer_id).set(status_value)
        self.tunnel_throughput_bytes.labels(self.node_id, tunnel_id, "tx").set(throughput_tx)
        self.tunnel_throughput_bytes.labels(self.node_id, tunnel_id, "rx").set(throughput_rx)

    def record_tunnel_setup(self, tunnel_id: str, duration_seconds: float):
        """Record tunnel setup time"""
        self.tunnel_setup_duration.labels(self.node_id, tunnel_id).observe(duration_seconds)

    def record_tunnel_data_transfer(self, tunnel_id: str, bytes_tx: int, bytes_rx: int):
        """Record tunnel data transfer"""
        self.tunnel_bytes_transferred.labels(self.node_id, tunnel_id, "tx").inc(bytes_tx)
        self.tunnel_bytes_transferred.labels(self.node_id, tunnel_id, "rx").inc(bytes_rx)

    def record_tunnel_handshake(self, tunnel_id: str, success: bool):
        """Record tunnel handshake"""
        status = "success" if success else "failed"
        self.tunnel_handshakes.labels(self.node_id, tunnel_id, status).inc()

    def update_active_tunnels_count(self, count: int):
        """Update active tunnels count"""
        self.tunnels_active.labels(self.node_id).set(count)

    # Algorithm Metrics Update Methods
    def record_path_computation(self, algorithm_type: str, duration_seconds: float):
        """Record path computation time"""
        self.path_computation_duration.labels(self.node_id, algorithm_type).observe(duration_seconds)

    def record_path_change(self, destination_id: str, change_reason: str):
        """Record path change event"""
        self.path_changes_total.labels(self.node_id, destination_id, change_reason).inc()

    def record_hysteresis_event(self, event_type: str):
        """Record hysteresis event"""
        self.hysteresis_events.labels(self.node_id, event_type).inc()

    def update_topology_metrics(self, node_count: int, edge_count: int):
        """Update topology size metrics"""
        self.topology_nodes.labels(self.node_id).set(node_count)
        self.topology_edges.labels(self.node_id).set(edge_count)

    def update_routing_table_size(self, size: int):
        """Update routing table size"""
        self.routing_table_size.labels(self.node_id).set(size)

    def record_algorithm_selection(self, algorithm_type: str):
        """Record algorithm selection"""
        self.algorithm_selection.labels(self.node_id, algorithm_type).inc()

    # System Metrics Update Methods
    def update_system_metrics(self):
        """Update system health metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=None)
            self.cpu_usage_percent.labels(self.node_id).set(cpu_percent)

            # Memory usage
            memory = psutil.virtual_memory()
            self.memory_usage_bytes.labels(self.node_id, "used").set(memory.used)
            self.memory_usage_bytes.labels(self.node_id, "available").set(memory.available)
            self.memory_usage_bytes.labels(self.node_id, "total").set(memory.total)

            # Process information
            process = psutil.Process()
            self.process_threads.labels(self.node_id).set(process.num_threads())
            try:
                self.process_fds.labels(self.node_id).set(process.num_fds())
            except (AttributeError, psutil.AccessDenied):
                pass  # Not available on all platforms

        except Exception as e:
            self.logger.error(f"Error updating system metrics: {e}")

    def update_container_health(self, container_name: str, healthy: bool):
        """Update container health status"""
        self.container_health.labels(self.node_id, container_name).set(1 if healthy else 0)

    # Info Metrics Update Methods
    def update_version_info(self, version: str, build_date: str, commit_hash: str):
        """Update version information"""
        self.version_info.info({
            'version': version,
            'build_date': build_date,
            'commit_hash': commit_hash
        })

    def update_node_info(self, node_type: str, owl_port: str, api_port: str, asn: str):
        """Update node information"""
        self.node_info.info({
            'node_id': self.node_id,
            'node_type': node_type,
            'owl_port': owl_port,
            'api_port': api_port,
            'asn': asn
        })

    # Utility Methods
    def generate_metrics(self) -> str:
        """Generate Prometheus format metrics"""
        return generate_latest(self.registry).decode('utf-8')

    def get_content_type(self) -> str:
        """Get Prometheus content type"""
        return CONTENT_TYPE_LATEST

    async def start_background_collection(self, interval: float = 30.0):
        """Start background system metrics collection"""
        while True:
            try:
                self.update_system_metrics()
                await asyncio.sleep(interval)
            except Exception as e:
                self.logger.error(f"Error in background metrics collection: {e}")
                await asyncio.sleep(interval)

    def get_metric_summary(self) -> Dict[str, Any]:
        """Get summary of current metrics"""
        try:
            # This would typically parse the metrics output
            # For now, return basic structure
            return {
                "node_id": self.node_id,
                "timestamp": time.time(),
                "metrics_available": True,
                "registry_collectors": len(self.registry._collector_to_names)
            }
        except Exception as e:
            self.logger.error(f"Error getting metric summary: {e}")
            return {"error": str(e)}