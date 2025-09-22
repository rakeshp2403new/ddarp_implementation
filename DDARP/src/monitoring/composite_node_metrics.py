"""
DDARP Composite Node Health Metrics

Prometheus metrics for monitoring DDARP composite node health,
including sub-component status, resource utilization, and
inter-component communication performance.
"""

import time
import psutil
import threading
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from prometheus_client import (
    Counter, Gauge, Histogram, Info, Summary,
    CollectorRegistry
)


class ComponentStatus(Enum):
    """Component health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    STARTING = "starting"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ComponentHealth:
    """Component health information"""
    name: str
    status: ComponentStatus
    last_heartbeat: float
    startup_time: Optional[float] = None
    restart_count: int = 0
    error_count: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    custom_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class InterComponentMetrics:
    """Inter-component communication metrics"""
    source: str
    target: str
    message_count: int = 0
    total_latency: float = 0.0
    error_count: int = 0
    last_communication: Optional[float] = None


class CompositeNodeHealthCollector:
    """Prometheus metrics collector for DDARP composite node health"""

    def __init__(self, node_id: str, registry: Optional[CollectorRegistry] = None):
        self.node_id = node_id
        self.registry = registry or CollectorRegistry()
        self.logger = logging.getLogger(f"composite_node_metrics_{node_id}")

        # Component tracking
        self.components: Dict[str, ComponentHealth] = {}
        self.inter_component_metrics: Dict[str, InterComponentMetrics] = {}
        self._lock = threading.RLock()

        self._init_component_metrics()
        self._init_resource_metrics()
        self._init_communication_metrics()
        self._init_performance_metrics()

    def _init_component_metrics(self):
        """Initialize component health metrics"""

        # Component health status
        self.component_health = Gauge(
            'ddarp_component_health',
            'Health status of DDARP components (1=healthy, 0=unhealthy)',
            ['node_id', 'component', 'status'],
            registry=self.registry
        )

        # Component uptime
        self.component_uptime_seconds = Gauge(
            'ddarp_component_uptime_seconds',
            'Component uptime in seconds',
            ['node_id', 'component'],
            registry=self.registry
        )

        # Component restart counter
        self.component_restarts_total = Counter(
            'ddarp_component_restarts_total',
            'Total number of component restarts',
            ['node_id', 'component', 'reason'],
            registry=self.registry
        )

        # Component initialization time
        self.component_init_duration_seconds = Histogram(
            'ddarp_component_init_duration_seconds',
            'Time taken for component initialization',
            ['node_id', 'component'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            registry=self.registry
        )

        # Component error counter
        self.component_errors_total = Counter(
            'ddarp_component_errors_total',
            'Total errors per component',
            ['node_id', 'component', 'error_type'],
            registry=self.registry
        )

        # Last heartbeat timestamp
        self.component_last_heartbeat = Gauge(
            'ddarp_component_last_heartbeat_timestamp',
            'Timestamp of last component heartbeat',
            ['node_id', 'component'],
            registry=self.registry
        )

    def _init_resource_metrics(self):
        """Initialize resource utilization metrics"""

        # CPU usage per component
        self.component_cpu_usage = Gauge(
            'ddarp_component_cpu_usage',
            'CPU usage percentage per component',
            ['node_id', 'component'],
            registry=self.registry
        )

        # Memory usage per component
        self.component_memory_usage = Gauge(
            'ddarp_component_memory_usage',
            'Memory usage in bytes per component',
            ['node_id', 'component'],
            registry=self.registry
        )

        # Memory usage percentage
        self.component_memory_usage_percent = Gauge(
            'ddarp_component_memory_usage_percent',
            'Memory usage percentage per component',
            ['node_id', 'component'],
            registry=self.registry
        )

        # Thread count per component
        self.component_thread_count = Gauge(
            'ddarp_component_thread_count',
            'Number of threads per component',
            ['node_id', 'component'],
            registry=self.registry
        )

        # File descriptor count per component
        self.component_fd_count = Gauge(
            'ddarp_component_fd_count',
            'Number of file descriptors per component',
            ['node_id', 'component'],
            registry=self.registry
        )

        # Network connections per component
        self.component_network_connections = Gauge(
            'ddarp_component_network_connections',
            'Number of network connections per component',
            ['node_id', 'component', 'state'],
            registry=self.registry
        )

    def _init_communication_metrics(self):
        """Initialize inter-component communication metrics"""

        # Inter-component communication latency
        self.inter_component_latency = Histogram(
            'ddarp_inter_component_latency_seconds',
            'Latency of inter-component communication',
            ['node_id', 'source_component', 'target_component', 'operation'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry
        )

        # Inter-component message counter
        self.inter_component_messages_total = Counter(
            'ddarp_inter_component_messages_total',
            'Total inter-component messages',
            ['node_id', 'source_component', 'target_component', 'message_type', 'status'],
            registry=self.registry
        )

        # Inter-component communication errors
        self.inter_component_errors_total = Counter(
            'ddarp_inter_component_errors_total',
            'Total inter-component communication errors',
            ['node_id', 'source_component', 'target_component', 'error_type'],
            registry=self.registry
        )

        # Component dependencies health
        self.component_dependency_health = Gauge(
            'ddarp_component_dependency_health',
            'Health of component dependencies (1=healthy, 0=unhealthy)',
            ['node_id', 'component', 'dependency'],
            registry=self.registry
        )

        # Message queue sizes
        self.component_queue_size = Gauge(
            'ddarp_component_queue_size',
            'Size of component message queues',
            ['node_id', 'component', 'queue_type'],
            registry=self.registry
        )

    def _init_performance_metrics(self):
        """Initialize performance monitoring metrics"""

        # Service response times
        self.service_response_time = Histogram(
            'ddarp_service_response_time_seconds',
            'Service response times',
            ['node_id', 'component', 'service', 'endpoint'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
            registry=self.registry
        )

        # Service request rate
        self.service_requests_per_second = Gauge(
            'ddarp_service_requests_per_second',
            'Service request rate',
            ['node_id', 'component', 'service'],
            registry=self.registry
        )

        # Resource bottleneck detection
        self.resource_bottleneck = Gauge(
            'ddarp_resource_bottleneck',
            'Resource bottleneck indicator (1=bottleneck detected)',
            ['node_id', 'component', 'resource_type'],
            registry=self.registry
        )

        # Performance regression detection
        self.performance_regression = Gauge(
            'ddarp_performance_regression',
            'Performance regression indicator (1=regression detected)',
            ['node_id', 'component', 'metric_type'],
            registry=self.registry
        )

    def register_component(self, component_name: str, startup_time: Optional[float] = None):
        """Register a new component for monitoring"""
        with self._lock:
            if component_name not in self.components:
                self.components[component_name] = ComponentHealth(
                    name=component_name,
                    status=ComponentStatus.STARTING,
                    last_heartbeat=time.time(),
                    startup_time=startup_time or time.time()
                )
                self.logger.info(f"Registered component: {component_name}")

    def update_component_status(self, component_name: str, status: ComponentStatus,
                              error_type: Optional[str] = None):
        """Update component health status"""
        with self._lock:
            if component_name in self.components:
                component = self.components[component_name]
                old_status = component.status
                component.status = status
                component.last_heartbeat = time.time()

                # Update Prometheus metrics
                self._update_component_health_metric(component_name, status)

                # Log status changes
                if old_status != status:
                    self.logger.info(f"Component {component_name} status: {old_status.value} -> {status.value}")

                # Record errors
                if status == ComponentStatus.ERROR and error_type:
                    component.error_count += 1
                    self.component_errors_total.labels(
                        node_id=self.node_id,
                        component=component_name,
                        error_type=error_type
                    ).inc()

    def record_component_restart(self, component_name: str, reason: str = "unknown"):
        """Record component restart event"""
        with self._lock:
            if component_name in self.components:
                self.components[component_name].restart_count += 1
                self.component_restarts_total.labels(
                    node_id=self.node_id,
                    component=component_name,
                    reason=reason
                ).inc()

    def record_component_initialization(self, component_name: str, duration: float):
        """Record component initialization time"""
        self.component_init_duration_seconds.labels(
            node_id=self.node_id,
            component=component_name
        ).observe(duration)

    def update_component_resources(self, component_name: str, cpu_percent: float,
                                 memory_bytes: float, memory_percent: float,
                                 thread_count: int = 0, fd_count: int = 0):
        """Update component resource utilization metrics"""
        with self._lock:
            if component_name in self.components:
                component = self.components[component_name]
                component.cpu_usage = cpu_percent
                component.memory_usage = memory_bytes

                # Update Prometheus metrics
                self.component_cpu_usage.labels(
                    node_id=self.node_id,
                    component=component_name
                ).set(cpu_percent)

                self.component_memory_usage.labels(
                    node_id=self.node_id,
                    component=component_name
                ).set(memory_bytes)

                self.component_memory_usage_percent.labels(
                    node_id=self.node_id,
                    component=component_name
                ).set(memory_percent)

                if thread_count > 0:
                    self.component_thread_count.labels(
                        node_id=self.node_id,
                        component=component_name
                    ).set(thread_count)

                if fd_count > 0:
                    self.component_fd_count.labels(
                        node_id=self.node_id,
                        component=component_name
                    ).set(fd_count)

    def record_inter_component_communication(self, source: str, target: str,
                                           operation: str, latency: float,
                                           message_type: str = "request",
                                           success: bool = True):
        """Record inter-component communication metrics"""
        # Record latency
        self.inter_component_latency.labels(
            node_id=self.node_id,
            source_component=source,
            target_component=target,
            operation=operation
        ).observe(latency)

        # Record message count
        status = "success" if success else "error"
        self.inter_component_messages_total.labels(
            node_id=self.node_id,
            source_component=source,
            target_component=target,
            message_type=message_type,
            status=status
        ).inc()

        # Update internal tracking
        key = f"{source}->{target}"
        with self._lock:
            if key not in self.inter_component_metrics:
                self.inter_component_metrics[key] = InterComponentMetrics(source, target)

            metrics = self.inter_component_metrics[key]
            metrics.message_count += 1
            metrics.total_latency += latency
            metrics.last_communication = time.time()

            if not success:
                metrics.error_count += 1

    def record_inter_component_error(self, source: str, target: str, error_type: str):
        """Record inter-component communication error"""
        self.inter_component_errors_total.labels(
            node_id=self.node_id,
            source_component=source,
            target_component=target,
            error_type=error_type
        ).inc()

    def update_component_dependency_health(self, component: str, dependency: str, healthy: bool):
        """Update component dependency health status"""
        self.component_dependency_health.labels(
            node_id=self.node_id,
            component=component,
            dependency=dependency
        ).set(1.0 if healthy else 0.0)

    def update_component_queue_size(self, component: str, queue_type: str, size: int):
        """Update component queue size"""
        self.component_queue_size.labels(
            node_id=self.node_id,
            component=component,
            queue_type=queue_type
        ).set(size)

    def record_service_response_time(self, component: str, service: str,
                                   endpoint: str, response_time: float):
        """Record service response time"""
        self.service_response_time.labels(
            node_id=self.node_id,
            component=component,
            service=service,
            endpoint=endpoint
        ).observe(response_time)

    def update_service_request_rate(self, component: str, service: str, rate: float):
        """Update service request rate"""
        self.service_requests_per_second.labels(
            node_id=self.node_id,
            component=component,
            service=service
        ).set(rate)

    def detect_resource_bottleneck(self, component: str, resource_type: str, is_bottleneck: bool):
        """Update resource bottleneck detection"""
        self.resource_bottleneck.labels(
            node_id=self.node_id,
            component=component,
            resource_type=resource_type
        ).set(1.0 if is_bottleneck else 0.0)

    def detect_performance_regression(self, component: str, metric_type: str, is_regression: bool):
        """Update performance regression detection"""
        self.performance_regression.labels(
            node_id=self.node_id,
            component=component,
            metric_type=metric_type
        ).set(1.0 if is_regression else 0.0)

    def heartbeat(self, component_name: str):
        """Record component heartbeat"""
        with self._lock:
            if component_name in self.components:
                self.components[component_name].last_heartbeat = time.time()
                self.component_last_heartbeat.labels(
                    node_id=self.node_id,
                    component=component_name
                ).set(time.time())

    def get_component_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive component health summary"""
        with self._lock:
            summary = {
                "node_id": self.node_id,
                "timestamp": time.time(),
                "components": {},
                "overall_health": "healthy"
            }

            unhealthy_count = 0
            for name, component in self.components.items():
                uptime = time.time() - component.startup_time if component.startup_time else 0
                avg_latency = 0

                # Calculate average inter-component latency
                relevant_metrics = [m for m in self.inter_component_metrics.values()
                                  if m.source == name or m.target == name]
                if relevant_metrics:
                    total_latency = sum(m.total_latency for m in relevant_metrics)
                    total_messages = sum(m.message_count for m in relevant_metrics)
                    avg_latency = total_latency / total_messages if total_messages > 0 else 0

                summary["components"][name] = {
                    "status": component.status.value,
                    "uptime_seconds": uptime,
                    "restart_count": component.restart_count,
                    "error_count": component.error_count,
                    "cpu_usage": component.cpu_usage,
                    "memory_usage": component.memory_usage,
                    "avg_inter_component_latency": avg_latency,
                    "last_heartbeat": component.last_heartbeat
                }

                if component.status not in [ComponentStatus.HEALTHY, ComponentStatus.STARTING]:
                    unhealthy_count += 1

            # Determine overall health
            if unhealthy_count == 0:
                summary["overall_health"] = "healthy"
            elif unhealthy_count < len(self.components) / 2:
                summary["overall_health"] = "degraded"
            else:
                summary["overall_health"] = "unhealthy"

            return summary

    def _update_component_health_metric(self, component_name: str, status: ComponentStatus):
        """Update component health Prometheus metric"""
        # Reset all status gauges for this component
        for status_enum in ComponentStatus:
            self.component_health.labels(
                node_id=self.node_id,
                component=component_name,
                status=status_enum.value
            ).set(0)

        # Set current status to 1
        self.component_health.labels(
            node_id=self.node_id,
            component=component_name,
            status=status.value
        ).set(1)

        # Update uptime
        component = self.components.get(component_name)
        if component and component.startup_time:
            uptime = time.time() - component.startup_time
            self.component_uptime_seconds.labels(
                node_id=self.node_id,
                component=component_name
            ).set(uptime)

    def get_unhealthy_components(self) -> List[str]:
        """Get list of unhealthy components"""
        with self._lock:
            return [
                name for name, component in self.components.items()
                if component.status not in [ComponentStatus.HEALTHY, ComponentStatus.STARTING]
            ]

    def get_stale_components(self, max_age_seconds: float = 300) -> List[str]:
        """Get components that haven't sent heartbeat recently"""
        current_time = time.time()
        with self._lock:
            return [
                name for name, component in self.components.items()
                if current_time - component.last_heartbeat > max_age_seconds
            ]


# Context managers for timing operations

class ComponentOperationTimer:
    """Context manager for timing component operations"""

    def __init__(self, collector: CompositeNodeHealthCollector,
                 source: str, target: str, operation: str):
        self.collector = collector
        self.source = source
        self.target = target
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            latency = time.time() - self.start_time
            success = exc_type is None
            self.collector.record_inter_component_communication(
                source=self.source,
                target=self.target,
                operation=self.operation,
                latency=latency,
                success=success
            )


class ServiceResponseTimer:
    """Context manager for timing service responses"""

    def __init__(self, collector: CompositeNodeHealthCollector,
                 component: str, service: str, endpoint: str):
        self.collector = collector
        self.component = component
        self.service = service
        self.endpoint = endpoint
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            response_time = time.time() - self.start_time
            self.collector.record_service_response_time(
                component=self.component,
                service=self.service,
                endpoint=self.endpoint,
                response_time=response_time
            )