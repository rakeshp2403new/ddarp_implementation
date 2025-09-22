"""
Real-time data pipeline for DDARP monitoring with WebSocket streaming.
Provides live metrics updates to connected clients.
"""

import asyncio
import json
import websockets
from websockets.server import WebSocketServerProtocol
from typing import Dict, Set, Any, Optional
import logging
from datetime import datetime, timezone
import threading
import time
from collections import defaultdict, deque
import uuid

from .prometheus_exporter import DDARPPrometheusExporter
from .structured_logger import DDARPStructuredLogger, LogCategory

class RealtimeDataPipeline:
    """Real-time data pipeline for streaming DDARP metrics via WebSocket."""

    def __init__(self, port: int = 8765, buffer_size: int = 1000):
        self.port = port
        self.buffer_size = buffer_size

        # Connected clients
        self.clients: Set[WebSocketServerProtocol] = set()

        # Data buffers for different metric types
        self.metric_buffers: Dict[str, deque] = {
            'owl_measurements': deque(maxlen=buffer_size),
            'path_computations': deque(maxlen=buffer_size),
            'bgp_events': deque(maxlen=buffer_size),
            'tunnel_events': deque(maxlen=buffer_size),
            'system_health': deque(maxlen=buffer_size),
            'topology_changes': deque(maxlen=buffer_size)
        }

        # Subscription management
        self.client_subscriptions: Dict[WebSocketServerProtocol, Set[str]] = defaultdict(set)

        # Pipeline state
        self.server = None
        self.running = False
        self.metrics_thread = None

        # Metrics collection
        self.prometheus_exporter: Optional[DDARPPrometheusExporter] = None
        self.logger = DDARPStructuredLogger(
            node_id="realtime-pipeline",
            component="realtime"
        )

        # Performance tracking
        self.stats = {
            'messages_sent': 0,
            'clients_connected': 0,
            'data_points_processed': 0,
            'last_update': None
        }

    def set_prometheus_exporter(self, exporter: DDARPPrometheusExporter):
        """Set the Prometheus exporter for metrics collection."""
        self.prometheus_exporter = exporter

    async def register_client(self, websocket: WebSocketServerProtocol):
        """Register a new WebSocket client."""
        self.clients.add(websocket)
        self.client_subscriptions[websocket] = set()
        self.stats['clients_connected'] = len(self.clients)

        # Send welcome message with available subscriptions
        welcome_msg = {
            'type': 'welcome',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'available_subscriptions': list(self.metric_buffers.keys()),
            'buffer_size': self.buffer_size
        }
        await websocket.send(json.dumps(welcome_msg))

        # Log client connection using standard logging
        logging.info(f"WebSocket client connected from {websocket.remote_address}")

    async def unregister_client(self, websocket: WebSocketServerProtocol):
        """Unregister a WebSocket client."""
        self.clients.discard(websocket)
        self.client_subscriptions.pop(websocket, None)
        self.stats['clients_connected'] = len(self.clients)

        # Log client disconnection using standard logging
        logging.info(f"WebSocket client disconnected from {websocket.remote_address}")

    async def handle_client_message(self, websocket: WebSocketServerProtocol, message: str):
        """Handle incoming messages from WebSocket clients."""
        try:
            data = json.loads(message)
            msg_type = data.get('type')

            if msg_type == 'subscribe':
                # Handle subscription request
                subscriptions = data.get('subscriptions', [])
                valid_subscriptions = [s for s in subscriptions if s in self.metric_buffers]
                self.client_subscriptions[websocket] = set(valid_subscriptions)

                # Send historical data for subscribed channels
                for subscription in valid_subscriptions:
                    buffer = self.metric_buffers[subscription]
                    if buffer:
                        historical_data = {
                            'type': 'historical',
                            'channel': subscription,
                            'data': list(buffer)
                        }
                        await websocket.send(json.dumps(historical_data))

                # Confirm subscription
                response = {
                    'type': 'subscription_confirmed',
                    'subscriptions': valid_subscriptions,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                await websocket.send(json.dumps(response))

            elif msg_type == 'ping':
                # Handle ping/pong for keepalive
                pong = {
                    'type': 'pong',
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                await websocket.send(json.dumps(pong))

            elif msg_type == 'get_stats':
                # Send pipeline statistics
                stats_response = {
                    'type': 'stats',
                    'data': self.stats.copy(),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                await websocket.send(json.dumps(stats_response))

        except json.JSONDecodeError:
            error_msg = {
                'type': 'error',
                'message': 'Invalid JSON format',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            await websocket.send(json.dumps(error_msg))

    async def client_handler(self, websocket: WebSocketServerProtocol, path: str):
        """Handle WebSocket client connections."""
        await self.register_client(websocket)
        try:
            async for message in websocket:
                await self.handle_client_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister_client(websocket)

    async def broadcast_to_subscribers(self, channel: str, data: Dict[str, Any]):
        """Broadcast data to all clients subscribed to a channel."""
        if not self.clients:
            return

        message = {
            'type': 'data',
            'channel': channel,
            'data': data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        message_json = json.dumps(message)

        # Send to subscribed clients
        disconnected_clients = set()
        for client in self.clients:
            if channel in self.client_subscriptions[client]:
                try:
                    await client.send(message_json)
                    self.stats['messages_sent'] += 1
                except websockets.exceptions.ConnectionClosed:
                    disconnected_clients.add(client)

        # Clean up disconnected clients
        for client in disconnected_clients:
            await self.unregister_client(client)

    def add_owl_measurement(self, node_id: str, peer_id: str, latency: float,
                           jitter: float, packet_loss: float):
        """Add OWL measurement to the pipeline."""
        data = {
            'node_id': node_id,
            'peer_id': peer_id,
            'latency_ms': latency,
            'jitter_ms': jitter,
            'packet_loss_ratio': packet_loss,
            'measurement_id': str(uuid.uuid4())
        }

        self.metric_buffers['owl_measurements'].append(data)
        self.stats['data_points_processed'] += 1
        self.stats['last_update'] = datetime.now(timezone.utc).isoformat()

        # Schedule broadcast
        if self.running:
            asyncio.create_task(self.broadcast_to_subscribers('owl_measurements', data))

    def add_path_computation(self, node_id: str, destination: str,
                           duration_ms: float, algorithm: str, path_length: int):
        """Add path computation event to the pipeline."""
        data = {
            'node_id': node_id,
            'destination': destination,
            'computation_duration_ms': duration_ms,
            'algorithm': algorithm,
            'path_length': path_length,
            'computation_id': str(uuid.uuid4())
        }

        self.metric_buffers['path_computations'].append(data)
        self.stats['data_points_processed'] += 1
        self.stats['last_update'] = datetime.now(timezone.utc).isoformat()

        if self.running:
            asyncio.create_task(self.broadcast_to_subscribers('path_computations', data))

    def add_bgp_event(self, node_id: str, event_type: str, neighbor: str,
                     session_status: str, routes_count: int = 0):
        """Add BGP event to the pipeline."""
        data = {
            'node_id': node_id,
            'event_type': event_type,
            'neighbor': neighbor,
            'session_status': session_status,
            'routes_count': routes_count,
            'event_id': str(uuid.uuid4())
        }

        self.metric_buffers['bgp_events'].append(data)
        self.stats['data_points_processed'] += 1
        self.stats['last_update'] = datetime.now(timezone.utc).isoformat()

        if self.running:
            asyncio.create_task(self.broadcast_to_subscribers('bgp_events', data))

    def add_tunnel_event(self, node_id: str, peer_id: str, event_type: str,
                        tunnel_status: str, interface: str = ""):
        """Add tunnel event to the pipeline."""
        data = {
            'node_id': node_id,
            'peer_id': peer_id,
            'event_type': event_type,
            'tunnel_status': tunnel_status,
            'interface': interface,
            'event_id': str(uuid.uuid4())
        }

        self.metric_buffers['tunnel_events'].append(data)
        self.stats['data_points_processed'] += 1
        self.stats['last_update'] = datetime.now(timezone.utc).isoformat()

        if self.running:
            asyncio.create_task(self.broadcast_to_subscribers('tunnel_events', data))

    def add_system_health(self, node_id: str, cpu_percent: float,
                         memory_percent: float, disk_percent: float):
        """Add system health metrics to the pipeline."""
        data = {
            'node_id': node_id,
            'cpu_usage_percent': cpu_percent,
            'memory_usage_percent': memory_percent,
            'disk_usage_percent': disk_percent,
            'health_id': str(uuid.uuid4())
        }

        self.metric_buffers['system_health'].append(data)
        self.stats['data_points_processed'] += 1
        self.stats['last_update'] = datetime.now(timezone.utc).isoformat()

        if self.running:
            asyncio.create_task(self.broadcast_to_subscribers('system_health', data))

    def add_topology_change(self, node_id: str, change_type: str,
                           affected_peer: str, new_status: str):
        """Add topology change event to the pipeline."""
        data = {
            'node_id': node_id,
            'change_type': change_type,
            'affected_peer': affected_peer,
            'new_status': new_status,
            'change_id': str(uuid.uuid4())
        }

        self.metric_buffers['topology_changes'].append(data)
        self.stats['data_points_processed'] += 1
        self.stats['last_update'] = datetime.now(timezone.utc).isoformat()

        if self.running:
            asyncio.create_task(self.broadcast_to_subscribers('topology_changes', data))

    def metrics_collector_thread(self):
        """Background thread for collecting system metrics."""
        while self.running:
            try:
                # Collect system health metrics if exporter is available
                if self.prometheus_exporter:
                    # This would integrate with actual system monitoring
                    # For now, we'll simulate with periodic health checks
                    pass

                time.sleep(5)  # Collect every 5 seconds

            except Exception as e:
                # Log error using standard logging
                logging.error(f"Error in metrics collector thread: {str(e)}")

    async def start_server(self):
        """Start the WebSocket server and data pipeline."""
        self.running = True

        # Start metrics collection thread
        self.metrics_thread = threading.Thread(
            target=self.metrics_collector_thread,
            daemon=True
        )
        self.metrics_thread.start()

        # Start WebSocket server
        self.server = await websockets.serve(
            self.client_handler,
            "0.0.0.0",
            self.port
        )

        # Log startup using standard logging
        logging.info(f"Real-time data pipeline started on port {self.port} with buffer size {self.buffer_size}")

        print(f"Real-time data pipeline running on port {self.port}")

    async def stop_server(self):
        """Stop the WebSocket server and data pipeline."""
        self.running = False

        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Close all client connections
        if self.clients:
            await asyncio.gather(
                *[client.close() for client in self.clients],
                return_exceptions=True
            )

        # Log shutdown using standard logging
        logging.info(f"Real-time data pipeline stopped. Final stats: {self.stats}")

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get current pipeline statistics."""
        return {
            'running': self.running,
            'connected_clients': len(self.clients),
            'total_subscriptions': sum(len(subs) for subs in self.client_subscriptions.values()),
            'buffer_utilization': {
                channel: len(buffer) for channel, buffer in self.metric_buffers.items()
            },
            'performance': self.stats.copy()
        }

# Global pipeline instance
_pipeline_instance: Optional[RealtimeDataPipeline] = None

def get_pipeline() -> RealtimeDataPipeline:
    """Get the global pipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = RealtimeDataPipeline()
    return _pipeline_instance

def initialize_pipeline(port: int = 8765, buffer_size: int = 1000) -> RealtimeDataPipeline:
    """Initialize the global pipeline instance."""
    global _pipeline_instance
    _pipeline_instance = RealtimeDataPipeline(port, buffer_size)
    return _pipeline_instance

async def main():
    """Main entry point for running the pipeline standalone."""
    pipeline = get_pipeline()
    await pipeline.start_server()

    try:
        # Keep the server running
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        await pipeline.stop_server()

if __name__ == "__main__":
    asyncio.run(main())