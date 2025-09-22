#!/usr/bin/env python3
"""
DDARP Main Application Entry Point
Starts the composite node with monitoring and data plane components.
"""

import asyncio
import os
import signal
import sys
import logging
from typing import Optional

# Import DDARP components
from src.core.composite_node import CompositeNode
from src.core.control_plane import NodeType
from src.monitoring.prometheus_exporter import DDARPPrometheusExporter
from src.monitoring.structured_logger import DDARPStructuredLogger, LogCategory
from src.monitoring.realtime_pipeline import get_pipeline

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DDARPApplication:
    """Main DDARP application orchestrator"""

    def __init__(self):
        self.node: Optional[CompositeNode] = None
        self.prometheus_exporter: Optional[DDARPPrometheusExporter] = None
        self.structured_logger: Optional[DDARPStructuredLogger] = None
        self.realtime_pipeline = None
        self.running = False

        # Get configuration from environment
        self.node_id = os.getenv('NODE_ID', 'node1')
        self.peers = os.getenv('PEERS', 'node2,node3').split(',')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        self.prometheus_port = int(os.getenv('PROMETHEUS_PORT', '9090'))
        self.websocket_port = int(os.getenv('WEBSOCKET_PORT', '8765'))
        self.api_port = int(os.getenv('API_PORT', '8000'))

        # Set log level
        numeric_level = getattr(logging, self.log_level.upper(), logging.INFO)
        logging.getLogger().setLevel(numeric_level)

    async def initialize(self):
        """Initialize all components"""
        logger.info(f"Initializing DDARP node: {self.node_id}")

        # Initialize structured logger
        self.structured_logger = DDARPStructuredLogger(
            node_id=self.node_id,
            component="main"
        )
        # Log initial system state
        logger.info(f"DDARP node {self.node_id} starting with peers: {self.peers}")

        # Initialize Prometheus exporter
        self.prometheus_exporter = DDARPPrometheusExporter(
            node_id=self.node_id
        )

        # Initialize real-time pipeline
        self.realtime_pipeline = get_pipeline()
        self.realtime_pipeline.set_prometheus_exporter(self.prometheus_exporter)

        # Initialize composite node
        self.node = CompositeNode(
            node_id=self.node_id,
            node_type="regular",
            api_port=self.api_port
        )

        # Add peers to control plane
        for peer in self.peers:
            if peer.strip():
                # Default to regular node type and generate IP based on peer name
                peer_ip = f"192.168.{100 + hash(peer.strip()) % 150}.1"
                self.node.control_plane.add_peer(peer.strip(), NodeType.REGULAR, peer_ip)

        logger.info("DDARP node initialized successfully")

    async def start(self):
        """Start all services"""
        logger.info("Starting DDARP services...")

        try:
            # Prometheus exporter is ready (no start method needed)
            if self.prometheus_exporter:
                logger.info(f"Prometheus exporter ready for metrics collection")

            # Start real-time pipeline
            if self.realtime_pipeline:
                await self.realtime_pipeline.start_server()
                logger.info(f"Real-time pipeline started on port {self.websocket_port}")

            # Start composite node
            if self.node:
                await self.node.start()
                logger.info(f"DDARP node {self.node_id} started")

            self.running = True

            logger.info(f"DDARP node {self.node_id} started successfully")

            logger.info("All DDARP services started successfully")

        except Exception as e:
            logger.error(f"Failed to start DDARP services: {e}")
            logger.error(f"DDARP node {self.node_id} startup failed: {str(e)}")
            raise

    async def stop(self):
        """Stop all services gracefully"""
        logger.info("Stopping DDARP services...")
        self.running = False

        try:
            # Stop composite node
            if self.node:
                await self.node.stop()
                logger.info("DDARP node stopped")

            # Stop real-time pipeline
            if self.realtime_pipeline:
                await self.realtime_pipeline.stop_server()
                logger.info("Real-time pipeline stopped")

            # Stop Prometheus exporter
            if self.prometheus_exporter:
                await self.prometheus_exporter.stop()
                logger.info("Prometheus exporter stopped")

            logger.info(f"DDARP node {self.node_id} stopped successfully")

            logger.info("All DDARP services stopped")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    async def run(self):
        """Main run loop"""
        await self.initialize()
        await self.start()

        # Setup signal handlers
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            asyncio.create_task(self.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Keep running until stopped
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            await self.stop()

async def main():
    """Main entry point"""
    logger.info("Starting DDARP application...")

    app = DDARPApplication()

    try:
        await app.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

    logger.info("DDARP application stopped")

if __name__ == "__main__":
    # Run the application
    asyncio.run(main())