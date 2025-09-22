"""
DDARP Resource Isolation and Process Management

Provides resource isolation, process lifecycle management, and resource
monitoring for all DDARP composite node sub-components.
"""

import asyncio
import logging
import time
import os
import psutil
import signal
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import subprocess
import resource

from ..monitoring.enhanced_prometheus_exporter import ComponentStatus


class ProcessState(Enum):
    """Process states"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    CRASHED = "crashed"


class ResourceLimit(Enum):
    """Resource limit types"""
    CPU_PERCENT = "cpu_percent"
    MEMORY_MB = "memory_mb"
    FILE_DESCRIPTORS = "file_descriptors"
    NETWORK_CONNECTIONS = "network_connections"
    DISK_IO_BPS = "disk_io_bps"


@dataclass
class ResourceLimits:
    """Resource limits for a process"""
    cpu_percent: Optional[float] = None  # Max CPU percentage
    memory_mb: Optional[int] = None      # Max memory in MB
    file_descriptors: Optional[int] = None  # Max file descriptors
    network_connections: Optional[int] = None  # Max network connections
    disk_io_bps: Optional[int] = None    # Max disk I/O bytes per second


@dataclass
class ProcessConfig:
    """Process configuration"""
    process_id: str
    component_name: str
    executable: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    working_dir: Optional[str] = None
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    restart_policy: str = "always"  # "always", "on-failure", "never"
    restart_delay: float = 5.0
    max_restarts: int = 5
    health_check_command: Optional[List[str]] = None
    health_check_interval: float = 30.0


@dataclass
class ProcessInfo:
    """Runtime process information"""
    config: ProcessConfig
    pid: Optional[int] = None
    state: ProcessState = ProcessState.STOPPED
    start_time: Optional[float] = None
    restart_count: int = 0
    last_restart: Optional[float] = None
    exit_code: Optional[int] = None
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    file_descriptors: int = 0
    network_connections: int = 0
    last_health_check: Optional[float] = None
    health_check_passed: bool = True


class ProcessManager:
    """Resource isolation and process management"""

    def __init__(self, node_id: str, config: Optional[Dict[str, Any]] = None):
        self.node_id = node_id
        self.config = config or {}
        self.logger = logging.getLogger(f"process_manager_{node_id}")

        # Component state
        self.running = False
        self.status = ComponentStatus.STOPPED

        # Process management
        self.processes: Dict[str, ProcessInfo] = {}
        self.process_objects: Dict[str, psutil.Process] = {}

        # Resource monitoring
        self.system_resources = {
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "disk_space": psutil.disk_usage('/').total
        }

        # Monitoring intervals
        self.resource_monitor_interval = 5.0   # seconds
        self.health_check_interval = 30.0      # seconds
        self.cleanup_interval = 60.0           # seconds

        # Resource enforcement
        self.enforce_limits = True
        self.kill_on_limit_exceeded = False

        # Process isolation
        self.use_cgroups = self._check_cgroups_available()
        self.cgroup_path = "/sys/fs/cgroup/ddarp"

        self.logger.info(f"Process Manager initialized for node {node_id}")

    def _check_cgroups_available(self) -> bool:
        """Check if cgroups are available"""
        try:
            return os.path.exists("/sys/fs/cgroup")
        except Exception:
            return False

    async def start(self):
        """Start the process manager"""
        self.logger.info("Starting Process Manager")
        self.status = ComponentStatus.STARTING

        try:
            # Initialize cgroups if available
            if self.use_cgroups:
                await self._initialize_cgroups()

            # Start monitoring tasks
            asyncio.create_task(self._resource_monitor_loop())
            asyncio.create_task(self._health_check_loop())
            asyncio.create_task(self._process_supervisor_loop())
            asyncio.create_task(self._cleanup_loop())

            self.running = True
            self.status = ComponentStatus.HEALTHY

            self.logger.info("Process Manager started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start Process Manager: {e}")
            self.status = ComponentStatus.ERROR
            raise

    async def stop(self):
        """Stop the process manager"""
        self.logger.info("Stopping Process Manager")
        self.status = ComponentStatus.STOPPING

        self.running = False

        # Stop all managed processes
        process_ids = list(self.processes.keys())
        for process_id in process_ids:
            try:
                await self.stop_process(process_id)
            except Exception as e:
                self.logger.error(f"Error stopping process {process_id}: {e}")

        # Cleanup cgroups
        if self.use_cgroups:
            await self._cleanup_cgroups()

        self.status = ComponentStatus.STOPPED
        self.logger.info("Process Manager stopped")

    async def _initialize_cgroups(self):
        """Initialize cgroups for resource isolation"""
        try:
            if not os.path.exists(self.cgroup_path):
                os.makedirs(self.cgroup_path, exist_ok=True)

            # Create cgroup for each subsystem
            subsystems = ["cpu", "memory", "pids"]
            for subsystem in subsystems:
                subsystem_path = os.path.join(self.cgroup_path, subsystem)
                if not os.path.exists(subsystem_path):
                    os.makedirs(subsystem_path, exist_ok=True)

            self.logger.info("Initialized cgroups for resource isolation")

        except Exception as e:
            self.logger.warning(f"Failed to initialize cgroups: {e}")
            self.use_cgroups = False

    async def _cleanup_cgroups(self):
        """Cleanup cgroups"""
        try:
            if os.path.exists(self.cgroup_path):
                # Remove cgroup directories
                for root, dirs, files in os.walk(self.cgroup_path, topdown=False):
                    for dir_name in dirs:
                        try:
                            os.rmdir(os.path.join(root, dir_name))
                        except OSError:
                            pass

            self.logger.info("Cleaned up cgroups")

        except Exception as e:
            self.logger.error(f"Error cleaning up cgroups: {e}")

    async def register_process(self, config: ProcessConfig):
        """Register a process for management"""
        if config.process_id in self.processes:
            raise ValueError(f"Process {config.process_id} already registered")

        process_info = ProcessInfo(config=config)
        self.processes[config.process_id] = process_info

        self.logger.info(f"Registered process {config.process_id} ({config.component_name})")

    async def start_process(self, process_id: str) -> bool:
        """Start a managed process"""
        if process_id not in self.processes:
            raise ValueError(f"Process {process_id} not registered")

        process_info = self.processes[process_id]
        if process_info.state == ProcessState.RUNNING:
            self.logger.warning(f"Process {process_id} is already running")
            return True

        try:
            process_info.state = ProcessState.STARTING
            config = process_info.config

            # Prepare environment
            env = os.environ.copy()
            env.update(config.env)

            # Prepare command
            cmd = [config.executable] + config.args

            # Start process
            self.logger.info(f"Starting process {process_id}: {' '.join(cmd)}")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                cwd=config.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Update process info
            process_info.pid = proc.pid
            process_info.start_time = time.time()
            process_info.state = ProcessState.RUNNING

            # Create psutil process object for monitoring
            try:
                psutil_proc = psutil.Process(proc.pid)
                self.process_objects[process_id] = psutil_proc
            except psutil.NoSuchProcess:
                self.logger.warning(f"Could not create psutil object for process {process_id}")

            # Apply resource limits
            if self.enforce_limits:
                await self._apply_resource_limits(process_id)

            # Setup cgroup if available
            if self.use_cgroups:
                await self._setup_process_cgroup(process_id)

            self.logger.info(f"Started process {process_id} with PID {proc.pid}")
            return True

        except Exception as e:
            self.logger.error(f"Error starting process {process_id}: {e}")
            process_info.state = ProcessState.ERROR
            return False

    async def stop_process(self, process_id: str, timeout: float = 10.0) -> bool:
        """Stop a managed process"""
        if process_id not in self.processes:
            raise ValueError(f"Process {process_id} not registered")

        process_info = self.processes[process_id]
        if process_info.state != ProcessState.RUNNING:
            self.logger.warning(f"Process {process_id} is not running")
            return True

        try:
            process_info.state = ProcessState.STOPPING

            if process_info.pid:
                # Try graceful shutdown first
                try:
                    os.kill(process_info.pid, signal.SIGTERM)
                    await asyncio.sleep(timeout)

                    # Check if process is still running
                    try:
                        os.kill(process_info.pid, 0)  # Check if process exists
                        # Process still running, force kill
                        self.logger.warning(f"Force killing process {process_id}")
                        os.kill(process_info.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        # Process already terminated
                        pass

                except ProcessLookupError:
                    # Process already terminated
                    pass

            # Cleanup
            process_info.pid = None
            process_info.state = ProcessState.STOPPED
            self.process_objects.pop(process_id, None)

            # Remove from cgroup
            if self.use_cgroups:
                await self._remove_process_from_cgroup(process_id)

            self.logger.info(f"Stopped process {process_id}")
            return True

        except Exception as e:
            self.logger.error(f"Error stopping process {process_id}: {e}")
            return False

    async def restart_process(self, process_id: str) -> bool:
        """Restart a managed process"""
        if process_id not in self.processes:
            raise ValueError(f"Process {process_id} not registered")

        process_info = self.processes[process_id]

        # Check restart policy
        if process_info.config.restart_policy == "never":
            self.logger.info(f"Not restarting process {process_id} (policy: never)")
            return False

        if process_info.restart_count >= process_info.config.max_restarts:
            self.logger.error(f"Process {process_id} exceeded max restarts ({process_info.config.max_restarts})")
            return False

        # Stop if running
        if process_info.state == ProcessState.RUNNING:
            await self.stop_process(process_id)

        # Wait for restart delay
        await asyncio.sleep(process_info.config.restart_delay)

        # Update restart info
        process_info.restart_count += 1
        process_info.last_restart = time.time()

        # Start process
        success = await self.start_process(process_id)

        if success:
            self.logger.info(f"Restarted process {process_id} (attempt {process_info.restart_count})")
        else:
            self.logger.error(f"Failed to restart process {process_id}")

        return success

    async def _apply_resource_limits(self, process_id: str):
        """Apply resource limits to process"""
        if process_id not in self.process_objects:
            return

        process_info = self.processes[process_id]
        limits = process_info.config.resource_limits
        psutil_proc = self.process_objects[process_id]

        try:
            # CPU limit (via nice value as approximation)
            if limits.cpu_percent:
                # Set nice value based on CPU limit
                nice_value = int((100 - limits.cpu_percent) / 10)
                nice_value = max(-20, min(19, nice_value))
                psutil_proc.nice(nice_value)

            # Memory limit (via setrlimit)
            if limits.memory_mb:
                memory_bytes = limits.memory_mb * 1024 * 1024
                try:
                    resource.prlimit(psutil_proc.pid, resource.RLIMIT_AS, (memory_bytes, memory_bytes))
                except OSError as e:
                    self.logger.warning(f"Could not set memory limit for {process_id}: {e}")

            # File descriptor limit
            if limits.file_descriptors:
                try:
                    resource.prlimit(
                        psutil_proc.pid,
                        resource.RLIMIT_NOFILE,
                        (limits.file_descriptors, limits.file_descriptors)
                    )
                except OSError as e:
                    self.logger.warning(f"Could not set file descriptor limit for {process_id}: {e}")

            self.logger.debug(f"Applied resource limits to process {process_id}")

        except Exception as e:
            self.logger.error(f"Error applying resource limits to {process_id}: {e}")

    async def _setup_process_cgroup(self, process_id: str):
        """Setup cgroup for process"""
        if not self.use_cgroups or process_id not in self.processes:
            return

        process_info = self.processes[process_id]
        limits = process_info.config.resource_limits

        try:
            # Create process-specific cgroup
            process_cgroup = os.path.join(self.cgroup_path, process_id)
            os.makedirs(process_cgroup, exist_ok=True)

            # Add process to cgroup
            cgroup_procs = os.path.join(process_cgroup, "cgroup.procs")
            with open(cgroup_procs, 'w') as f:
                f.write(str(process_info.pid))

            # Set CPU limit
            if limits.cpu_percent:
                cpu_quota_file = os.path.join(process_cgroup, "cpu.cfs_quota_us")
                cpu_period_file = os.path.join(process_cgroup, "cpu.cfs_period_us")

                if os.path.exists(cpu_quota_file):
                    quota = int(limits.cpu_percent / 100 * 100000)  # 100ms period
                    with open(cpu_quota_file, 'w') as f:
                        f.write(str(quota))
                    with open(cpu_period_file, 'w') as f:
                        f.write("100000")

            # Set memory limit
            if limits.memory_mb:
                memory_limit_file = os.path.join(process_cgroup, "memory.limit_in_bytes")
                if os.path.exists(memory_limit_file):
                    memory_bytes = limits.memory_mb * 1024 * 1024
                    with open(memory_limit_file, 'w') as f:
                        f.write(str(memory_bytes))

            self.logger.debug(f"Setup cgroup for process {process_id}")

        except Exception as e:
            self.logger.error(f"Error setting up cgroup for {process_id}: {e}")

    async def _remove_process_from_cgroup(self, process_id: str):
        """Remove process from cgroup"""
        if not self.use_cgroups:
            return

        try:
            process_cgroup = os.path.join(self.cgroup_path, process_id)
            if os.path.exists(process_cgroup):
                os.rmdir(process_cgroup)

        except Exception as e:
            self.logger.error(f"Error removing cgroup for {process_id}: {e}")

    async def _resource_monitor_loop(self):
        """Monitor resource usage of all processes"""
        while self.running:
            try:
                await self._monitor_process_resources()
                await asyncio.sleep(self.resource_monitor_interval)
            except Exception as e:
                self.logger.error(f"Error in resource monitor loop: {e}")

    async def _monitor_process_resources(self):
        """Monitor resources for all processes"""
        for process_id, process_info in self.processes.items():
            if process_info.state != ProcessState.RUNNING or process_id not in self.process_objects:
                continue

            try:
                psutil_proc = self.process_objects[process_id]

                # Update resource usage
                process_info.cpu_percent = psutil_proc.cpu_percent()
                process_info.memory_mb = psutil_proc.memory_info().rss / (1024 * 1024)

                try:
                    process_info.file_descriptors = psutil_proc.num_fds()
                except (psutil.AccessDenied, AttributeError):
                    pass

                try:
                    process_info.network_connections = len(psutil_proc.connections())
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass

                # Check resource limits
                if self.enforce_limits:
                    await self._check_resource_limits(process_id)

            except psutil.NoSuchProcess:
                # Process terminated
                process_info.state = ProcessState.CRASHED
                process_info.pid = None
                self.process_objects.pop(process_id, None)

            except Exception as e:
                self.logger.error(f"Error monitoring process {process_id}: {e}")

    async def _check_resource_limits(self, process_id: str):
        """Check if process exceeds resource limits"""
        process_info = self.processes[process_id]
        limits = process_info.config.resource_limits

        exceeded_limits = []

        # Check CPU limit
        if limits.cpu_percent and process_info.cpu_percent > limits.cpu_percent:
            exceeded_limits.append(f"CPU: {process_info.cpu_percent:.1f}% > {limits.cpu_percent}%")

        # Check memory limit
        if limits.memory_mb and process_info.memory_mb > limits.memory_mb:
            exceeded_limits.append(f"Memory: {process_info.memory_mb:.1f}MB > {limits.memory_mb}MB")

        # Check file descriptor limit
        if limits.file_descriptors and process_info.file_descriptors > limits.file_descriptors:
            exceeded_limits.append(f"FDs: {process_info.file_descriptors} > {limits.file_descriptors}")

        if exceeded_limits:
            self.logger.warning(f"Process {process_id} exceeded limits: {', '.join(exceeded_limits)}")

            if self.kill_on_limit_exceeded:
                self.logger.warning(f"Killing process {process_id} for exceeding limits")
                await self.stop_process(process_id)

    async def _health_check_loop(self):
        """Perform health checks on processes"""
        while self.running:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.health_check_interval)
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")

    async def _perform_health_checks(self):
        """Perform health checks for all processes"""
        for process_id, process_info in self.processes.items():
            if (process_info.state == ProcessState.RUNNING and
                    process_info.config.health_check_command):

                try:
                    await self._run_health_check(process_id)
                except Exception as e:
                    self.logger.error(f"Error running health check for {process_id}: {e}")

    async def _run_health_check(self, process_id: str):
        """Run health check for specific process"""
        process_info = self.processes[process_id]
        health_cmd = process_info.config.health_check_command

        try:
            proc = await asyncio.create_subprocess_exec(
                *health_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            await asyncio.wait_for(proc.communicate(), timeout=10.0)

            process_info.health_check_passed = proc.returncode == 0
            process_info.last_health_check = time.time()

            if not process_info.health_check_passed:
                self.logger.warning(f"Health check failed for process {process_id}")

        except asyncio.TimeoutError:
            self.logger.warning(f"Health check timeout for process {process_id}")
            process_info.health_check_passed = False

        except Exception as e:
            self.logger.error(f"Health check error for process {process_id}: {e}")
            process_info.health_check_passed = False

    async def _process_supervisor_loop(self):
        """Supervise processes and restart if needed"""
        while self.running:
            try:
                await self._supervise_processes()
                await asyncio.sleep(10.0)  # Check every 10 seconds
            except Exception as e:
                self.logger.error(f"Error in process supervisor loop: {e}")

    async def _supervise_processes(self):
        """Check process states and restart if needed"""
        for process_id, process_info in self.processes.items():
            if process_info.state == ProcessState.CRASHED:
                # Process crashed, consider restart
                if process_info.config.restart_policy in ["always", "on-failure"]:
                    self.logger.info(f"Process {process_id} crashed, attempting restart")
                    await self.restart_process(process_id)

            elif process_info.state == ProcessState.RUNNING:
                # Check if process is still alive
                if process_id in self.process_objects:
                    try:
                        psutil_proc = self.process_objects[process_id]
                        if not psutil_proc.is_running():
                            process_info.state = ProcessState.CRASHED
                    except Exception:
                        process_info.state = ProcessState.CRASHED

    async def _cleanup_loop(self):
        """Periodic cleanup tasks"""
        while self.running:
            try:
                await self._cleanup_resources()
                await asyncio.sleep(self.cleanup_interval)
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_resources(self):
        """Cleanup resources and stale data"""
        # Remove stale psutil objects
        stale_objects = []
        for process_id, psutil_proc in self.process_objects.items():
            try:
                if not psutil_proc.is_running():
                    stale_objects.append(process_id)
            except Exception:
                stale_objects.append(process_id)

        for process_id in stale_objects:
            self.process_objects.pop(process_id, None)

    def get_process_status(self, process_id: str) -> Optional[Dict[str, Any]]:
        """Get status of specific process"""
        if process_id not in self.processes:
            return None

        process_info = self.processes[process_id]
        return {
            "process_id": process_id,
            "component_name": process_info.config.component_name,
            "state": process_info.state.value,
            "pid": process_info.pid,
            "start_time": process_info.start_time,
            "restart_count": process_info.restart_count,
            "cpu_percent": process_info.cpu_percent,
            "memory_mb": process_info.memory_mb,
            "file_descriptors": process_info.file_descriptors,
            "network_connections": process_info.network_connections,
            "health_check_passed": process_info.health_check_passed,
            "last_health_check": process_info.last_health_check
        }

    def get_all_processes_status(self) -> List[Dict[str, Any]]:
        """Get status of all managed processes"""
        return [
            self.get_process_status(process_id)
            for process_id in self.processes.keys()
        ]

    def get_system_resources(self) -> Dict[str, Any]:
        """Get system resource information"""
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "cpu_percent": cpu,
            "memory_total_mb": memory.total // (1024 * 1024),
            "memory_used_mb": memory.used // (1024 * 1024),
            "memory_percent": memory.percent,
            "disk_total_gb": disk.total // (1024 * 1024 * 1024),
            "disk_used_gb": disk.used // (1024 * 1024 * 1024),
            "disk_percent": (disk.used / disk.total) * 100,
            "process_count": len(self.processes)
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get process manager metrics"""
        running_processes = sum(
            1 for p in self.processes.values()
            if p.state == ProcessState.RUNNING
        )

        total_cpu = sum(p.cpu_percent for p in self.processes.values())
        total_memory = sum(p.memory_mb for p in self.processes.values())

        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "total_processes": len(self.processes),
            "running_processes": running_processes,
            "crashed_processes": sum(
                1 for p in self.processes.values()
                if p.state == ProcessState.CRASHED
            ),
            "total_restarts": sum(p.restart_count for p in self.processes.values()),
            "total_cpu_percent": total_cpu,
            "total_memory_mb": total_memory,
            "cgroups_enabled": self.use_cgroups,
            "resource_enforcement": self.enforce_limits
        }

    def get_status(self) -> ComponentStatus:
        """Get current process manager status"""
        return self.status

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        unhealthy_processes = [
            p.config.process_id for p in self.processes.values()
            if p.state in [ProcessState.CRASHED, ProcessState.ERROR] or
            not p.health_check_passed
        ]

        health_status = {
            "healthy": self.status == ComponentStatus.HEALTHY and len(unhealthy_processes) == 0,
            "status": self.status.value,
            "managed_processes": len(self.processes),
            "unhealthy_processes": unhealthy_processes,
            "system_resources": self.get_system_resources()
        }

        return health_status