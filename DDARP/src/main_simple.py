#!/usr/bin/env python3
"""
DDARP Simple Main Application Entry Point
Basic startup for testing without full monitoring components.
"""

import asyncio
import os
import signal
import sys
import logging
from typing import Optional

# Import minimal DDARP components
from src.core.composite_node import CompositeNode

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DDARPSimpleApplication:
    """Simple DDARP application for testing"""

    def __init__(self):
        self.node: Optional[CompositeNode] = None
        self.running = False

        # Get configuration from environment
        self.node_id = os.getenv('NODE_ID', 'node1')
        self.peers = os.getenv('PEERS', 'node2,node3').split(',')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')

        # Set log level
        numeric_level = getattr(logging, self.log_level.upper(), logging.INFO)
        logging.getLogger().setLevel(numeric_level)

    async def initialize(self):
        """Initialize basic components"""
        logger.info(f"Initializing DDARP node: {self.node_id}")

        # Initialize basic composite node
        self.node = CompositeNode(
            node_id=self.node_id,
            node_type="regular"
        )

        logger.info("DDARP node initialized successfully")

    async def start(self):
        """Start basic services"""
        logger.info("Starting DDARP services...")

        try:
            # Start composite node
            if self.node:
                # For now, just log that we would start it
                logger.info(f"DDARP node {self.node_id} would start here")

            self.running = True
            logger.info("All DDARP services started successfully")

        except Exception as e:
            logger.error(f"Failed to start DDARP services: {e}")
            raise

    async def stop(self):
        """Stop all services gracefully"""
        logger.info("Stopping DDARP services...")
        self.running = False

        try:
            # Stop composite node
            if self.node:
                logger.info("DDARP node stopped")

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
                logger.info(f"DDARP node {self.node_id} is running...")
                await asyncio.sleep(30)  # Log every 30 seconds
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            await self.stop()

async def main():
    """Main entry point"""
    logger.info("Starting DDARP simple application...")

    app = DDARPSimpleApplication()

    try:
        await app.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

    logger.info("DDARP simple application stopped")

if __name__ == "__main__":
    # Run the application
    asyncio.run(main())