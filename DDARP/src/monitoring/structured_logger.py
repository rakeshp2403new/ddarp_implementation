"""
Structured Logging for DDARP

Provides JSON-formatted structured logging with correlation IDs and proper
categorization for ELK stack integration and log analysis.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
from contextvars import ContextVar


class LogCategory(Enum):
    """Log categories for DDARP components"""
    OWL_MEASUREMENT = "owl_measurement"
    PATH_COMPUTATION = "path_computation"
    TUNNEL_LIFECYCLE = "tunnel_lifecycle"
    BGP_EVENT = "bgp_event"
    SYSTEM_HEALTH = "system_health"
    API_REQUEST = "api_request"
    CONFIGURATION = "configuration"
    SECURITY = "security"
    PERFORMANCE = "performance"
    ERROR = "error"


class LogLevel(Enum):
    """Extended log levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    AUDIT = "audit"


@dataclass
class LogContext:
    """Log context information"""
    correlation_id: str
    node_id: str
    component: str
    operation: Optional[str] = None
    peer_id: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class StructuredLogEntry:
    """Structured log entry"""
    timestamp: float
    level: str
    category: str
    message: str
    context: LogContext
    data: Dict[str, Any]
    tags: List[str]
    duration_ms: Optional[float] = None
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None


# Context variable for correlation ID
correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')


class DDARPStructuredLogger:
    """Structured logger for DDARP system"""

    def __init__(self, node_id: str, component: str, logger_name: Optional[str] = None):
        self.node_id = node_id
        self.component = component
        self.logger_name = logger_name or f"ddarp.{component}.{node_id}"

        # Set up Python logger
        self.logger = logging.getLogger(self.logger_name)
        self.logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # Add JSON formatter
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        self.logger.addHandler(handler)

        # Prevent propagation to avoid duplicate logs
        self.logger.propagate = False

    def _create_log_entry(self, level: LogLevel, category: LogCategory, message: str,
                         data: Optional[Dict[str, Any]] = None,
                         tags: Optional[List[str]] = None,
                         operation: Optional[str] = None,
                         peer_id: Optional[str] = None,
                         duration_ms: Optional[float] = None,
                         error_code: Optional[str] = None,
                         stack_trace: Optional[str] = None) -> StructuredLogEntry:
        """Create structured log entry"""

        correlation_id = correlation_id_var.get() or str(uuid.uuid4())

        context = LogContext(
            correlation_id=correlation_id,
            node_id=self.node_id,
            component=self.component,
            operation=operation,
            peer_id=peer_id
        )

        return StructuredLogEntry(
            timestamp=time.time(),
            level=level.value,
            category=category.value,
            message=message,
            context=context,
            data=data or {},
            tags=tags or [],
            duration_ms=duration_ms,
            error_code=error_code,
            stack_trace=stack_trace
        )

    def _log_entry(self, entry: StructuredLogEntry):
        """Log structured entry"""
        log_data = asdict(entry)

        # Map to Python log levels
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
            "audit": logging.INFO
        }

        python_level = level_map.get(entry.level, logging.INFO)
        self.logger.log(python_level, json.dumps(log_data))

    # OWL Measurement Logging
    def log_owl_measurement(self, peer_id: str, latency_ms: float, jitter_ms: float,
                           packet_loss_percent: float, measurement_id: str,
                           success: bool = True, error_msg: Optional[str] = None):
        """Log OWL measurement event"""
        data = {
            "measurement_id": measurement_id,
            "latency_ms": latency_ms,
            "jitter_ms": jitter_ms,
            "packet_loss_percent": packet_loss_percent,
            "success": success
        }

        if error_msg:
            data["error_message"] = error_msg

        level = LogLevel.INFO if success else LogLevel.WARNING
        message = f"OWL measurement to {peer_id}: {latency_ms:.2f}ms latency"

        entry = self._create_log_entry(
            level=level,
            category=LogCategory.OWL_MEASUREMENT,
            message=message,
            data=data,
            peer_id=peer_id,
            operation="measure_latency"
        )

        self._log_entry(entry)

    def log_owl_ping_timeout(self, peer_id: str, sequence: int, timeout_ms: int):
        """Log OWL ping timeout"""
        data = {
            "sequence": sequence,
            "timeout_ms": timeout_ms,
            "event": "ping_timeout"
        }

        entry = self._create_log_entry(
            level=LogLevel.WARNING,
            category=LogCategory.OWL_MEASUREMENT,
            message=f"OWL ping timeout to {peer_id} (seq={sequence})",
            data=data,
            peer_id=peer_id,
            operation="ping_timeout"
        )

        self._log_entry(entry)

    # Path Computation Logging
    def log_path_computation(self, algorithm: str, destination: str, path: List[str],
                           computation_time_ms: float, path_cost: float,
                           topology_size: int, reason: str = "periodic"):
        """Log path computation event"""
        data = {
            "algorithm": algorithm,
            "destination": destination,
            "path": path,
            "path_cost": path_cost,
            "topology_nodes": topology_size,
            "computation_reason": reason
        }

        message = f"Path computation to {destination}: {' -> '.join(path)} (cost: {path_cost:.2f})"

        entry = self._create_log_entry(
            level=LogLevel.INFO,
            category=LogCategory.PATH_COMPUTATION,
            message=message,
            data=data,
            operation="compute_path",
            duration_ms=computation_time_ms,
            tags=[algorithm]
        )

        self._log_entry(entry)

    def log_path_change(self, destination: str, old_path: List[str], new_path: List[str],
                       trigger: str, hysteresis_applied: bool):
        """Log path change event"""
        data = {
            "destination": destination,
            "old_path": old_path,
            "new_path": new_path,
            "change_trigger": trigger,
            "hysteresis_applied": hysteresis_applied
        }

        message = f"Path change to {destination}: {' -> '.join(old_path)} to {' -> '.join(new_path)}"

        entry = self._create_log_entry(
            level=LogLevel.INFO,
            category=LogCategory.PATH_COMPUTATION,
            message=message,
            data=data,
            operation="path_change",
            tags=["path_change", trigger]
        )

        self._log_entry(entry)

    def log_hysteresis_event(self, destination: str, current_cost: float, new_cost: float,
                           threshold: float, action: str):
        """Log hysteresis event"""
        improvement = ((current_cost - new_cost) / current_cost) * 100 if current_cost > 0 else 0

        data = {
            "destination": destination,
            "current_cost": current_cost,
            "new_cost": new_cost,
            "improvement_percent": improvement,
            "threshold_percent": threshold * 100,
            "action": action
        }

        message = f"Hysteresis {action} for {destination}: {improvement:.1f}% improvement"

        entry = self._create_log_entry(
            level=LogLevel.INFO,
            category=LogCategory.PATH_COMPUTATION,
            message=message,
            data=data,
            operation="hysteresis_check",
            tags=["hysteresis", action]
        )

        self._log_entry(entry)

    # Tunnel Lifecycle Logging
    def log_tunnel_created(self, tunnel_id: str, peer_id: str, local_ip: str,
                          remote_ip: str, setup_time_ms: float):
        """Log tunnel creation"""
        data = {
            "tunnel_id": tunnel_id,
            "local_ip": local_ip,
            "remote_ip": remote_ip,
            "setup_duration_ms": setup_time_ms
        }

        message = f"Tunnel created to {peer_id}: {local_ip} -> {remote_ip}"

        entry = self._create_log_entry(
            level=LogLevel.INFO,
            category=LogCategory.TUNNEL_LIFECYCLE,
            message=message,
            data=data,
            peer_id=peer_id,
            operation="tunnel_create",
            duration_ms=setup_time_ms,
            tags=["tunnel_up"]
        )

        self._log_entry(entry)

    def log_tunnel_destroyed(self, tunnel_id: str, peer_id: str, reason: str,
                           bytes_sent: int, bytes_received: int):
        """Log tunnel destruction"""
        data = {
            "tunnel_id": tunnel_id,
            "destruction_reason": reason,
            "total_bytes_sent": bytes_sent,
            "total_bytes_received": bytes_received
        }

        message = f"Tunnel destroyed to {peer_id}: {reason}"

        entry = self._create_log_entry(
            level=LogLevel.INFO,
            category=LogCategory.TUNNEL_LIFECYCLE,
            message=message,
            data=data,
            peer_id=peer_id,
            operation="tunnel_destroy",
            tags=["tunnel_down", reason]
        )

        self._log_entry(entry)

    def log_tunnel_handshake(self, tunnel_id: str, peer_id: str, success: bool,
                           handshake_time_ms: Optional[float] = None,
                           error_msg: Optional[str] = None):
        """Log tunnel handshake event"""
        data = {
            "tunnel_id": tunnel_id,
            "handshake_success": success
        }

        if handshake_time_ms:
            data["handshake_duration_ms"] = handshake_time_ms
        if error_msg:
            data["error_message"] = error_msg

        level = LogLevel.INFO if success else LogLevel.WARNING
        message = f"Tunnel handshake to {peer_id}: {'success' if success else 'failed'}"

        entry = self._create_log_entry(
            level=level,
            category=LogCategory.TUNNEL_LIFECYCLE,
            message=message,
            data=data,
            peer_id=peer_id,
            operation="tunnel_handshake",
            duration_ms=handshake_time_ms,
            tags=["handshake"]
        )

        self._log_entry(entry)

    # BGP Event Logging
    def log_bgp_session_state_change(self, peer_id: str, old_state: str, new_state: str,
                                   peer_asn: int, session_time_ms: Optional[float] = None):
        """Log BGP session state change"""
        data = {
            "peer_asn": peer_asn,
            "old_state": old_state,
            "new_state": new_state
        }

        if session_time_ms:
            data["session_duration_ms"] = session_time_ms

        level = LogLevel.INFO if new_state == "established" else LogLevel.WARNING
        message = f"BGP session to {peer_id} (AS{peer_asn}): {old_state} -> {new_state}"

        entry = self._create_log_entry(
            level=level,
            category=LogCategory.BGP_EVENT,
            message=message,
            data=data,
            peer_id=peer_id,
            operation="bgp_state_change",
            duration_ms=session_time_ms,
            tags=["bgp", new_state]
        )

        self._log_entry(entry)

    def log_bgp_route_update(self, peer_id: str, prefix: str, action: str,
                           communities: List[str], next_hop: str):
        """Log BGP route update"""
        data = {
            "prefix": prefix,
            "action": action,
            "communities": communities,
            "next_hop": next_hop
        }

        message = f"BGP route {action} for {prefix} via {peer_id}"

        entry = self._create_log_entry(
            level=LogLevel.INFO,
            category=LogCategory.BGP_EVENT,
            message=message,
            data=data,
            peer_id=peer_id,
            operation="bgp_route_update",
            tags=["bgp", action]
        )

        self._log_entry(entry)

    # System Health Logging
    def log_system_health(self, cpu_percent: float, memory_percent: float,
                         disk_percent: float, active_connections: int):
        """Log system health metrics"""
        data = {
            "cpu_usage_percent": cpu_percent,
            "memory_usage_percent": memory_percent,
            "disk_usage_percent": disk_percent,
            "active_connections": active_connections
        }

        # Determine log level based on resource usage
        max_usage = max(cpu_percent, memory_percent, disk_percent)
        if max_usage > 90:
            level = LogLevel.CRITICAL
        elif max_usage > 80:
            level = LogLevel.WARNING
        else:
            level = LogLevel.INFO

        message = f"System health: CPU {cpu_percent:.1f}%, Memory {memory_percent:.1f}%, Disk {disk_percent:.1f}%"

        entry = self._create_log_entry(
            level=level,
            category=LogCategory.SYSTEM_HEALTH,
            message=message,
            data=data,
            operation="health_check",
            tags=["health", "resources"]
        )

        self._log_entry(entry)

    def log_container_health(self, container_name: str, healthy: bool,
                           checks_passed: int, checks_total: int):
        """Log container health status"""
        data = {
            "container_name": container_name,
            "healthy": healthy,
            "checks_passed": checks_passed,
            "checks_total": checks_total,
            "health_ratio": checks_passed / checks_total if checks_total > 0 else 0
        }

        level = LogLevel.INFO if healthy else LogLevel.ERROR
        message = f"Container {container_name}: {'healthy' if healthy else 'unhealthy'} ({checks_passed}/{checks_total})"

        entry = self._create_log_entry(
            level=level,
            category=LogCategory.SYSTEM_HEALTH,
            message=message,
            data=data,
            operation="container_health_check",
            tags=["container", "health"]
        )

        self._log_entry(entry)

    # API Request Logging
    def log_api_request(self, method: str, path: str, status_code: int,
                       response_time_ms: float, client_ip: str, user_agent: str = ""):
        """Log API request"""
        data = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "client_ip": client_ip,
            "user_agent": user_agent
        }

        level = LogLevel.ERROR if status_code >= 400 else LogLevel.INFO
        message = f"{method} {path} -> {status_code} ({response_time_ms:.1f}ms)"

        entry = self._create_log_entry(
            level=level,
            category=LogCategory.API_REQUEST,
            message=message,
            data=data,
            operation="api_request",
            duration_ms=response_time_ms,
            tags=["api", method.lower()]
        )

        self._log_entry(entry)

    # Error Logging
    def log_error(self, error_msg: str, error_code: str, operation: str,
                 exception: Optional[Exception] = None,
                 additional_data: Optional[Dict[str, Any]] = None):
        """Log error event"""
        data = additional_data or {}
        data.update({
            "error_code": error_code,
            "operation": operation
        })

        stack_trace = None
        if exception:
            import traceback
            stack_trace = traceback.format_exc()
            data["exception_type"] = type(exception).__name__

        entry = self._create_log_entry(
            level=LogLevel.ERROR,
            category=LogCategory.ERROR,
            message=error_msg,
            data=data,
            operation=operation,
            error_code=error_code,
            stack_trace=stack_trace,
            tags=["error"]
        )

        self._log_entry(entry)

    # Generic Event Logging
    def log_event(self, event_type: str, message: str, data: Optional[Dict[str, Any]] = None,
                  level: str = "info", category: Optional[str] = None, peer_id: Optional[str] = None,
                  operation: Optional[str] = None, tags: Optional[List[str]] = None):
        """Generic event logging method for backward compatibility"""
        # Map string level to LogLevel enum
        level_map = {
            "debug": LogLevel.DEBUG,
            "info": LogLevel.INFO,
            "warning": LogLevel.WARNING,
            "error": LogLevel.ERROR,
            "critical": LogLevel.CRITICAL,
            "audit": LogLevel.AUDIT
        }

        log_level = level_map.get(level.lower(), LogLevel.INFO)

        # Map category string to LogCategory enum if provided
        category_map = {
            "owl_measurement": LogCategory.OWL_MEASUREMENT,
            "path_computation": LogCategory.PATH_COMPUTATION,
            "tunnel_lifecycle": LogCategory.TUNNEL_LIFECYCLE,
            "bgp_event": LogCategory.BGP_EVENT,
            "system_health": LogCategory.SYSTEM_HEALTH,
            "api_request": LogCategory.API_REQUEST,
            "configuration": LogCategory.CONFIGURATION,
            "security": LogCategory.SECURITY,
            "performance": LogCategory.PERFORMANCE,
            "error": LogCategory.ERROR
        }

        log_category = category_map.get(category, LogCategory.SYSTEM_HEALTH) if category else LogCategory.SYSTEM_HEALTH

        # Add event type to data
        event_data = data or {}
        event_data["event_type"] = event_type

        # Add event type to tags if not already present
        event_tags = tags or []
        if event_type not in event_tags:
            event_tags.append(event_type)

        entry = self._create_log_entry(
            level=log_level,
            category=log_category,
            message=message,
            data=event_data,
            operation=operation,
            peer_id=peer_id,
            tags=event_tags
        )

        self._log_entry(entry)

    # Context Management
    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID for current context"""
        correlation_id_var.set(correlation_id)

    def get_correlation_id(self) -> str:
        """Get current correlation ID"""
        return correlation_id_var.get()

    def new_correlation_id(self) -> str:
        """Generate and set new correlation ID"""
        correlation_id = str(uuid.uuid4())
        self.set_correlation_id(correlation_id)
        return correlation_id


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logs"""

    def format(self, record):
        """Format log record as JSON"""
        try:
            # If the message is already JSON, return it as-is
            if hasattr(record, 'message') and record.message.startswith('{'):
                return record.message

            # Otherwise, create basic JSON structure
            log_data = {
                "timestamp": record.created,
                "level": record.levelname.lower(),
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }

            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)

            return json.dumps(log_data)

        except Exception:
            # Fallback to standard formatting
            return super().format(record)


# Context manager for correlation ID
class CorrelationContext:
    """Context manager for correlation ID"""

    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.previous_id = None

    def __enter__(self):
        self.previous_id = correlation_id_var.get('')
        correlation_id_var.set(self.correlation_id)
        return self.correlation_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        correlation_id_var.set(self.previous_id or '')


# Factory function
def create_logger(node_id: str, component: str) -> DDARPStructuredLogger:
    """Factory function to create structured logger"""
    return DDARPStructuredLogger(node_id, component)