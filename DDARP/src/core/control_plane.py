import asyncio
import time
import logging
import networkx as nx
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

class NodeType(Enum):
    REGULAR = "regular"
    BORDER = "border"

@dataclass
class TopologyNode:
    node_id: str
    node_type: NodeType
    ip_address: str
    last_seen: float

@dataclass
class PathInfo:
    destination: str
    next_hop: str
    path: List[str]
    cost: float
    last_updated: float

class ControlPlane:
    def __init__(self, node_id: str, node_type: NodeType, hysteresis_threshold: float = 0.2):
        self.node_id = node_id
        self.node_type = node_type
        self.hysteresis_threshold = hysteresis_threshold  # 20% improvement required
        self.topology = nx.Graph()
        self.routing_table: Dict[str, PathInfo] = {}
        self.topology_nodes: Dict[str, TopologyNode] = {}
        self.running = False
        self.logger = logging.getLogger(f"control_plane_{node_id}")
        
        # Add self to topology
        self._add_node_to_topology(node_id, node_type, "self")
    
    def _add_node_to_topology(self, node_id: str, node_type: NodeType, ip_address: str):
        self.topology_nodes[node_id] = TopologyNode(
            node_id=node_id,
            node_type=node_type,
            ip_address=ip_address,
            last_seen=time.time()
        )
        self.topology.add_node(node_id, type=node_type.value)
        self.logger.info(f"Added node {node_id} ({node_type.value}) to topology")
    
    def add_peer(self, node_id: str, node_type: NodeType, ip_address: str):
        if node_id not in self.topology_nodes:
            self._add_node_to_topology(node_id, node_type, ip_address)
        else:
            self.topology_nodes[node_id].last_seen = time.time()
    
    def remove_peer(self, node_id: str):
        if node_id in self.topology_nodes:
            del self.topology_nodes[node_id]
            if self.topology.has_node(node_id):
                self.topology.remove_node(node_id)
            # Remove from routing table
            if node_id in self.routing_table:
                del self.routing_table[node_id]
            self.logger.info(f"Removed node {node_id} from topology")
    
    def update_topology(self, owl_metrics: Dict[str, Dict[str, Dict]]):
        current_time = time.time()

        # Always update our own last_seen timestamp
        if self.node_id in self.topology_nodes:
            self.topology_nodes[self.node_id].last_seen = current_time

        # Update edges based on OWL metrics
        # Since each node only has its own measurements, we process all measurements
        # and create bidirectional edges based on the assumption that network links
        # have similar characteristics in both directions

        for src_node, destinations in owl_metrics.items():
            if src_node not in self.topology_nodes:
                continue

            # Update last_seen for source node to prevent staleness
            self.topology_nodes[src_node].last_seen = current_time

            for dest_node, metrics in destinations.items():
                if dest_node not in self.topology_nodes:
                    continue

                # Calculate edge weight based on latency and packet loss
                latency = metrics.get("latency_ms")
                packet_loss = metrics.get("packet_loss_percent", 100)
                last_updated = metrics.get("last_updated", 0)

                # Skip if no latency data or metrics are too old (>30 seconds)
                if latency is None or current_time - last_updated > 30:
                    if self.topology.has_edge(src_node, dest_node):
                        self.topology.remove_edge(src_node, dest_node)
                        self.logger.info(f"Removed edge {src_node} -> {dest_node} (stale/invalid metrics)")
                    continue

                # Skip if packet loss is too high (>50%)
                if packet_loss > 50:
                    if self.topology.has_edge(src_node, dest_node):
                        self.topology.remove_edge(src_node, dest_node)
                        self.logger.info(f"Removed edge {src_node} -> {dest_node} (high packet loss: {packet_loss}%)")
                    continue

                # Update last_seen for destination node with fresh metrics
                self.topology_nodes[dest_node].last_seen = current_time

                # Calculate weight: latency + penalty for packet loss
                weight = latency + (packet_loss * 10)  # 10ms penalty per % packet loss

                # Update or add edge (bidirectional for undirected graph)
                if self.topology.has_edge(src_node, dest_node):
                    current_weight = self.topology[src_node][dest_node]['weight']
                    # Only update if the new measurement is significantly different or better
                    if abs(current_weight - weight) > 0.1:  # 0.1ms threshold
                        self.topology[src_node][dest_node]['weight'] = weight
                        self.logger.info(f"Updated edge {src_node} <-> {dest_node} with weight {weight:.2f}ms")
                else:
                    self.topology.add_edge(src_node, dest_node, weight=weight)
                    self.logger.info(f"Added edge {src_node} <-> {dest_node} with weight {weight:.2f}ms")

        # Clean up edges for nodes that are no longer reachable
        self._cleanup_stale_edges(current_time)

        # Update routing table
        self._update_routing_table()

    def _cleanup_stale_edges(self, current_time: float):
        """Remove edges for nodes that haven't been seen recently."""
        edges_to_remove = []

        for src, dest in self.topology.edges():
            # Remove edge if either node is stale (except ourselves)
            src_stale = (src != self.node_id and
                        src in self.topology_nodes and
                        current_time - self.topology_nodes[src].last_seen > 60)
            dest_stale = (dest != self.node_id and
                         dest in self.topology_nodes and
                         current_time - self.topology_nodes[dest].last_seen > 60)

            if src_stale or dest_stale:
                edges_to_remove.append((src, dest))

        for src, dest in edges_to_remove:
            self.topology.remove_edge(src, dest)
            self.logger.info(f"Removed stale edge {src} <-> {dest}")
    
    def _update_routing_table(self):
        if not self.topology.has_node(self.node_id):
            return
        
        try:
            # Calculate shortest paths using Dijkstra
            paths = nx.single_source_dijkstra_path(self.topology, self.node_id, weight='weight')
            costs = nx.single_source_dijkstra_path_length(self.topology, self.node_id, weight='weight')
            
            current_time = time.time()
            
            for destination, path in paths.items():
                if destination == self.node_id or len(path) < 2:
                    continue
                
                next_hop = path[1]
                cost = costs[destination]
                
                # Apply hysteresis: only update if new path is significantly better
                should_update = True
                if destination in self.routing_table:
                    current_cost = self.routing_table[destination].cost
                    current_next_hop = self.routing_table[destination].next_hop
                    route_age = current_time - self.routing_table[destination].last_updated

                    # Always update if route is older than 30 seconds (refresh)
                    if route_age > 30:
                        should_update = True
                    # Update if current next hop is no longer available
                    elif not self.topology.has_edge(self.node_id, current_next_hop):
                        should_update = True
                    # Apply hysteresis for stable routes
                    else:
                        improvement = (current_cost - cost) / current_cost if current_cost > 0 else 0
                        should_update = improvement >= self.hysteresis_threshold

                if not should_update:
                    continue  # Keep current path
                
                # Update routing table entry
                self.routing_table[destination] = PathInfo(
                    destination=destination,
                    next_hop=next_hop,
                    path=path,
                    cost=cost,
                    last_updated=current_time
                )
                
                self.logger.debug(f"Updated route to {destination}: {' -> '.join(path)} (cost: {cost:.2f})")
        
        except nx.NetworkXNoPath:
            self.logger.warning("No path found for some destinations")
        except Exception as e:
            self.logger.error(f"Error updating routing table: {e}")
    
    def get_next_hop(self, destination: str) -> Optional[str]:
        if destination in self.routing_table:
            path_info = self.routing_table[destination]
            # Check if route is still fresh (< 120 seconds old)
            if time.time() - path_info.last_updated < 120:
                return path_info.next_hop
        return None
    
    def get_path_to_destination(self, destination: str) -> Optional[List[str]]:
        if destination in self.routing_table:
            path_info = self.routing_table[destination]
            # Check if route is still fresh (< 120 seconds old)
            if time.time() - path_info.last_updated < 120:
                return path_info.path
        return None
    
    def get_routing_table(self) -> Dict[str, Dict]:
        table = {}
        current_time = time.time()

        for dest, path_info in self.routing_table.items():
            # Only include fresh routes (< 120 seconds old)
            if current_time - path_info.last_updated < 120:
                table[dest] = {
                    "next_hop": path_info.next_hop,
                    "path": path_info.path,
                    "cost": path_info.cost,
                    "last_updated": path_info.last_updated
                }

        return table
    
    def get_topology_info(self) -> Dict:
        nodes = []
        edges = []
        
        # Get nodes
        for node_id, node_info in self.topology_nodes.items():
            nodes.append({
                "id": node_id,
                "type": node_info.node_type.value,
                "ip_address": node_info.ip_address,
                "last_seen": node_info.last_seen
            })
        
        # Get edges
        for src, dest, data in self.topology.edges(data=True):
            edges.append({
                "source": src,
                "destination": dest,
                "weight": data.get("weight", 0)
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges)
        }
    
    def get_border_nodes(self) -> List[str]:
        return [
            node_id for node_id, node_info in self.topology_nodes.items()
            if node_info.node_type == NodeType.BORDER
        ]
    
    def is_reachable(self, destination: str) -> bool:
        return destination in self.routing_table and \
               time.time() - self.routing_table[destination].last_updated < 120
    
    async def start(self):
        self.running = True
        self.logger.info("Control Plane started")
        
        # Start topology update loop
        asyncio.create_task(self._topology_update_loop())
    
    async def stop(self):
        self.running = False
        self.logger.info("Control Plane stopped")
    
    async def _topology_update_loop(self):
        while self.running:
            # Clean up stale nodes (not seen for >120 seconds)
            current_time = time.time()
            stale_nodes = [
                node_id for node_id, node_info in self.topology_nodes.items()
                if current_time - node_info.last_seen > 120 and node_id != self.node_id
            ]
            
            for node_id in stale_nodes:
                self.remove_peer(node_id)
            
            await asyncio.sleep(5.0)  # Update every 5 seconds