"""
Enhanced DDARP OWL Engine with Matrix Management

Provides advanced One-Way Latency measurement capabilities with
distributed matrix management, predictive analytics, and quality monitoring.
"""

import asyncio
import logging
import time
import json
import statistics
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from collections import defaultdict, deque

from ..monitoring.enhanced_prometheus_exporter import ComponentStatus


class MeasurementQuality(Enum):
    """Quality levels for OWL measurements"""
    EXCELLENT = "excellent"  # < 1% jitter, < 0.1% loss
    GOOD = "good"           # < 5% jitter, < 1% loss
    FAIR = "fair"           # < 10% jitter, < 5% loss
    POOR = "poor"           # >= 10% jitter or >= 5% loss


@dataclass
class OWLMeasurement:
    """Individual OWL measurement"""
    source: str
    destination: str
    latency_ns: int
    timestamp: float
    sequence: int
    jitter_ns: Optional[int] = None
    packet_loss_percent: float = 0.0
    quality: MeasurementQuality = MeasurementQuality.GOOD


@dataclass
class MatrixEntry:
    """Entry in the OWL measurement matrix"""
    source: str
    destination: str
    current_latency_ms: float
    average_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    jitter_ms: float
    packet_loss_percent: float
    quality: MeasurementQuality
    sample_count: int
    last_updated: float
    confidence: float = 1.0  # 0.0 to 1.0
    trend: str = "stable"    # "improving", "degrading", "stable"


@dataclass
class PredictionModel:
    """Predictive model for latency forecasting"""
    destination: str
    model_type: str = "linear_regression"
    parameters: Dict[str, float] = field(default_factory=dict)
    training_data: List[Tuple[float, float]] = field(default_factory=list)  # (time, latency)
    accuracy: float = 0.0
    last_trained: float = 0.0


class EnhancedOWLEngine:
    """Enhanced OWL Engine with matrix management and analytics"""

    def __init__(self, node_id: str, config: Optional[Dict[str, Any]] = None):
        self.node_id = node_id
        self.config = config or {}
        self.logger = logging.getLogger(f"enhanced_owl_engine_{node_id}")

        # Component state
        self.running = False
        self.status = ComponentStatus.STOPPED

        # Measurement matrix
        self.owl_matrix: Dict[str, Dict[str, MatrixEntry]] = defaultdict(dict)
        self.measurement_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)  # Keep last 1000 measurements per destination
        )

        # Active measurements
        self.active_measurements: Set[str] = set()  # destination nodes
        self.measurement_tasks: Dict[str, asyncio.Task] = {}

        # Prediction models
        self.prediction_models: Dict[str, PredictionModel] = {}

        # Network discovery
        self.peer_nodes: Set[str] = set()
        self.network_topology: Dict[str, Set[str]] = defaultdict(set)

        # Quality monitoring
        self.quality_thresholds = {
            MeasurementQuality.EXCELLENT: {"jitter_percent": 1.0, "loss_percent": 0.1},
            MeasurementQuality.GOOD: {"jitter_percent": 5.0, "loss_percent": 1.0},
            MeasurementQuality.FAIR: {"jitter_percent": 10.0, "loss_percent": 5.0}
        }

        # Performance metrics
        self.measurements_sent = 0
        self.measurements_received = 0
        self.matrix_updates = 0
        self.prediction_accuracy = 0.0

        # Configuration
        self.measurement_interval = 1.0  # seconds
        self.matrix_sync_interval = 10.0  # seconds
        self.prediction_update_interval = 60.0  # seconds
        self.history_retention_hours = 24

        self.logger.info(f"Enhanced OWL Engine initialized for node {node_id}")

    async def start(self):
        """Start the enhanced OWL engine"""
        self.logger.info("Starting Enhanced OWL Engine")
        self.status = ComponentStatus.STARTING

        try:
            # Start background tasks
            asyncio.create_task(self._measurement_orchestrator())
            asyncio.create_task(self._matrix_management_loop())
            asyncio.create_task(self._prediction_update_loop())
            asyncio.create_task(self._quality_monitoring_loop())
            asyncio.create_task(self._history_cleanup_loop())

            self.running = True
            self.status = ComponentStatus.HEALTHY

            self.logger.info("Enhanced OWL Engine started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start Enhanced OWL Engine: {e}")
            self.status = ComponentStatus.ERROR
            raise

    async def stop(self):
        """Stop the enhanced OWL engine"""
        self.logger.info("Stopping Enhanced OWL Engine")
        self.status = ComponentStatus.STOPPING

        self.running = False

        # Stop all measurement tasks
        for task in self.measurement_tasks.values():
            if not task.done():
                task.cancel()

        await asyncio.gather(*self.measurement_tasks.values(), return_exceptions=True)

        self.status = ComponentStatus.STOPPED
        self.logger.info("Enhanced OWL Engine stopped")

    async def _measurement_orchestrator(self):
        """Orchestrate OWL measurements to all destinations"""
        while self.running:
            try:
                # Start measurements for new peers
                new_destinations = self.peer_nodes - self.active_measurements
                for destination in new_destinations:
                    await self._start_measurement_to_destination(destination)

                # Stop measurements for removed peers
                removed_destinations = self.active_measurements - self.peer_nodes
                for destination in removed_destinations:
                    await self._stop_measurement_to_destination(destination)

                await asyncio.sleep(5.0)  # Check every 5 seconds

            except Exception as e:
                self.logger.error(f"Error in measurement orchestrator: {e}")

    async def _start_measurement_to_destination(self, destination: str):
        """Start OWL measurements to specific destination"""
        if destination in self.measurement_tasks:
            return

        self.logger.info(f"Starting OWL measurements to {destination}")

        task = asyncio.create_task(
            self._measurement_loop(destination),
            name=f"owl_measurement_{destination}"
        )

        self.measurement_tasks[destination] = task
        self.active_measurements.add(destination)

    async def _stop_measurement_to_destination(self, destination: str):
        """Stop OWL measurements to specific destination"""
        if destination not in self.measurement_tasks:
            return

        self.logger.info(f"Stopping OWL measurements to {destination}")

        task = self.measurement_tasks.pop(destination)
        if not task.done():
            task.cancel()

        self.active_measurements.discard(destination)

    async def _measurement_loop(self, destination: str):
        """Continuous measurement loop for specific destination"""
        sequence = 0

        while self.running and destination in self.peer_nodes:
            try:
                # Perform measurement
                measurement = await self._perform_measurement(destination, sequence)
                if measurement:
                    await self._process_measurement(measurement)

                sequence += 1
                await asyncio.sleep(self.measurement_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error measuring to {destination}: {e}")
                await asyncio.sleep(self.measurement_interval)

    async def _perform_measurement(self, destination: str, sequence: int) -> Optional[OWLMeasurement]:
        """Perform single OWL measurement"""
        try:
            start_time = time.time_ns()

            # Simulate measurement (in real implementation, this would send actual packets)
            await asyncio.sleep(0.001)  # Simulate network delay

            end_time = time.time_ns()
            latency_ns = end_time - start_time

            # Calculate jitter if we have previous measurements
            jitter_ns = None
            history = self.measurement_history[destination]
            if history:
                recent_latencies = [m.latency_ns for m in list(history)[-10:]]
                if len(recent_latencies) > 1:
                    jitter_ns = int(statistics.stdev(recent_latencies))

            measurement = OWLMeasurement(
                source=self.node_id,
                destination=destination,
                latency_ns=latency_ns,
                timestamp=time.time(),
                sequence=sequence,
                jitter_ns=jitter_ns
            )

            self.measurements_sent += 1
            return measurement

        except Exception as e:
            self.logger.error(f"Error performing measurement to {destination}: {e}")
            return None

    async def _process_measurement(self, measurement: OWLMeasurement):
        """Process and store measurement"""
        try:
            # Add to history
            destination = measurement.destination
            self.measurement_history[destination].append(measurement)

            # Update matrix entry
            await self._update_matrix_entry(measurement)

            # Check quality
            quality = self._assess_measurement_quality(measurement, destination)
            measurement.quality = quality

            self.logger.debug(
                f"Measurement to {destination}: "
                f"{measurement.latency_ns / 1_000_000:.2f}ms "
                f"(quality: {quality.value})"
            )

        except Exception as e:
            self.logger.error(f"Error processing measurement: {e}")

    async def _update_matrix_entry(self, measurement: OWLMeasurement):
        """Update OWL matrix entry with new measurement"""
        source = measurement.source
        destination = measurement.destination

        if destination not in self.owl_matrix[source]:
            # Create new entry
            self.owl_matrix[source][destination] = MatrixEntry(
                source=source,
                destination=destination,
                current_latency_ms=measurement.latency_ns / 1_000_000,
                average_latency_ms=measurement.latency_ns / 1_000_000,
                min_latency_ms=measurement.latency_ns / 1_000_000,
                max_latency_ms=measurement.latency_ns / 1_000_000,
                jitter_ms=0.0,
                packet_loss_percent=0.0,
                quality=measurement.quality,
                sample_count=1,
                last_updated=measurement.timestamp
            )
        else:
            # Update existing entry
            entry = self.owl_matrix[source][destination]
            latency_ms = measurement.latency_ns / 1_000_000

            # Update statistics
            entry.current_latency_ms = latency_ms
            entry.min_latency_ms = min(entry.min_latency_ms, latency_ms)
            entry.max_latency_ms = max(entry.max_latency_ms, latency_ms)

            # Calculate running average
            total_latency = entry.average_latency_ms * entry.sample_count + latency_ms
            entry.sample_count += 1
            entry.average_latency_ms = total_latency / entry.sample_count

            # Update jitter
            if measurement.jitter_ns:
                entry.jitter_ms = measurement.jitter_ns / 1_000_000

            # Update quality
            entry.quality = measurement.quality
            entry.last_updated = measurement.timestamp

            # Calculate trend
            entry.trend = self._calculate_trend(destination)

            # Update confidence based on sample count and recency
            entry.confidence = min(1.0, entry.sample_count / 100) * \
                             max(0.1, 1.0 - (time.time() - entry.last_updated) / 300)

        self.matrix_updates += 1

    def _assess_measurement_quality(self, measurement: OWLMeasurement, destination: str) -> MeasurementQuality:
        """Assess quality of measurement"""
        if not measurement.jitter_ns:
            return MeasurementQuality.GOOD

        # Calculate jitter percentage
        jitter_percent = (measurement.jitter_ns / measurement.latency_ns) * 100

        # Determine quality based on thresholds
        if (jitter_percent < self.quality_thresholds[MeasurementQuality.EXCELLENT]["jitter_percent"] and
                measurement.packet_loss_percent < self.quality_thresholds[MeasurementQuality.EXCELLENT]["loss_percent"]):
            return MeasurementQuality.EXCELLENT

        elif (jitter_percent < self.quality_thresholds[MeasurementQuality.GOOD]["jitter_percent"] and
              measurement.packet_loss_percent < self.quality_thresholds[MeasurementQuality.GOOD]["loss_percent"]):
            return MeasurementQuality.GOOD

        elif (jitter_percent < self.quality_thresholds[MeasurementQuality.FAIR]["jitter_percent"] and
              measurement.packet_loss_percent < self.quality_thresholds[MeasurementQuality.FAIR]["loss_percent"]):
            return MeasurementQuality.FAIR

        else:
            return MeasurementQuality.POOR

    def _calculate_trend(self, destination: str) -> str:
        """Calculate latency trend for destination"""
        history = self.measurement_history[destination]
        if len(history) < 10:
            return "stable"

        # Get recent measurements
        recent = list(history)[-10:]
        latencies = [m.latency_ns for m in recent]

        # Simple trend analysis
        first_half = latencies[:5]
        second_half = latencies[5:]

        avg_first = statistics.mean(first_half)
        avg_second = statistics.mean(second_half)

        change_percent = ((avg_second - avg_first) / avg_first) * 100

        if change_percent > 10:
            return "degrading"
        elif change_percent < -10:
            return "improving"
        else:
            return "stable"

    async def _matrix_management_loop(self):
        """Manage and synchronize OWL matrix"""
        while self.running:
            try:
                await self._synchronize_matrix()
                await asyncio.sleep(self.matrix_sync_interval)
            except Exception as e:
                self.logger.error(f"Error in matrix management loop: {e}")

    async def _synchronize_matrix(self):
        """Synchronize matrix with peer nodes"""
        # Prepare matrix for sharing
        matrix_data = {
            "node_id": self.node_id,
            "timestamp": time.time(),
            "matrix": {}
        }

        for source, destinations in self.owl_matrix.items():
            matrix_data["matrix"][source] = {}
            for dest, entry in destinations.items():
                matrix_data["matrix"][source][dest] = {
                    "current_latency_ms": entry.current_latency_ms,
                    "average_latency_ms": entry.average_latency_ms,
                    "jitter_ms": entry.jitter_ms,
                    "quality": entry.quality.value,
                    "confidence": entry.confidence,
                    "last_updated": entry.last_updated
                }

        # Send to all peers (placeholder for actual networking)
        for peer in self.peer_nodes:
            await self._send_matrix_update(peer, matrix_data)

    async def _send_matrix_update(self, peer: str, matrix_data: Dict[str, Any]):
        """Send matrix update to peer"""
        # Placeholder for actual network communication
        self.logger.debug(f"Sending matrix update to {peer}")

    async def _prediction_update_loop(self):
        """Update prediction models"""
        while self.running:
            try:
                await self._update_prediction_models()
                await asyncio.sleep(self.prediction_update_interval)
            except Exception as e:
                self.logger.error(f"Error in prediction update loop: {e}")

    async def _update_prediction_models(self):
        """Update latency prediction models"""
        for destination in self.peer_nodes:
            try:
                await self._train_prediction_model(destination)
            except Exception as e:
                self.logger.error(f"Error training model for {destination}: {e}")

    async def _train_prediction_model(self, destination: str):
        """Train prediction model for destination"""
        history = self.measurement_history[destination]
        if len(history) < 50:  # Need sufficient data
            return

        # Prepare training data
        measurements = list(history)[-100:]  # Use last 100 measurements
        training_data = [
            (m.timestamp, m.latency_ns / 1_000_000)  # (time, latency_ms)
            for m in measurements
        ]

        if destination not in self.prediction_models:
            self.prediction_models[destination] = PredictionModel(destination=destination)

        model = self.prediction_models[destination]
        model.training_data = training_data
        model.last_trained = time.time()

        # Simple linear regression (placeholder for more sophisticated models)
        if len(training_data) >= 2:
            times = [t for t, _ in training_data]
            latencies = [l for _, l in training_data]

            # Calculate slope and intercept
            x_mean = statistics.mean(times)
            y_mean = statistics.mean(latencies)

            numerator = sum((x - x_mean) * (y - y_mean) for x, y in training_data)
            denominator = sum((x - x_mean) ** 2 for x, _ in training_data)

            if denominator != 0:
                slope = numerator / denominator
                intercept = y_mean - slope * x_mean

                model.parameters = {"slope": slope, "intercept": intercept}

                # Calculate accuracy (simplified R-squared)
                predicted = [slope * t + intercept for t, _ in training_data]
                ss_res = sum((actual - pred) ** 2 for (_, actual), pred in zip(training_data, predicted))
                ss_tot = sum((actual - y_mean) ** 2 for _, actual in training_data)

                model.accuracy = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

        self.logger.debug(f"Trained prediction model for {destination}: accuracy={model.accuracy:.3f}")

    def predict_latency(self, destination: str, future_time: Optional[float] = None) -> Optional[float]:
        """Predict latency to destination at future time"""
        if destination not in self.prediction_models:
            return None

        model = self.prediction_models[destination]
        if not model.parameters:
            return None

        target_time = future_time or time.time()
        slope = model.parameters.get("slope", 0)
        intercept = model.parameters.get("intercept", 0)

        predicted_latency = slope * target_time + intercept
        return max(0, predicted_latency)  # Latency can't be negative

    async def _quality_monitoring_loop(self):
        """Monitor measurement quality and adjust parameters"""
        while self.running:
            try:
                await self._monitor_quality()
                await asyncio.sleep(30.0)  # Monitor every 30 seconds
            except Exception as e:
                self.logger.error(f"Error in quality monitoring loop: {e}")

    async def _monitor_quality(self):
        """Monitor and report measurement quality"""
        quality_stats = defaultdict(int)

        for source_entries in self.owl_matrix.values():
            for entry in source_entries.values():
                quality_stats[entry.quality] += 1

        total_entries = sum(quality_stats.values())
        if total_entries > 0:
            quality_distribution = {
                quality.value: count / total_entries
                for quality, count in quality_stats.items()
            }

            self.logger.debug(f"Quality distribution: {quality_distribution}")

            # Adjust measurement frequency based on quality
            poor_quality_ratio = quality_stats[MeasurementQuality.POOR] / total_entries
            if poor_quality_ratio > 0.2:  # More than 20% poor quality
                self.measurement_interval = min(2.0, self.measurement_interval * 1.1)
            elif poor_quality_ratio < 0.05:  # Less than 5% poor quality
                self.measurement_interval = max(0.5, self.measurement_interval * 0.95)

    async def _history_cleanup_loop(self):
        """Clean up old measurement history"""
        while self.running:
            try:
                await self._cleanup_old_measurements()
                await asyncio.sleep(3600)  # Cleanup every hour
            except Exception as e:
                self.logger.error(f"Error in history cleanup loop: {e}")

    async def _cleanup_old_measurements(self):
        """Remove old measurements beyond retention period"""
        cutoff_time = time.time() - (self.history_retention_hours * 3600)

        for destination, history in self.measurement_history.items():
            # Remove old measurements
            while history and history[0].timestamp < cutoff_time:
                history.popleft()

    def add_peer(self, peer_id: str):
        """Add peer for OWL measurement"""
        self.peer_nodes.add(peer_id)
        self.logger.info(f"Added OWL peer {peer_id}")

    def remove_peer(self, peer_id: str):
        """Remove peer from OWL measurement"""
        self.peer_nodes.discard(peer_id)

        # Clean up data
        if peer_id in self.measurement_history:
            del self.measurement_history[peer_id]

        if peer_id in self.prediction_models:
            del self.prediction_models[peer_id]

        for source_entries in self.owl_matrix.values():
            source_entries.pop(peer_id, None)

        self.logger.info(f"Removed OWL peer {peer_id}")

    def get_matrix(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Get current OWL matrix"""
        matrix_export = {}

        for source, destinations in self.owl_matrix.items():
            matrix_export[source] = {}
            for dest, entry in destinations.items():
                matrix_export[source][dest] = {
                    "latency_ms": entry.current_latency_ms,
                    "average_latency_ms": entry.average_latency_ms,
                    "jitter_ms": entry.jitter_ms,
                    "packet_loss_percent": entry.packet_loss_percent,
                    "quality": entry.quality.value,
                    "confidence": entry.confidence,
                    "trend": entry.trend,
                    "sample_count": entry.sample_count,
                    "last_updated": entry.last_updated
                }

        return matrix_export

    def get_metrics(self) -> Dict[str, Any]:
        """Get OWL engine metrics"""
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "measurements_sent": self.measurements_sent,
            "measurements_received": self.measurements_received,
            "matrix_updates": self.matrix_updates,
            "active_destinations": len(self.active_measurements),
            "peer_count": len(self.peer_nodes),
            "matrix_entries": sum(len(dest) for dest in self.owl_matrix.values()),
            "prediction_models": len(self.prediction_models),
            "average_prediction_accuracy": (
                statistics.mean([m.accuracy for m in self.prediction_models.values()])
                if self.prediction_models else 0.0
            ),
            "measurement_interval": self.measurement_interval
        }

    def get_status(self) -> ComponentStatus:
        """Get current OWL engine status"""
        return self.status

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        current_time = time.time()
        recent_measurements = sum(
            1 for history in self.measurement_history.values()
            for measurement in history
            if current_time - measurement.timestamp < 60  # Last minute
        )

        health_status = {
            "healthy": self.status == ComponentStatus.HEALTHY,
            "status": self.status.value,
            "recent_measurements": recent_measurements,
            "matrix_current": any(
                current_time - entry.last_updated < 60
                for dest_entries in self.owl_matrix.values()
                for entry in dest_entries.values()
            ),
            "peers_responding": len(self.active_measurements) > 0
        }

        return health_status