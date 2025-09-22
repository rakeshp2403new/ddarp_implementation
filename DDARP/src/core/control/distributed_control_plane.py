"""
DDARP Distributed Control Plane

Enhanced control plane with algorithm selection, distributed decision making,
and consensus mechanisms for the DDARP composite node architecture.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib

from ..monitoring.enhanced_prometheus_exporter import ComponentStatus


class RoutingAlgorithm(Enum):
    """Available routing algorithms"""
    DIJKSTRA = "dijkstra"
    BELLMAN_FORD = "bellman_ford"
    FLOYD_WARSHALL = "floyd_warshall"
    A_STAR = "a_star"
    GENETIC_ALGORITHM = "genetic"
    MACHINE_LEARNING = "ml_based"
    HYBRID = "hybrid"


class ConsensusState(Enum):
    """Consensus mechanism states"""
    IDLE = "idle"
    PROPOSING = "proposing"
    VOTING = "voting"
    COMMITTED = "committed"
    ABORTED = "aborted"


@dataclass
class AlgorithmMetrics:
    """Performance metrics for routing algorithms"""
    algorithm: RoutingAlgorithm
    execution_time_ms: float
    convergence_iterations: int
    path_quality_score: float
    memory_usage_mb: float
    success_rate: float
    last_execution: float = field(default_factory=time.time)


@dataclass
class RoutingProposal:
    """Routing decision proposal for consensus"""
    proposal_id: str
    proposer_node: str
    algorithm: RoutingAlgorithm
    routing_table: Dict[str, Any]
    timestamp: float
    votes: Dict[str, bool] = field(default_factory=dict)
    committed: bool = False


@dataclass
class TopologySnapshot:
    """Snapshot of network topology"""
    timestamp: float
    nodes: Set[str]
    edges: Dict[str, Dict[str, float]]  # source -> dest -> metric
    owl_metrics: Dict[str, Dict[str, Dict[str, float]]]  # src -> dest -> metrics
    version: int = 1


class DistributedControlPlane:
    """Enhanced distributed control plane with algorithm selection"""

    def __init__(self, node_id: str, config: Optional[Dict[str, Any]] = None):
        self.node_id = node_id
        self.config = config or {}
        self.logger = logging.getLogger(f"distributed_control_plane_{node_id}")

        # Component state
        self.running = False
        self.status = ComponentStatus.STOPPED

        # Topology and routing
        self.topology_snapshot: Optional[TopologySnapshot] = None
        self.routing_table: Dict[str, Dict[str, Any]] = {}
        self.algorithm_metrics: Dict[RoutingAlgorithm, AlgorithmMetrics] = {}

        # Distributed consensus
        self.consensus_state = ConsensusState.IDLE
        self.active_proposals: Dict[str, RoutingProposal] = {}
        self.peer_nodes: Set[str] = set()
        self.leader_node: Optional[str] = None

        # Algorithm selection
        self.available_algorithms = list(RoutingAlgorithm)
        self.current_algorithm = RoutingAlgorithm.DIJKSTRA
        self.algorithm_selection_enabled = True
        self.performance_history: List[AlgorithmMetrics] = []

        # Configuration
        self.consensus_timeout = 30.0  # seconds
        self.topology_sync_interval = 10.0  # seconds
        self.algorithm_evaluation_interval = 60.0  # seconds
        self.max_proposal_age = 300.0  # seconds

        # Caching
        self.routing_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}
        self.cache_ttl = 30.0  # seconds

        self._init_algorithm_metrics()

        self.logger.info(f"Distributed Control Plane initialized for node {node_id}")

    def _init_algorithm_metrics(self):
        """Initialize algorithm performance metrics"""
        for algorithm in RoutingAlgorithm:
            self.algorithm_metrics[algorithm] = AlgorithmMetrics(
                algorithm=algorithm,
                execution_time_ms=0.0,
                convergence_iterations=0,
                path_quality_score=0.0,
                memory_usage_mb=0.0,
                success_rate=1.0
            )

    async def start(self):
        """Start the distributed control plane"""
        self.logger.info("Starting Distributed Control Plane")
        self.status = ComponentStatus.STARTING

        try:
            # Initialize topology
            self.topology_snapshot = TopologySnapshot(
                timestamp=time.time(),
                nodes={self.node_id},
                edges={},
                owl_metrics={}
            )

            # Start background tasks
            asyncio.create_task(self._topology_sync_loop())
            asyncio.create_task(self._consensus_manager_loop())
            asyncio.create_task(self._algorithm_evaluation_loop())
            asyncio.create_task(self._cache_cleanup_loop())

            # Start leader election
            asyncio.create_task(self._leader_election_loop())

            self.running = True
            self.status = ComponentStatus.HEALTHY

            self.logger.info("Distributed Control Plane started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start Distributed Control Plane: {e}")
            self.status = ComponentStatus.ERROR
            raise

    async def stop(self):
        """Stop the distributed control plane"""
        self.logger.info("Stopping Distributed Control Plane")
        self.status = ComponentStatus.STOPPING

        self.running = False
        self.status = ComponentStatus.STOPPED

        self.logger.info("Distributed Control Plane stopped")

    async def _topology_sync_loop(self):
        """Synchronize topology with peer nodes"""
        while self.running:
            try:
                await self._synchronize_topology()
                await asyncio.sleep(self.topology_sync_interval)
            except Exception as e:
                self.logger.error(f"Error in topology sync loop: {e}")

    async def _synchronize_topology(self):
        """Synchronize topology information with peers"""
        if not self.peer_nodes:
            return

        # Prepare topology update message
        topology_update = {
            "node_id": self.node_id,
            "timestamp": time.time(),
            "topology": {
                "nodes": list(self.topology_snapshot.nodes),
                "edges": self.topology_snapshot.edges,
                "version": self.topology_snapshot.version
            }
        }

        # Send to all peers (placeholder - would use actual networking)
        for peer in self.peer_nodes:
            await self._send_to_peer(peer, "topology_sync", topology_update)

    async def _consensus_manager_loop(self):
        """Manage consensus proposals and voting"""
        while self.running:
            try:
                await self._process_consensus()
                await asyncio.sleep(1.0)  # Check frequently
            except Exception as e:
                self.logger.error(f"Error in consensus manager loop: {e}")

    async def _process_consensus(self):
        """Process active consensus proposals"""
        current_time = time.time()

        # Clean up old proposals
        expired_proposals = [
            proposal_id for proposal_id, proposal in self.active_proposals.items()
            if current_time - proposal.timestamp > self.max_proposal_age
        ]

        for proposal_id in expired_proposals:
            del self.active_proposals[proposal_id]
            self.logger.debug(f"Expired proposal {proposal_id}")

        # Process active proposals
        for proposal_id, proposal in self.active_proposals.items():
            if not proposal.committed and self._has_consensus(proposal):
                await self._commit_proposal(proposal)

    def _has_consensus(self, proposal: RoutingProposal) -> bool:
        """Check if proposal has achieved consensus"""
        total_peers = len(self.peer_nodes) + 1  # Include self
        votes_needed = (total_peers // 2) + 1  # Simple majority

        positive_votes = sum(1 for vote in proposal.votes.values() if vote)
        return positive_votes >= votes_needed

    async def _commit_proposal(self, proposal: RoutingProposal):
        """Commit a consensus proposal"""
        try:
            # Update routing table
            self.routing_table = proposal.routing_table.copy()
            proposal.committed = True

            # Update current algorithm
            self.current_algorithm = proposal.algorithm

            # Clear cache
            self.routing_cache.clear()

            self.logger.info(
                f"Committed proposal {proposal.proposal_id} "
                f"using algorithm {proposal.algorithm.value}"
            )

            # Notify peers of commitment
            commit_message = {
                "proposal_id": proposal.proposal_id,
                "committed": True,
                "timestamp": time.time()
            }

            for peer in self.peer_nodes:
                await self._send_to_peer(peer, "proposal_commit", commit_message)

        except Exception as e:
            self.logger.error(f"Error committing proposal {proposal.proposal_id}: {e}")

    async def _algorithm_evaluation_loop(self):
        """Evaluate algorithm performance and select optimal one"""
        while self.running:
            try:
                if self.algorithm_selection_enabled:
                    await self._evaluate_algorithms()
                await asyncio.sleep(self.algorithm_evaluation_interval)
            except Exception as e:
                self.logger.error(f"Error in algorithm evaluation loop: {e}")

    async def _evaluate_algorithms(self):
        """Evaluate and potentially switch routing algorithms"""
        if not self.topology_snapshot or len(self.topology_snapshot.nodes) < 2:
            return

        # Test all available algorithms
        algorithm_scores = {}

        for algorithm in self.available_algorithms:
            try:
                score = await self._benchmark_algorithm(algorithm)
                algorithm_scores[algorithm] = score
            except Exception as e:
                self.logger.warning(f"Error benchmarking {algorithm.value}: {e}")
                algorithm_scores[algorithm] = 0.0

        # Select best algorithm
        if algorithm_scores:
            best_algorithm = max(algorithm_scores.keys(), key=lambda a: algorithm_scores[a])

            # Switch if significantly better
            current_score = algorithm_scores.get(self.current_algorithm, 0.0)
            best_score = algorithm_scores[best_algorithm]

            if best_score > current_score * 1.1:  # 10% improvement threshold
                await self._propose_algorithm_change(best_algorithm)

    async def _benchmark_algorithm(self, algorithm: RoutingAlgorithm) -> float:
        """Benchmark algorithm performance"""
        start_time = time.time()

        try:
            # Run algorithm on current topology
            routing_result = await self._run_routing_algorithm(algorithm)

            # Calculate performance metrics
            execution_time = (time.time() - start_time) * 1000  # ms
            path_quality = self._calculate_path_quality(routing_result)

            # Update metrics
            metrics = self.algorithm_metrics[algorithm]
            metrics.execution_time_ms = execution_time
            metrics.path_quality_score = path_quality
            metrics.last_execution = time.time()

            # Calculate composite score
            # Lower execution time and higher path quality is better
            score = path_quality / (1 + execution_time / 1000)

            return score

        except Exception as e:
            self.logger.error(f"Error benchmarking {algorithm.value}: {e}")
            return 0.0

    async def _run_routing_algorithm(self, algorithm: RoutingAlgorithm) -> Dict[str, Any]:
        """Run specific routing algorithm"""
        if algorithm == RoutingAlgorithm.DIJKSTRA:
            return await self._dijkstra_algorithm()
        elif algorithm == RoutingAlgorithm.BELLMAN_FORD:
            return await self._bellman_ford_algorithm()
        elif algorithm == RoutingAlgorithm.FLOYD_WARSHALL:
            return await self._floyd_warshall_algorithm()
        elif algorithm == RoutingAlgorithm.A_STAR:
            return await self._a_star_algorithm()
        elif algorithm == RoutingAlgorithm.GENETIC_ALGORITHM:
            return await self._genetic_algorithm()
        elif algorithm == RoutingAlgorithm.MACHINE_LEARNING:
            return await self._ml_based_algorithm()
        elif algorithm == RoutingAlgorithm.HYBRID:
            return await self._hybrid_algorithm()
        else:
            return await self._dijkstra_algorithm()  # Default fallback

    async def _dijkstra_algorithm(self) -> Dict[str, Any]:
        """Dijkstra's shortest path algorithm"""
        # Simplified implementation
        routing_table = {}
        nodes = self.topology_snapshot.nodes
        edges = self.topology_snapshot.edges

        for destination in nodes:
            if destination != self.node_id:
                # Find shortest path
                path, cost = self._find_shortest_path(self.node_id, destination, edges)
                routing_table[destination] = {
                    "path": path,
                    "cost": cost,
                    "next_hop": path[1] if len(path) > 1 else None
                }

        return routing_table

    async def _bellman_ford_algorithm(self) -> Dict[str, Any]:
        """Bellman-Ford algorithm for shortest paths"""
        # Placeholder implementation
        return await self._dijkstra_algorithm()

    async def _floyd_warshall_algorithm(self) -> Dict[str, Any]:
        """Floyd-Warshall all-pairs shortest path algorithm"""
        # Placeholder implementation
        return await self._dijkstra_algorithm()

    async def _a_star_algorithm(self) -> Dict[str, Any]:
        """A* algorithm with heuristics"""
        # Placeholder implementation
        return await self._dijkstra_algorithm()

    async def _genetic_algorithm(self) -> Dict[str, Any]:
        """Genetic algorithm for path optimization"""
        # Placeholder implementation
        return await self._dijkstra_algorithm()

    async def _ml_based_algorithm(self) -> Dict[str, Any]:
        """Machine learning based routing"""
        # Placeholder implementation
        return await self._dijkstra_algorithm()

    async def _hybrid_algorithm(self) -> Dict[str, Any]:
        """Hybrid approach combining multiple algorithms"""
        # Placeholder implementation
        return await self._dijkstra_algorithm()

    def _find_shortest_path(self, source: str, destination: str,
                          edges: Dict[str, Dict[str, float]]) -> Tuple[List[str], float]:
        """Find shortest path between two nodes"""
        # Simple Dijkstra implementation
        distances = {node: float('inf') for node in self.topology_snapshot.nodes}
        distances[source] = 0
        previous = {}
        unvisited = set(self.topology_snapshot.nodes)

        while unvisited:
            current = min(unvisited, key=lambda node: distances[node])
            if distances[current] == float('inf'):
                break

            unvisited.remove(current)

            if current == destination:
                break

            for neighbor, weight in edges.get(current, {}).items():
                if neighbor in unvisited:
                    alt = distances[current] + weight
                    if alt < distances[neighbor]:
                        distances[neighbor] = alt
                        previous[neighbor] = current

        # Reconstruct path
        path = []
        current = destination
        while current is not None:
            path.append(current)
            current = previous.get(current)

        path.reverse()
        return path, distances[destination]

    def _calculate_path_quality(self, routing_result: Dict[str, Any]) -> float:
        """Calculate overall quality score for routing result"""
        if not routing_result:
            return 0.0

        total_cost = 0.0
        valid_paths = 0

        for destination, route_info in routing_result.items():
            cost = route_info.get("cost", float('inf'))
            if cost < float('inf'):
                total_cost += cost
                valid_paths += 1

        if valid_paths == 0:
            return 0.0

        # Lower average cost means higher quality
        average_cost = total_cost / valid_paths
        quality_score = 1.0 / (1.0 + average_cost)

        return quality_score

    async def _propose_algorithm_change(self, new_algorithm: RoutingAlgorithm):
        """Propose algorithm change through consensus"""
        if self.consensus_state != ConsensusState.IDLE:
            return

        # Create proposal
        proposal_id = self._generate_proposal_id()
        routing_result = await self._run_routing_algorithm(new_algorithm)

        proposal = RoutingProposal(
            proposal_id=proposal_id,
            proposer_node=self.node_id,
            algorithm=new_algorithm,
            routing_table=routing_result,
            timestamp=time.time()
        )

        self.active_proposals[proposal_id] = proposal
        self.consensus_state = ConsensusState.PROPOSING

        # Send proposal to peers
        proposal_message = {
            "proposal_id": proposal_id,
            "proposer": self.node_id,
            "algorithm": new_algorithm.value,
            "routing_table": routing_result,
            "timestamp": proposal.timestamp
        }

        for peer in self.peer_nodes:
            await self._send_to_peer(peer, "routing_proposal", proposal_message)

        self.logger.info(f"Proposed algorithm change to {new_algorithm.value}")

    def _generate_proposal_id(self) -> str:
        """Generate unique proposal ID"""
        data = f"{self.node_id}_{time.time()}_{len(self.active_proposals)}"
        return hashlib.md5(data.encode()).hexdigest()[:16]

    async def _leader_election_loop(self):
        """Manage leader election process"""
        while self.running:
            try:
                await self._check_leader_status()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                self.logger.error(f"Error in leader election loop: {e}")

    async def _check_leader_status(self):
        """Check and update leader status"""
        if not self.peer_nodes:
            self.leader_node = self.node_id
            return

        # Simple leader election based on node ID
        all_nodes = self.peer_nodes | {self.node_id}
        self.leader_node = min(all_nodes)

        if self.leader_node == self.node_id:
            self.logger.debug("This node is the leader")
        else:
            self.logger.debug(f"Leader is {self.leader_node}")

    async def _cache_cleanup_loop(self):
        """Clean up expired cache entries"""
        while self.running:
            try:
                current_time = time.time()
                expired_keys = [
                    key for key, (_, timestamp) in self.routing_cache.items()
                    if current_time - timestamp > self.cache_ttl
                ]

                for key in expired_keys:
                    del self.routing_cache[key]

                await asyncio.sleep(60)  # Cleanup every minute

            except Exception as e:
                self.logger.error(f"Error in cache cleanup loop: {e}")

    async def _send_to_peer(self, peer_id: str, message_type: str, data: Dict[str, Any]):
        """Send message to peer node"""
        # Placeholder for actual peer communication
        self.logger.debug(f"Sending {message_type} to {peer_id}: {data}")

    def update_topology(self, owl_metrics: Dict[str, Dict[str, Dict[str, float]]]):
        """Update topology with new OWL metrics"""
        if not self.topology_snapshot:
            return

        self.topology_snapshot.owl_metrics = owl_metrics
        self.topology_snapshot.timestamp = time.time()
        self.topology_snapshot.version += 1

        # Update edges based on OWL metrics
        edges = {}
        for source, destinations in owl_metrics.items():
            edges[source] = {}
            for dest, metrics in destinations.items():
                # Use latency as edge weight
                latency = metrics.get('latency_ms', float('inf'))
                if latency < float('inf'):
                    edges[source][dest] = latency

        self.topology_snapshot.edges = edges

        # Clear cache when topology changes
        self.routing_cache.clear()

        self.logger.debug(f"Updated topology with {len(edges)} edge sets")

    def add_peer(self, peer_id: str):
        """Add peer node"""
        self.peer_nodes.add(peer_id)
        self.topology_snapshot.nodes.add(peer_id)
        self.logger.info(f"Added peer {peer_id}")

    def remove_peer(self, peer_id: str):
        """Remove peer node"""
        self.peer_nodes.discard(peer_id)
        self.topology_snapshot.nodes.discard(peer_id)

        # Clean up topology
        if peer_id in self.topology_snapshot.edges:
            del self.topology_snapshot.edges[peer_id]

        for source_edges in self.topology_snapshot.edges.values():
            source_edges.pop(peer_id, None)

        self.logger.info(f"Removed peer {peer_id}")

    async def get_routing_table(self) -> Dict[str, Dict[str, Any]]:
        """Get current routing table"""
        cache_key = "routing_table"
        current_time = time.time()

        # Check cache
        if cache_key in self.routing_cache:
            cached_result, timestamp = self.routing_cache[cache_key]
            if current_time - timestamp < self.cache_ttl:
                return cached_result

        # Compute new routing table
        routing_result = await self._run_routing_algorithm(self.current_algorithm)

        # Cache result
        self.routing_cache[cache_key] = (routing_result, current_time)

        return routing_result

    def get_metrics(self) -> Dict[str, Any]:
        """Get control plane metrics"""
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "current_algorithm": self.current_algorithm.value,
            "consensus_state": self.consensus_state.value,
            "leader_node": self.leader_node,
            "peer_count": len(self.peer_nodes),
            "active_proposals": len(self.active_proposals),
            "topology_version": self.topology_snapshot.version if self.topology_snapshot else 0,
            "cache_entries": len(self.routing_cache),
            "algorithm_metrics": {
                algo.value: {
                    "execution_time_ms": metrics.execution_time_ms,
                    "path_quality_score": metrics.path_quality_score,
                    "success_rate": metrics.success_rate
                }
                for algo, metrics in self.algorithm_metrics.items()
            }
        }

    def get_status(self) -> ComponentStatus:
        """Get current control plane status"""
        return self.status

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        health_status = {
            "healthy": self.status == ComponentStatus.HEALTHY,
            "status": self.status.value,
            "topology_current": (
                time.time() - self.topology_snapshot.timestamp < 60
                if self.topology_snapshot else False
            ),
            "consensus_active": self.consensus_state != ConsensusState.IDLE,
            "peers_reachable": len(self.peer_nodes) > 0
        }

        return health_status