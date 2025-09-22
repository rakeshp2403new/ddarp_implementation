import asyncio
import time
import json
import hmac
import hashlib
import logging
import statistics
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict, deque

@dataclass
class PingResult:
    latency: float
    timestamp: float
    lost: bool = False

@dataclass
class OwlMetrics:
    latency: Optional[float] = None
    jitter: Optional[float] = None
    packet_loss: float = 0.0
    last_updated: float = 0.0

class OwlEngine:
    def __init__(self, node_id: str, port: int, secret_key: str):
        self.node_id = node_id
        self.port = port
        self.secret_key = secret_key.encode()
        self.peers: Dict[str, str] = {}  # node_id -> ip_address
        self.ping_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.metrics_matrix: Dict[str, Dict[str, OwlMetrics]] = {}
        self.transport = None
        self.running = False
        self.logger = logging.getLogger(f"owl_engine_{node_id}")
        
    def add_peer(self, node_id: str, ip_address: str):
        self.peers[node_id] = ip_address
        if self.node_id not in self.metrics_matrix:
            self.metrics_matrix[self.node_id] = {}
        self.metrics_matrix[self.node_id][node_id] = OwlMetrics()
        self.logger.info(f"Added peer {node_id} at {ip_address}")
    
    def remove_peer(self, node_id: str):
        if node_id in self.peers:
            del self.peers[node_id]
            if self.node_id in self.metrics_matrix and node_id in self.metrics_matrix[self.node_id]:
                del self.metrics_matrix[self.node_id][node_id]
            self.logger.info(f"Removed peer {node_id}")
    
    def _create_ping_message(self, dest_node_id: str, sequence: int) -> bytes:
        timestamp = time.time()
        payload = {
            "type": "ping",
            "src": self.node_id,
            "dest": dest_node_id,
            "seq": sequence,
            "timestamp": timestamp
        }
        message = json.dumps(payload).encode()
        signature = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()
        return json.dumps({"payload": payload, "signature": signature}).encode()
    
    def _create_pong_message(self, ping_payload: Dict) -> bytes:
        payload = {
            "type": "pong",
            "src": self.node_id,
            "dest": ping_payload["src"],
            "seq": ping_payload["seq"],
            "original_timestamp": ping_payload["timestamp"],
            "pong_timestamp": time.time()
        }
        message = json.dumps(payload).encode()
        signature = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()
        return json.dumps({"payload": payload, "signature": signature}).encode()
    
    def _verify_signature(self, message: Dict) -> bool:
        payload = message.get("payload", {})
        signature = message.get("signature", "")
        expected_signature = hmac.new(
            self.secret_key, 
            json.dumps(payload).encode(), 
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)
    
    def _calculate_metrics(self, node_id: str) -> OwlMetrics:
        history = self.ping_history[node_id]
        if not history:
            return OwlMetrics()
        
        recent_pings = [p for p in history if time.time() - p.timestamp < 30]
        if not recent_pings:
            return OwlMetrics()
        
        latencies = [p.latency for p in recent_pings if not p.lost]
        total_pings = len(recent_pings)
        lost_pings = sum(1 for p in recent_pings if p.lost)
        
        metrics = OwlMetrics()
        metrics.packet_loss = (lost_pings / total_pings) * 100 if total_pings > 0 else 0
        metrics.last_updated = time.time()
        
        if latencies:
            metrics.latency = statistics.mean(latencies)
            if len(latencies) > 1:
                metrics.jitter = statistics.stdev(latencies)
            else:
                metrics.jitter = 0.0
        
        return metrics
    
    def get_metrics_matrix(self) -> Dict[str, Dict[str, Dict]]:
        matrix = {}
        for src_node in self.metrics_matrix:
            matrix[src_node] = {}
            for dest_node in self.metrics_matrix[src_node]:
                metrics = self.metrics_matrix[src_node][dest_node]
                matrix[src_node][dest_node] = {
                    "latency_ms": metrics.latency,
                    "jitter_ms": metrics.jitter,
                    "packet_loss_percent": metrics.packet_loss,
                    "last_updated": metrics.last_updated
                }
        return matrix
    
    class OwlProtocol:
        def __init__(self, engine):
            self.engine = engine
            self.pending_pings: Dict[Tuple[str, int], float] = {}
        
        def connection_made(self, transport):
            self.transport = transport
            self.engine.transport = transport
        
        def datagram_received(self, data, addr):
            try:
                message = json.loads(data.decode())
                if not self.engine._verify_signature(message):
                    self.engine.logger.warning(f"Invalid signature from {addr}")
                    return
                
                payload = message["payload"]
                msg_type = payload.get("type")
                
                if msg_type == "ping":
                    self._handle_ping(payload, addr)
                elif msg_type == "pong":
                    self._handle_pong(payload, addr)
                    
            except (json.JSONDecodeError, KeyError) as e:
                self.engine.logger.error(f"Invalid message from {addr}: {e}")
        
        def _handle_ping(self, payload: Dict, addr):
            src_node = payload.get("src")
            if src_node and src_node in self.engine.peers:
                pong_message = self.engine._create_pong_message(payload)
                self.transport.sendto(pong_message, addr)
        
        def _handle_pong(self, payload: Dict, addr):
            src_node = payload.get("src")
            seq = payload.get("seq")
            original_timestamp = payload.get("original_timestamp")
            
            if not all([src_node, seq is not None, original_timestamp]):
                return
            
            ping_key = (src_node, seq)
            if ping_key in self.pending_pings:
                send_time = self.pending_pings.pop(ping_key)
                latency = (time.time() - send_time) * 1000  # Convert to ms
                
                result = PingResult(latency=latency, timestamp=time.time())
                self.engine.ping_history[src_node].append(result)
                
                # Update metrics
                metrics = self.engine._calculate_metrics(src_node)
                if self.engine.node_id not in self.engine.metrics_matrix:
                    self.engine.metrics_matrix[self.engine.node_id] = {}
                self.engine.metrics_matrix[self.engine.node_id][src_node] = metrics
    
    async def start(self):
        loop = asyncio.get_event_loop()
        self.transport, _ = await loop.create_datagram_endpoint(
            lambda: self.OwlProtocol(self),
            local_addr=('0.0.0.0', self.port)
        )
        self.running = True
        self.logger.info(f"OWL Engine started on port {self.port}")
        
        # Start ping loop
        asyncio.create_task(self._ping_loop())
    
    async def stop(self):
        self.running = False
        if self.transport:
            self.transport.close()
        self.logger.info("OWL Engine stopped")
    
    async def _ping_loop(self):
        sequence = 0
        while self.running:
            for node_id, ip_address in self.peers.items():
                await self._send_ping(node_id, ip_address, sequence)
            
            sequence += 1
            await asyncio.sleep(1.0)  # 1Hz ping rate
    
    async def _send_ping(self, node_id: str, ip_address: str, sequence: int):
        if not self.transport:
            return
        
        try:
            ping_message = self._create_ping_message(node_id, sequence)
            send_time = time.time()
            self.transport.sendto(ping_message, (ip_address, self.port))
            
            # Track pending ping with timeout
            ping_key = (node_id, sequence)
            protocol = self.transport.get_protocol()
            protocol.pending_pings[ping_key] = send_time
            
            # Schedule timeout cleanup
            asyncio.create_task(self._cleanup_ping(ping_key, send_time))
            
        except Exception as e:
            self.logger.error(f"Failed to send ping to {node_id}: {e}")
    
    async def _cleanup_ping(self, ping_key: Tuple[str, int], send_time: float):
        await asyncio.sleep(5.0)  # 5 second timeout
        
        protocol = self.transport.get_protocol()
        if ping_key in protocol.pending_pings:
            protocol.pending_pings.pop(ping_key)
            
            # Record as lost packet
            node_id = ping_key[0]
            result = PingResult(latency=0, timestamp=time.time(), lost=True)
            self.ping_history[node_id].append(result)
            
            # Update metrics
            metrics = self._calculate_metrics(node_id)
            if self.node_id not in self.metrics_matrix:
                self.metrics_matrix[self.node_id] = {}
            self.metrics_matrix[self.node_id][node_id] = metrics