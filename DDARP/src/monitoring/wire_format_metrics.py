"""
DDARP Wire Format Metrics

Prometheus metrics for DDARP protocol wire format processing,
including packet parsing, TLV processing, and error handling.
"""

import time
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass
from prometheus_client import (
    Counter, Gauge, Histogram, Summary, Info,
    CollectorRegistry
)

from ..protocol import TLVType


@dataclass
class PacketMetrics:
    """Packet processing metrics container"""
    parse_duration: float
    tlv_count: int
    packet_size: int
    success: bool
    error_type: Optional[str] = None


class WireFormatMetricsCollector:
    """Prometheus metrics collector for DDARP wire format processing"""

    def __init__(self, node_id: str, registry: Optional[CollectorRegistry] = None):
        self.node_id = node_id
        self.registry = registry or CollectorRegistry()
        self.logger = logging.getLogger(f"wire_format_metrics_{node_id}")

        self._init_packet_metrics()
        self._init_tlv_metrics()
        self._init_encoding_metrics()
        self._init_error_metrics()

    def _init_packet_metrics(self):
        """Initialize packet processing metrics"""

        # Packet parsing duration histogram
        self.packet_parse_duration = Histogram(
            'ddarp_packet_parse_duration_seconds',
            'Time taken to parse DDARP packets',
            ['node_id', 'packet_type', 'direction'],
            buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
            registry=self.registry
        )

        # Packet processing counters
        self.packets_processed_total = Counter(
            'ddarp_packets_processed_total',
            'Total number of DDARP packets processed',
            ['node_id', 'direction', 'status'],
            registry=self.registry
        )

        # Packet size histogram
        self.packet_size_bytes = Histogram(
            'ddarp_packet_size_bytes',
            'Size of DDARP packets in bytes',
            ['node_id', 'packet_type', 'direction'],
            buckets=[20, 50, 100, 200, 500, 1000, 2000, 5000, 10000],
            registry=self.registry
        )

        # Malformed packet detection
        self.malformed_packets_total = Counter(
            'ddarp_malformed_packets_total',
            'Total number of malformed packets detected',
            ['node_id', 'error_type', 'direction'],
            registry=self.registry
        )

        # Active packet processing gauge
        self.active_packet_processing = Gauge(
            'ddarp_active_packet_processing',
            'Number of packets currently being processed',
            ['node_id'],
            registry=self.registry
        )

    def _init_tlv_metrics(self):
        """Initialize TLV processing metrics"""

        # TLV processing counters
        self.tlv_processing_total = Counter(
            'ddarp_tlv_processing_total',
            'Total TLV processing operations',
            ['node_id', 'tlv_type', 'status', 'direction'],
            registry=self.registry
        )

        # TLV processing duration
        self.tlv_processing_duration = Histogram(
            'ddarp_tlv_processing_duration_seconds',
            'Time taken to process individual TLVs',
            ['node_id', 'tlv_type', 'operation'],
            buckets=[0.00001, 0.00005, 0.0001, 0.0005, 0.001, 0.005, 0.01],
            registry=self.registry
        )

        # Unknown TLV skip counts
        self.unknown_tlv_skipped_total = Counter(
            'ddarp_unknown_tlv_skipped_total',
            'Total number of unknown TLVs skipped',
            ['node_id', 'tlv_type_hex'],
            registry=self.registry
        )

        # TLV size distribution
        self.tlv_size_bytes = Histogram(
            'ddarp_tlv_size_bytes',
            'Size of individual TLVs in bytes',
            ['node_id', 'tlv_type'],
            buckets=[4, 10, 20, 50, 100, 200, 500, 1000, 2000],
            registry=self.registry
        )

        # TLV count per packet
        self.tlvs_per_packet = Histogram(
            'ddarp_tlvs_per_packet',
            'Number of TLVs per packet',
            ['node_id', 'packet_type'],
            buckets=[1, 2, 3, 5, 10, 20, 50],
            registry=self.registry
        )

    def _init_encoding_metrics(self):
        """Initialize binary encoding/decoding metrics"""

        # Encoding performance
        self.encoding_duration = Histogram(
            'ddarp_encoding_duration_seconds',
            'Time taken for packet encoding operations',
            ['node_id', 'operation_type', 'data_type'],
            buckets=[0.00001, 0.00005, 0.0001, 0.0005, 0.001, 0.005, 0.01],
            registry=self.registry
        )

        # Encoding operations counter
        self.encoding_operations_total = Counter(
            'ddarp_encoding_operations_total',
            'Total encoding/decoding operations',
            ['node_id', 'operation', 'status'],
            registry=self.registry
        )

        # Data compression ratio (when compression is enabled)
        self.compression_ratio = Histogram(
            'ddarp_compression_ratio',
            'Compression ratio for packet data',
            ['node_id', 'data_type'],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            registry=self.registry
        )

        # Encoding throughput
        self.encoding_throughput_bytes_per_second = Gauge(
            'ddarp_encoding_throughput_bytes_per_second',
            'Current encoding throughput in bytes per second',
            ['node_id', 'operation'],
            registry=self.registry
        )

    def _init_error_metrics(self):
        """Initialize error tracking metrics"""

        # Protocol errors
        self.protocol_errors_total = Counter(
            'ddarp_protocol_errors_total',
            'Total protocol-level errors',
            ['node_id', 'error_type', 'component'],
            registry=self.registry
        )

        # Recovery operations
        self.error_recovery_total = Counter(
            'ddarp_error_recovery_total',
            'Total error recovery operations',
            ['node_id', 'recovery_type', 'success'],
            registry=self.registry
        )

        # Current error rate
        self.current_error_rate = Gauge(
            'ddarp_current_error_rate',
            'Current error rate (errors per second)',
            ['node_id', 'error_category'],
            registry=self.registry
        )

    def record_packet_processing(self, metrics: PacketMetrics, direction: str, packet_type: str = "unknown"):
        """Record packet processing metrics"""

        # Record parsing duration
        self.packet_parse_duration.labels(
            node_id=self.node_id,
            packet_type=packet_type,
            direction=direction
        ).observe(metrics.parse_duration)

        # Record packet processed
        status = "success" if metrics.success else "failure"
        self.packets_processed_total.labels(
            node_id=self.node_id,
            direction=direction,
            status=status
        ).inc()

        # Record packet size
        self.packet_size_bytes.labels(
            node_id=self.node_id,
            packet_type=packet_type,
            direction=direction
        ).observe(metrics.packet_size)

        # Record TLV count
        self.tlvs_per_packet.labels(
            node_id=self.node_id,
            packet_type=packet_type
        ).observe(metrics.tlv_count)

        # Record error if present
        if not metrics.success and metrics.error_type:
            self.malformed_packets_total.labels(
                node_id=self.node_id,
                error_type=metrics.error_type,
                direction=direction
            ).inc()

    def record_tlv_processing(self, tlv_type: int, processing_time: float,
                            status: str, direction: str, operation: str = "decode"):
        """Record TLV processing metrics"""

        # Get TLV type name
        tlv_name = self._get_tlv_name(tlv_type)

        # Record processing time
        self.tlv_processing_duration.labels(
            node_id=self.node_id,
            tlv_type=tlv_name,
            operation=operation
        ).observe(processing_time)

        # Record processing count
        self.tlv_processing_total.labels(
            node_id=self.node_id,
            tlv_type=tlv_name,
            status=status,
            direction=direction
        ).inc()

    def record_unknown_tlv_skipped(self, tlv_type: int):
        """Record unknown TLV skip event"""
        self.unknown_tlv_skipped_total.labels(
            node_id=self.node_id,
            tlv_type_hex=f"0x{tlv_type:04X}"
        ).inc()

    def record_tlv_size(self, tlv_type: int, size_bytes: int):
        """Record TLV size distribution"""
        tlv_name = self._get_tlv_name(tlv_type)
        self.tlv_size_bytes.labels(
            node_id=self.node_id,
            tlv_type=tlv_name
        ).observe(size_bytes)

    def record_encoding_operation(self, operation: str, data_type: str,
                                 duration: float, success: bool):
        """Record encoding/decoding operation metrics"""

        # Record duration
        self.encoding_duration.labels(
            node_id=self.node_id,
            operation_type=operation,
            data_type=data_type
        ).observe(duration)

        # Record operation count
        status = "success" if success else "failure"
        self.encoding_operations_total.labels(
            node_id=self.node_id,
            operation=operation,
            status=status
        ).inc()

    def record_protocol_error(self, error_type: str, component: str):
        """Record protocol error"""
        self.protocol_errors_total.labels(
            node_id=self.node_id,
            error_type=error_type,
            component=component
        ).inc()

    def record_error_recovery(self, recovery_type: str, success: bool):
        """Record error recovery attempt"""
        self.error_recovery_total.labels(
            node_id=self.node_id,
            recovery_type=recovery_type,
            success=str(success).lower()
        ).inc()

    def update_active_processing(self, count: int):
        """Update active packet processing count"""
        self.active_packet_processing.labels(
            node_id=self.node_id
        ).set(count)

    def update_encoding_throughput(self, operation: str, bytes_per_second: float):
        """Update encoding throughput"""
        self.encoding_throughput_bytes_per_second.labels(
            node_id=self.node_id,
            operation=operation
        ).set(bytes_per_second)

    def update_error_rate(self, error_category: str, rate: float):
        """Update current error rate"""
        self.current_error_rate.labels(
            node_id=self.node_id,
            error_category=error_category
        ).set(rate)

    def _get_tlv_name(self, tlv_type: int) -> str:
        """Get human-readable TLV type name"""
        try:
            return TLVType(tlv_type).name
        except ValueError:
            return f"UNKNOWN_0x{tlv_type:04X}"

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get current metrics summary for debugging"""
        return {
            "node_id": self.node_id,
            "metrics_collected": [
                "packet_parse_duration",
                "packets_processed_total",
                "packet_size_bytes",
                "malformed_packets_total",
                "tlv_processing_total",
                "tlv_processing_duration",
                "unknown_tlv_skipped_total",
                "encoding_operations_total",
                "protocol_errors_total"
            ]
        }


class WireFormatMetricsInstrumentor:
    """Context manager for wire format metrics instrumentation"""

    def __init__(self, collector: WireFormatMetricsCollector, operation: str):
        self.collector = collector
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            success = exc_type is None
            self.collector.record_encoding_operation(
                operation=self.operation,
                data_type="packet",
                duration=duration,
                success=success
            )


# Utility functions for common metric patterns

def time_tlv_operation(collector: WireFormatMetricsCollector, tlv_type: int,
                      direction: str, operation: str = "decode"):
    """Decorator for timing TLV operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                status = "success" if success else "error"
                collector.record_tlv_processing(
                    tlv_type=tlv_type,
                    processing_time=duration,
                    status=status,
                    direction=direction,
                    operation=operation
                )
        return wrapper
    return decorator


def time_packet_operation(collector: WireFormatMetricsCollector, direction: str):
    """Decorator for timing packet operations"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            packet_size = 0
            tlv_count = 0
            success = True
            error_type = None

            try:
                result = func(*args, **kwargs)

                # Extract metrics from result if available
                if hasattr(result, '__len__'):
                    if isinstance(result, bytes):
                        packet_size = len(result)
                elif isinstance(result, tuple) and len(result) >= 2:
                    header, tlvs = result[:2]
                    tlv_count = len(tlvs) if tlvs else 0

                return result
            except Exception as e:
                success = False
                error_type = type(e).__name__
                raise
            finally:
                duration = time.time() - start_time
                metrics = PacketMetrics(
                    parse_duration=duration,
                    tlv_count=tlv_count,
                    packet_size=packet_size,
                    success=success,
                    error_type=error_type
                )
                collector.record_packet_processing(metrics, direction)
        return wrapper
    return decorator