"""
Enhanced Prometheus Exporter for DDARP

Integrates wire format metrics and composite node health monitoring
with the existing DDARP metrics collection system.
"""

import asyncio
import logging
import time
import psutil
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from prometheus_client import (
    CollectorRegistry, Counter, Gauge, Histogram, Info, Summary,
    generate_latest, CONTENT_TYPE_LATEST, start_http_server
)
from aiohttp import web

from .wire_format_metrics import WireFormatMetricsCollector, PacketMetrics
from .composite_node_metrics import CompositeNodeHealthCollector, ComponentStatus


@dataclass
class ExporterConfig:
    """Configuration for the enhanced Prometheus exporter"""
    node_id: str
    http_port: int = 9090
    enable_wire_format_metrics: bool = True
    enable_composite_metrics: bool = True
    collection_interval: float = 5.0
    resource_monitoring_interval: float = 10.0
    health_check_interval: float = 30.0


class EnhancedDDARPPrometheusExporter:
    """Enhanced Prometheus metrics exporter with wire format and composite node monitoring"""

    def __init__(self, config: ExporterConfig):
        self.config = config
        self.node_id = config.node_id
        self.registry = CollectorRegistry()
        self.logger = logging.getLogger(f"enhanced_prometheus_exporter_{self.node_id}")

        # Initialize collectors
        self.wire_format_collector = None
        self.composite_node_collector = None

        if config.enable_wire_format_metrics:
            self.wire_format_collector = WireFormatMetricsCollector(
                node_id=self.node_id,
                registry=self.registry
            )

        if config.enable_composite_metrics:
            self.composite_node_collector = CompositeNodeHealthCollector(
                node_id=self.node_id,
                registry=self.registry
            )

        # Initialize legacy metrics (from existing prometheus_exporter.py)
        self._init_legacy_metrics()

        # Background tasks
        self._monitoring_tasks = []
        self._shutdown_event = threading.Event()

        self.logger.info(f"Enhanced Prometheus exporter initialized for node {self.node_id}")

    def _init_legacy_metrics(self):
        """Initialize existing DDARP metrics for compatibility"""

        # OWL metrics
        self.owl_latency_histogram = Histogram(
            'ddarp_owl_latency_seconds',
            'One-way latency measurements',
            ['node_id', 'peer_id', 'direction'],
            registry=self.registry
        )

        self.owl_jitter_histogram = Histogram(
            'ddarp_owl_jitter_seconds',
            'Jitter measurements',
            ['node_id', 'peer_id'],
            registry=self.registry
        )

        # BGP metrics
        self.bgp_sessions_gauge = Gauge(
            'ddarp_bgp_sessions',
            'Number of BGP sessions',
            ['node_id', 'state'],
            registry=self.registry
        )

        self.bgp_routes_gauge = Gauge(
            'ddarp_bgp_routes',
            'Number of BGP routes',
            ['node_id', 'type'],
            registry=self.registry
        )

        # Tunnel metrics
        self.tunnel_count_gauge = Gauge(
            'ddarp_tunnels',
            'Number of active tunnels',
            ['node_id', 'type', 'state'],
            registry=self.registry
        )

        self.tunnel_traffic_bytes = Counter(
            'ddarp_tunnel_traffic_bytes_total',
            'Total tunnel traffic in bytes',
            ['node_id', 'tunnel_id', 'direction'],
            registry=self.registry
        )

        # System metrics
        self.system_cpu_usage = Gauge(
            'ddarp_system_cpu_usage',
            'System CPU usage percentage',
            ['node_id'],
            registry=self.registry
        )

        self.system_memory_usage = Gauge(
            'ddarp_system_memory_usage',
            'System memory usage in bytes',
            ['node_id'],
            registry=self.registry
        )

    async def start_monitoring(self):
        """Start background monitoring tasks"""
        self.logger.info("Starting enhanced monitoring tasks")

        # Start resource monitoring
        if self.composite_node_collector:
            self._monitoring_tasks.append(
                asyncio.create_task(self._resource_monitoring_loop())
            )

        # Start health checking
        if self.composite_node_collector:
            self._monitoring_tasks.append(
                asyncio.create_task(self._health_check_loop())
            )

        # Start metrics collection
        self._monitoring_tasks.append(
            asyncio.create_task(self._metrics_collection_loop())
        )

        await asyncio.gather(*self._monitoring_tasks, return_exceptions=True)

    async def stop_monitoring(self):
        """Stop all monitoring tasks"""
        self.logger.info("Stopping enhanced monitoring tasks")
        self._shutdown_event.set()

        for task in self._monitoring_tasks:
            if not task.done():
                task.cancel()

        await asyncio.gather(*self._monitoring_tasks, return_exceptions=True)

    async def _resource_monitoring_loop(self):
        """Background task for monitoring system resources"""
        while not self._shutdown_event.is_set():
            try:
                await self._collect_system_resources()
                await asyncio.sleep(self.config.resource_monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in resource monitoring: {e}")
                await asyncio.sleep(5)

    async def _health_check_loop(self):
        """Background task for health checking"""
        while not self._shutdown_event.is_set():
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in health checking: {e}")
                await asyncio.sleep(5)

    async def _metrics_collection_loop(self):
        """Background task for general metrics collection"""
        while not self._shutdown_event.is_set():
            try:
                await self._collect_general_metrics()
                await asyncio.sleep(self.config.collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in metrics collection: {e}")
                await asyncio.sleep(5)

    async def _collect_system_resources(self):
        """Collect system resource metrics"""
        try:
            # Overall system metrics
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()

            self.system_cpu_usage.labels(node_id=self.node_id).set(cpu_percent)
            self.system_memory_usage.labels(node_id=self.node_id).set(memory.used)

            # Process-specific metrics (if available)
            if self.composite_node_collector:
                current_process = psutil.Process()
                process_cpu = current_process.cpu_percent()
                process_memory = current_process.memory_info()

                # Update main process metrics
                self.composite_node_collector.update_component_resources(
                    component_name="main_process",
                    cpu_percent=process_cpu,
                    memory_bytes=process_memory.rss,
                    memory_percent=(process_memory.rss / memory.total) * 100,
                    thread_count=current_process.num_threads(),
                    fd_count=current_process.num_fds() if hasattr(current_process, 'num_fds') else 0
                )

        except Exception as e:
            self.logger.error(f"Error collecting system resources: {e}")

    async def _perform_health_checks(self):
        """Perform component health checks"""
        if not self.composite_node_collector:
            return

        try:
            # Check for stale components (haven't sent heartbeat recently)
            stale_components = self.composite_node_collector.get_stale_components(
                max_age_seconds=self.config.health_check_interval * 2
            )

            for component in stale_components:
                self.composite_node_collector.update_component_status(
                    component_name=component,
                    status=ComponentStatus.UNHEALTHY,
                    error_type="stale_heartbeat"
                )

            # Log health summary
            health_summary = self.composite_node_collector.get_component_health_summary()
            self.logger.debug(f"Health summary: {health_summary['overall_health']}")

        except Exception as e:
            self.logger.error(f"Error performing health checks: {e}")

    async def _collect_general_metrics(self):
        """Collect general DDARP metrics"""
        try:
            # This would integrate with existing DDARP components
            # For now, we'll simulate some basic metrics

            # Simulate BGP session status
            self.bgp_sessions_gauge.labels(
                node_id=self.node_id,
                state="established"
            ).set(3)  # Example: 3 established sessions

            # Simulate tunnel count
            self.tunnel_count_gauge.labels(
                node_id=self.node_id,
                type="wireguard",
                state="active"
            ).set(5)  # Example: 5 active WireGuard tunnels

        except Exception as e:
            self.logger.error(f"Error collecting general metrics: {e}")

    # Wire Format Metrics Integration

    def record_packet_processing(self, packet_data: bytes, direction: str,
                                success: bool, parse_duration: float,
                                tlv_count: int = 0, error_type: Optional[str] = None):
        """Record wire format packet processing metrics"""
        if not self.wire_format_collector:
            return

        metrics = PacketMetrics(
            parse_duration=parse_duration,
            tlv_count=tlv_count,
            packet_size=len(packet_data),
            success=success,
            error_type=error_type
        )

        self.wire_format_collector.record_packet_processing(
            metrics=metrics,
            direction=direction,
            packet_type="ddarp"
        )

    def record_tlv_processing(self, tlv_type: int, processing_time: float,
                            success: bool, direction: str, operation: str = "decode"):
        """Record TLV processing metrics"""
        if not self.wire_format_collector:
            return

        status = "success" if success else "error"
        self.wire_format_collector.record_tlv_processing(
            tlv_type=tlv_type,
            processing_time=processing_time,
            status=status,
            direction=direction,
            operation=operation
        )

    def record_unknown_tlv_skipped(self, tlv_type: int):
        """Record unknown TLV skip event"""
        if self.wire_format_collector:
            self.wire_format_collector.record_unknown_tlv_skipped(tlv_type)

    def record_encoding_operation(self, operation: str, data_type: str,
                                 duration: float, success: bool):
        """Record encoding/decoding operation"""
        if self.wire_format_collector:
            self.wire_format_collector.record_encoding_operation(
                operation=operation,
                data_type=data_type,
                duration=duration,
                success=success
            )

    # Composite Node Metrics Integration

    def register_component(self, component_name: str):
        """Register a component for health monitoring"""
        if self.composite_node_collector:
            self.composite_node_collector.register_component(
                component_name=component_name,
                startup_time=time.time()
            )

    def update_component_status(self, component_name: str, status: ComponentStatus,
                              error_type: Optional[str] = None):
        """Update component health status"""
        if self.composite_node_collector:
            self.composite_node_collector.update_component_status(
                component_name=component_name,
                status=status,
                error_type=error_type
            )

    def record_component_restart(self, component_name: str, reason: str = "unknown"):
        """Record component restart"""
        if self.composite_node_collector:
            self.composite_node_collector.record_component_restart(
                component_name=component_name,
                reason=reason
            )

    def record_inter_component_communication(self, source: str, target: str,
                                           operation: str, latency: float,
                                           success: bool = True):
        """Record inter-component communication"""
        if self.composite_node_collector:
            self.composite_node_collector.record_inter_component_communication(
                source=source,
                target=target,
                operation=operation,
                latency=latency,
                success=success
            )

    def heartbeat(self, component_name: str):
        """Send component heartbeat"""
        if self.composite_node_collector:
            self.composite_node_collector.heartbeat(component_name)

    # Legacy metric methods for compatibility

    def record_owl_measurement(self, peer_id: str, latency: float, jitter: float, direction: str):
        """Record OWL measurement (legacy compatibility)"""
        self.owl_latency_histogram.labels(
            node_id=self.node_id,
            peer_id=peer_id,
            direction=direction
        ).observe(latency)

        self.owl_jitter_histogram.labels(
            node_id=self.node_id,
            peer_id=peer_id
        ).observe(jitter)

    def update_bgp_sessions(self, state: str, count: int):
        """Update BGP session count"""
        self.bgp_sessions_gauge.labels(
            node_id=self.node_id,
            state=state
        ).set(count)

    def update_tunnel_count(self, tunnel_type: str, state: str, count: int):
        """Update tunnel count"""
        self.tunnel_count_gauge.labels(
            node_id=self.node_id,
            type=tunnel_type,
            state=state
        ).set(count)

    def record_tunnel_traffic(self, tunnel_id: str, direction: str, bytes_count: int):
        """Record tunnel traffic"""
        self.tunnel_traffic_bytes.labels(
            node_id=self.node_id,
            tunnel_id=tunnel_id,
            direction=direction
        ).inc(bytes_count)

    # HTTP endpoint for metrics exposition

    async def setup_http_server(self):
        """Setup HTTP server for metrics exposition"""
        app = web.Application()
        app.router.add_get('/metrics', self._metrics_handler)
        app.router.add_get('/health', self._health_handler)
        app.router.add_get('/status', self._status_handler)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, '0.0.0.0', self.config.http_port)
        await site.start()

        self.logger.info(f"Metrics HTTP server started on port {self.config.http_port}")
        return runner

    async def _metrics_handler(self, request):
        """Handle metrics exposition endpoint"""
        try:
            metrics_data = generate_latest(self.registry)
            return web.Response(
                body=metrics_data,
                content_type=CONTENT_TYPE_LATEST
            )
        except Exception as e:
            self.logger.error(f"Error generating metrics: {e}")
            return web.Response(status=500, text=str(e))

    async def _health_handler(self, request):
        """Handle health check endpoint"""
        try:
            if self.composite_node_collector:
                health_summary = self.composite_node_collector.get_component_health_summary()
                return web.json_response(health_summary)
            else:
                return web.json_response({"status": "ok", "timestamp": time.time()})
        except Exception as e:
            self.logger.error(f"Error in health handler: {e}")
            return web.Response(status=500, text=str(e))

    async def _status_handler(self, request):
        """Handle status endpoint"""
        try:
            status = {
                "node_id": self.node_id,
                "timestamp": time.time(),
                "wire_format_metrics_enabled": self.wire_format_collector is not None,
                "composite_metrics_enabled": self.composite_node_collector is not None,
                "monitoring_tasks_active": len([t for t in self._monitoring_tasks if not t.done()]),
                "config": {
                    "collection_interval": self.config.collection_interval,
                    "resource_monitoring_interval": self.config.resource_monitoring_interval,
                    "health_check_interval": self.config.health_check_interval
                }
            }

            if self.wire_format_collector:
                status["wire_format_metrics"] = self.wire_format_collector.get_metrics_summary()

            if self.composite_node_collector:
                status["component_health"] = self.composite_node_collector.get_component_health_summary()

            return web.json_response(status)
        except Exception as e:
            self.logger.error(f"Error in status handler: {e}")
            return web.Response(status=500, text=str(e))

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        summary = {
            "node_id": self.node_id,
            "timestamp": time.time(),
            "exporter_status": "active"
        }

        if self.wire_format_collector:
            summary["wire_format_metrics"] = self.wire_format_collector.get_metrics_summary()

        if self.composite_node_collector:
            summary["component_health"] = self.composite_node_collector.get_component_health_summary()

        return summary


# Factory function for easy initialization
def create_enhanced_exporter(node_id: str, **kwargs) -> EnhancedDDARPPrometheusExporter:
    """Factory function to create enhanced Prometheus exporter"""
    config = ExporterConfig(node_id=node_id, **kwargs)
    return EnhancedDDARPPrometheusExporter(config)