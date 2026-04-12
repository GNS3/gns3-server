# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copyright (C) 2026 YueGuobin
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Web Wireshark - Session Manager

This module handles xpra session management for Web Wireshark containers.
"""

import asyncio
import logging
import re
import socket
from typing import Optional
from urllib.parse import urlparse

from gns3server.config import Config
from gns3server.utils.port_allocator import link_id_to_display, link_id_to_port
from .docker_client import DockerHTTPClient

logger = logging.getLogger(__name__)

# Default GNS3 server address
DEFAULT_GNS3_URL = "http://127.0.0.1:3080"


class WebWiresharkManager:
    """Manages Web Wireshark sessions and containers."""

    # Container command execution timeout (seconds)
    CONTAINER_EXEC_TIMEOUT = 10

    def __init__(self):
        self.docker = DockerHTTPClient()
        self.network_name = "gns3-wireshark"

    async def close(self):
        """Close Docker connection."""
        await self.docker.close()

    async def _is_container_healthy(self, container_id: str) -> bool:
        """Check if container is responsive.

        Args:
            container_id: Container ID

        Returns:
            True if healthy, False otherwise
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", container_id,
                "bash", "-c", "echo 'ping'",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.CONTAINER_EXEC_TIMEOUT
            )
            return proc.returncode == 0 and b"ping" in stdout
        except asyncio.TimeoutError:
            logger.warning(f"Container {container_id[:12]} health check timeout")
            return False
        except FileNotFoundError:
            logger.warning(f"Container {container_id[:12]} docker command not found")
            return False
        except Exception as e:
            logger.warning(f"Container {container_id[:12]} health check failed: {e}")
            return False

    async def _exec_in_container(self, container_id: str, command: str, timeout: int = None) -> tuple:
        """Execute command in container with timeout.

        Args:
            container_id: Container ID
            command: Command to execute
            timeout: Timeout in seconds (default: CONTAINER_EXEC_TIMEOUT)

        Returns:
            (returncode, stdout, stderr)
        """
        if timeout is None:
            timeout = self.CONTAINER_EXEC_TIMEOUT

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", container_id,
                "bash", "-c", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
                return (proc.returncode, stdout.decode().strip(), stderr.decode().strip())
            except asyncio.TimeoutError:
                logger.error(f"Command timeout after {timeout}s: {command}")
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=2)
                except asyncio.TimeoutError:
                    proc.kill()
                return (-1, "", f"timeout after {timeout}s")
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return (-1, "", str(e))

    async def _kill_process_tree(self, container_id: str, pattern: str) -> None:
        """Kill all processes matching pattern inside the container.

        Uses pgrep inside the container to get container-local PIDs, then kills them.
        This avoids the issue where Docker API returns host PIDs instead of container PIDs.

        Args:
            container_id: Container ID
            pattern: Process pattern to match (regex applied to COMMAND field)
        """
        try:
            # Get container-local PIDs using pgrep inside the container
            pgrep_cmd = f"sh -c 'pgrep -f \"{pattern}\" || true'"
            returncode, stdout, stderr = await self._exec_in_container(container_id, pgrep_cmd)
            pids_str = stdout.strip()

            if not pids_str:
                logger.debug(f"No processes found matching pattern '{pattern}'")
                return

            pids = pids_str.replace('\n', ' ')
            logger.info(f"Found matching processes for '{pattern}': PIDs={pids}")

            # Kill the processes using their container-local PIDs
            kill_cmd = f"kill -9 {pids} 2>/dev/null || true"
            returncode, stdout, stderr = await self._exec_in_container(container_id, kill_cmd)
            logger.debug(f"Kill result: returncode={returncode}")

        except Exception as e:
            logger.error(f"Error killing processes matching '{pattern}': {e}")

    async def _check_residuals_exist(self, container_id: str, display: int) -> tuple[bool, bool]:
        """Check if there are residual processes or files for a display.

        Uses host perspective for fast checking (~20ms vs ~850ms for docker exec).
        Returns two booleans: (has_process_residuals, has_socket_residuals).
        This allows selective cleanup when only one type needs attention.

        Args:
            container_id: Container ID
            display: Display number (e.g., 10210)

        Returns:
            Tuple of (has_process_residuals, has_socket_residuals)
        """
        try:
            # Get container init PID from host perspective
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect", container_id,
                "--format", "{{.State.Pid}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            container_init_pid = stdout.decode().strip()

            if not container_init_pid:
                # Can't determine, assume cleanup needed
                return (True, True)

            has_process_residuals = False
            has_socket_residuals = False

            # Check for residual processes from host perspective
            proc = await asyncio.create_subprocess_exec(
                "ps", "-eo", "pid,ppid,args",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()

            # Build parent->children mapping
            children_map = {}
            for line in stdout.decode().strip().split('\n'):
                parts = line.split(None, 2)
                if len(parts) < 3:
                    continue
                try:
                    pid, ppid = int(parts[0]), int(parts[1])
                    children_map.setdefault(ppid, []).append(pid)
                except ValueError:
                    continue

            # Recursively find all descendant PIDs of container init
            descendant_pids = set()

            def find_descendants(ppid):
                children = children_map.get(ppid, [])
                for child_pid in children:
                    descendant_pids.add(child_pid)
                    find_descendants(child_pid)

            find_descendants(int(container_init_pid))

            # Check if any descendant processes match display patterns
            import re
            patterns = [
                f'xpra.*:{display}',
                f'Xvfb.*:{display}',
                f'wireshark.*:{display}',
                f'pulseaudio.*display=:{display}'
            ]

            for line in stdout.decode().strip().split('\n'):
                parts = line.split(None, 2)
                if len(parts) < 3:
                    continue
                try:
                    pid, ppid = int(parts[0]), int(parts[1])
                    command = parts[2]

                    if pid not in descendant_pids:
                        continue

                    for pattern in patterns:
                        if re.search(pattern, command):
                            logger.debug(f"Found residual process: PID={pid}, COMMAND={command[:80]}")
                            has_process_residuals = True
                            break
                except ValueError:
                    continue

            # Check for X lock files from host perspective
            # /proc/<pid>/root points to container filesystem
            lock_paths = [
                f"/proc/{container_init_pid}/root/tmp/.X{display}-lock",
                f"/proc/{container_init_pid}/root/tmp/.X11-unix/X{display}"
            ]
            for lock_path in lock_paths:
                proc = await asyncio.create_subprocess_exec(
                    "test", "-e", lock_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
                if proc.returncode == 0:
                    logger.debug(f"Found residual lock file: {lock_path}")
                    has_socket_residuals = True

            # Check for xpra socket files
            socket_path = f"/proc/{container_init_pid}/root/run/user/1000/xpra/{display}/socket"
            proc = await asyncio.create_subprocess_exec(
                "test", "-e", socket_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            if proc.returncode == 0:
                logger.debug(f"Found residual socket: {socket_path}")
                has_socket_residuals = True

            return (has_process_residuals, has_socket_residuals)

        except Exception as e:
            logger.warning(f"Error checking residuals (assuming cleanup needed): {e}")
            return (True, True)

    async def _kill_process_tree_batch(self, container_id: str, patterns: list) -> None:
        """Kill all processes matching multiple patterns inside the container.

        Uses host perspective to find and kill container processes much faster
        than docker exec (37x faster: ~23ms vs ~850ms).

        This method finds ALL processes in the container (including grandchildren)
        by walking the process tree from container init, not just direct children.

        Args:
            container_id: Container ID
            patterns: List of process patterns to match (regex applied to COMMAND field)
        """
        if not patterns:
            return

        try:
            # Get container init PID from host perspective
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect", container_id,
                "--format", "{{.State.Pid}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            container_init_pid = stdout.decode().strip()

            if not container_init_pid:
                logger.warning("Could not get container init PID, falling back to docker exec")
                await self._kill_process_tree_batch_via_exec(container_id, patterns)
                return

            # List all processes from host perspective with PID, PPID, and command
            # This is faster than docker exec and allows us to walk the process tree
            proc = await asyncio.create_subprocess_exec(
                "ps", "-eo", "pid,ppid,args",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()

            if not stdout.strip():
                logger.debug(f"No processes found from host perspective")
                return

            # Build parent->children mapping and collect process info
            children_map = {}  # ppid -> [pid]
            process_info = {}  # pid -> (ppid, command)

            for line in stdout.decode().strip().split('\n'):
                parts = line.split(None, 2)
                if len(parts) < 3:
                    continue
                try:
                    pid, ppid = int(parts[0]), int(parts[1])
                    command = parts[2]

                    children_map.setdefault(ppid, []).append(pid)
                    process_info[pid] = (ppid, command)
                except ValueError:
                    continue

            # Recursively find all descendant processes of container init
            descendant_pids = set()

            def find_descendants(ppid):
                """Recursively find all descendant PIDs."""
                children = children_map.get(ppid, [])
                for child_pid in children:
                    descendant_pids.add(child_pid)
                    find_descendants(child_pid)  # Recursively find grandchildren

            find_descendants(int(container_init_pid))

            # Filter descendant processes by pattern and extract PIDs
            matching_pids = []
            for pid in descendant_pids:
                if pid not in process_info:
                    continue
                _, command = process_info[pid]

                # Check if command matches any pattern
                for pattern in patterns:
                    if re.search(pattern, command):
                        matching_pids.append(str(pid))
                        logger.debug(f"Found process: PID={pid}, COMMAND={command[:100]}")
                        break

            if matching_pids:
                logger.info(f"Killing {len(matching_pids)} processes: {matching_pids}")
                # Kill all matching PIDs from host perspective
                proc = await asyncio.create_subprocess_exec(
                    "kill", "-9", *matching_pids,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
                logger.debug(f"Kill completed from host perspective")
            else:
                logger.debug(f"No processes found matching patterns: {patterns}")

        except Exception as e:
            logger.warning(f"Error using host perspective for killing (fallback to docker exec): {e}")
            # Fallback to docker exec method
            await self._kill_process_tree_batch_via_exec(container_id, patterns)

    async def _kill_process_tree_batch_via_exec(self, container_id: str, patterns: list) -> None:
        """Kill processes using docker exec (fallback method).

        This is slower (~850ms) but more reliable in some edge cases.

        Args:
            container_id: Container ID
            patterns: List of process patterns to match
        """
        try:
            # Combine all patterns into a single regex using OR operator
            combined_pattern = '|'.join(f'({pattern})' for pattern in patterns)

            # Single pgrep to find all matching processes
            pgrep_cmd = f'pids=$(pgrep -f "{combined_pattern}" 2>/dev/null || true); if [ -n "$pids" ]; then echo "Found processes: $pids"; kill -9 $pids 2>/dev/null || true; fi'

            returncode, stdout, stderr = await self._exec_in_container(
                container_id,
                pgrep_cmd,
                timeout=5
            )

            if "Found processes:" in stdout:
                logger.info(stdout.strip())

        except Exception as e:
            logger.error(f"Error in batch kill via docker exec: {e}")

    async def _cleanup_x_lock(self, container_id: str, display: int) -> None:
        """Remove X lock file and xpra socket files for a display.

        Args:
            container_id: Container ID
            display: Display number (e.g., 10210)
        """
        # Clean up X lock files
        cmd = f"rm -f /tmp/.X{display}-lock /tmp/.X11-unix/X{display} 2>/dev/null || true"
        returncode, stdout, stderr = await self._exec_in_container(container_id, cmd)
        logger.debug(f"Cleanup X locks: returncode={returncode}")

        # Clean up xpra socket files
        cmd = (f"rm -f /run/user/1000/xpra/{display}/socket "
               f"/run/user/1000/xpra/*-{display} "
               f"/home/gns3/.xpra/*-{display} 2>/dev/null || true")
        returncode, stdout, stderr = await self._exec_in_container(container_id, cmd)
        logger.debug(f"Cleanup xpra sockets: returncode={returncode}")

    async def _cleanup_socket_files(self, container_id: str, display: int) -> None:
        """Remove only xpra socket files for a display (faster, single docker exec).

        Args:
            container_id: Container ID
            display: Display number (e.g., 10210)
        """
        cmd = (f"rm -f /run/user/1000/xpra/{display}/socket "
               f"/run/user/1000/xpra/*-{display} "
               f"/home/gns3/.xpra/*-{display} 2>/dev/null || true")
        returncode, stdout, stderr = await self._exec_in_container(container_id, cmd)
        logger.debug(f"Cleanup socket files: returncode={returncode}")

    @staticmethod
    def _parse_memory(memory_str: str) -> int:
        """Parse memory string to bytes.

        Args:
            memory_str: Memory string (e.g., "2g", "512m")

        Returns:
            Memory in bytes
        """
        memory_str = memory_str.lower().strip()
        if not memory_str:
            return 0

        # Extract number and unit
        match = re.match(r'(\d+(?:\.\d+)?)\s*([kmg]b?)?', memory_str)
        if not match:
            raise ValueError(f"Invalid memory format: {memory_str}")

        value = float(match.group(1))
        unit = match.group(2) or 'b'

        # Convert to bytes
        multipliers = {
            'b': 1,
            'k': 1024,
            'm': 1024 * 1024,
            'g': 1024 * 1024 * 1024
        }

        unit = unit[0]  # Take first character
        return int(value * multipliers.get(unit, 1))

    def _get_gns3_url_from_config(self) -> Optional[str]:
        """Get GNS3 server URL from config file."""
        try:
            server_config = Config.instance().settings.Server
            url = f"{server_config.protocol.value}://{server_config.host}:{server_config.port}"
            logger.info(f"Got GNS3 URL from Config: {url}")
            return url
        except Exception as e:
            logger.debug(f"Cannot get URL from Config: {e}")
        return None

    async def _get_container_gateway_ip(self, container_id: str = None) -> Optional[str]:
        """Get the Docker bridge gateway IP for container to access host.

        Args:
            container_id: Container ID (optional, only used for fallback methods)

        Returns:
            Gateway IP (e.g., 172.31.0.1) or None if not detectable
        """
        # Method 1: Get from Docker Network API (fastest, no container access needed)
        try:
            network = await self.docker.get_network(self.network_name)
            if network and "IPAM" in network:
                for config in network["IPAM"].get("Config", []):
                    if "Gateway" in config:
                        gateway_ip = config["Gateway"]
                        logger.info(f"Got gateway IP from Docker network API: {gateway_ip}")
                        return gateway_ip
        except Exception as e:
            logger.debug(f"Cannot get gateway from Docker network API: {e}")

        # Fallback: Read from /proc/net/route inside container (slower)
        if container_id:
            try:
                returncode, stdout, stderr = await self._exec_in_container(
                    container_id,
                    "cat /proc/net/route | grep -E '^eth0\\s+00000000' | awk '{print $3}' | head -1"
                )
                logger.info(f"Gateway detection - fallback method: returncode={returncode}, stdout='{stdout}'")
                if returncode == 0 and stdout.strip():
                    gateway_hex = stdout.strip()
                    # Convert hex to dotted decimal
                    gateway_ip = socket.inet_ntoa(bytes.fromhex(gateway_hex)[::-1])
                    logger.info(f"Detected container gateway IP from route: {gateway_ip}")
                    return gateway_ip
            except Exception as e:
                logger.debug(f"Cannot get gateway from /proc/net/route: {e}")

        return None

    async def _fix_localhost_url(self, url: str, container_id: str) -> str:
        """Fix URL with localhost/127.0.0.1 for container access.

        If the URL points to localhost, replace it with the container's
        gateway IP so the container can reach the host.

        Args:
            url: Original URL
            container_id: Container ID

        Returns:
            Fixed URL with accessible host IP
        """
        try:
            parsed = urlparse(url)
            if parsed.hostname in ('localhost', '127.0.0.1', '0.0.0.0'):
                gateway = await self._get_container_gateway_ip(container_id)
                if gateway:
                    fixed_url = f"{parsed.scheme}://{gateway}:{parsed.port or 3080}{parsed.path}"
                    if parsed.query:
                        fixed_url += f"?{parsed.query}"
                    logger.info(f"Fixed localhost URL for container: {url} -> {fixed_url}")
                    return fixed_url
                else:
                    logger.warning(f"Cannot detect gateway IP, keeping original URL: {url}")
        except Exception as e:
            logger.warning(f"Error fixing localhost URL: {e}")
        return url

    def detect_gns3_url(self) -> str:
        """Detect GNS3 server URL from config or use default.

        Note: This returns the raw URL (may contain 127.0.0.1).
        The URL will be fixed for container access later using _fix_localhost_url.

        Returns:
            GNS3 server URL
        """
        # Strategy 1: Get from Config
        url = self._get_gns3_url_from_config()
        if url:
            return url

        # Strategy 2: Use default
        logger.warning(f"Using fallback default URL: {DEFAULT_GNS3_URL}")
        return DEFAULT_GNS3_URL

    async def ensure_network(self):
        """Ensure Docker network exists."""
        network = await self.docker.get_network(self.network_name)
        if network:
            logger.info(f"Network {self.network_name} already exists")
        else:
            # Get subnet from config or use default
            config = Config.instance()
            subnet = getattr(config.settings.WebWireshark, "network_subnet", "172.31.0.0/22")
            logger.info(f"Creating network {self.network_name} with subnet {subnet}")
            await self.docker.create_network(
                self.network_name,
                driver="bridge",
                subnet=subnet
            )

    async def get_or_create_container(
        self,
        project_id: str,
        image: str = "gns3/web-wireshark:latest",
        memory: str = "2g",
        memory_swap: str = None,
        cpus: float = 1.0,
        pids_limit: int = 1000
    ) -> str:
        """Get or create project's Web Wireshark container.

        Args:
            project_id: Project ID
            image: Docker image name
            memory: Memory limit (default: 2g)
            memory_swap: Memory swap limit (default: same as memory)
            cpus: CPU cores (default: 1.0)
            pids_limit: Process limit (default: 1000)

        Returns:
            Container ID
        """
        container_name = f"gns3-wireshark-{project_id}"

        logger.info(f"Checking container {container_name}")
        container = await self.docker.get_container(container_name)
        logger.info(f"Container found: {container is not None}")

        if container:
            logger.info(f"Container state: {container['State']}")
            if container["State"]["Running"]:
                # Use Docker's built-in health check status instead of manual ping
                health_status = container.get("Health", {}).get("Status", None)

                if health_status == "unhealthy":
                    # Only unhealthy containers need further verification
                    logger.warning(f"Container {container_name} reports unhealthy status")
                    if not await self._is_container_healthy(container["Id"]):
                        # Container is truly unresponsive, force remove
                        logger.warning(f"Container {container_name} is not responding, force removing...")
                        try:
                            await self.docker.remove_container(container["Id"], force=True)
                            logger.info(f"Container {container_name} force removed")
                        except Exception as e:
                            logger.warning(f"Failed to remove unhealthy container: {e}")
                        container = None  # Trigger recreation
                    else:
                        # Health check passed despite unhealthy status, use it
                        logger.info(f"Container {container_name} is responsive despite unhealthy status")
                        return container["Id"]
                else:
                    # healthy, starting, or no health check configured - trust Docker
                    logger.info(f"Container {container_name} is running (health: {health_status})")
                    return container["Id"]
            else:
                logger.info(f"Starting existing container {container_name}")
                await self.docker.start_container(container["Id"])
                if await self._is_container_healthy(container["Id"]):
                    return container["Id"]
                # Still unhealthy after start, remove and recreate
                logger.error(f"Container {container_name} failed to become healthy, force removing...")
                try:
                    await self.docker.remove_container(container["Id"], force=True)
                except Exception:
                    pass
                container = None

        # Need to create new container
        if container is None:
            logger.info(f"Creating new container {container_name} with image {image}")
            logger.info(f"Resources: memory={memory}, cpus={cpus}, pids_limit={pids_limit}")

            # Calculate CPU quota (NanoCpus uses nanoseconds: 1 CPU = 1000000000)
            cpu_quota = int(cpus * 1000000000)

            # Configure host settings
            host_config = {
                "Memory": self._parse_memory(memory),
                "MemorySwap": self._parse_memory(memory_swap) if memory_swap else 0,
                "NanoCpus": cpu_quota,
                "PidsLimit": pids_limit,
                "RestartPolicy": {"Name": "unless-stopped"},
                "Init": True,  # Use init system (tini) as PID 1 to reap zombie processes
                "LogConfig": {
                    "Type": "json-file",
                    "Config": {
                        "max-size": "10m",
                        "max-file": "3"
                    }
                }
            }

            # Health check configuration
            health_config = {
                "Test": ["CMD-SHELL", "xpra list"],
                "Interval": 30000000000,  # 30 seconds (nanoseconds)
                "Timeout": 10000000000,   # 10 seconds
                "Retries": 3
            }

            container_id = await self.docker.create_container(
                name=container_name,
                image=image,
                network=self.network_name,
                host_config=host_config,
                health_config=health_config,
                environment={
                    "XDG_RUNTIME_DIR": "/run/user/1000",
                    "LANG": "C.UTF-8",
                    "LC_ALL": "C.UTF-8"
                }
            )

            # Start container
            await self.docker.start_container(container_id)
            logger.info(f"Container {container_name} created and started")
            return container_id

        return container["Id"]

    async def start_wireshark_session(
        self,
        project_id: str,
        link_id: str,
        jwt_token: str,
        capture_stream_url: Optional[str] = None,
        image: str = "gns3/web-wireshark:latest",
        memory: str = "2g",
        memory_swap: Optional[str] = None,
        cpus: float = 1.0,
        pids_limit: int = 1000
    ) -> dict:
        """Start Web Wireshark session.

        Args:
            project_id: Project ID
            link_id: Link ID
            jwt_token: JWT authentication token
            capture_stream_url: Capture stream URL (optional, auto-detected if not provided)
            image: Docker image name
            memory: Memory limit
            memory_swap: Memory swap limit
            cpus: CPU cores
            pids_limit: Process limit

        Returns:
            Session info dict
        """
        logger.info(f"Starting Web Wireshark session for link {link_id}")

        # Auto-detect capture_stream_url if not provided
        if not capture_stream_url:
            gns3_url = self.detect_gns3_url()
            capture_stream_url = (
                f"{gns3_url}/v3/projects/{project_id}/links/"
                f"{link_id}/capture/stream"
            )
            logger.info(f"Auto-detected capture stream URL: {capture_stream_url}")

        container_id = await self.get_or_create_container(
            project_id,
            image,
            memory,
            memory_swap,
            cpus,
            pids_limit
        )
        container_name = f"gns3-wireshark-{project_id}"

        # Fix localhost URL after we have container_id
        capture_stream_url = await self._fix_localhost_url(capture_stream_url, container_id)
        logger.info(f"Final capture stream URL: {capture_stream_url}")

        # Allocate display and port using deterministic hash
        display = link_id_to_display(link_id)
        port = link_id_to_port(link_id)

        # Check for residual processes/files from host perspective (fast ~20ms)
        # Only execute docker exec cleanup (~850ms) if residuals are found
        has_process_residuals, has_socket_residuals = await self._check_residuals_exist(container_id, display)

        if has_process_residuals or has_socket_residuals:
            logger.info(f"Found residual processes={has_process_residuals} sockets={has_socket_residuals} on display :{display}, cleaning up...")
            if has_process_residuals:
                patterns = [
                    f'xpra.*:{display}',
                    f'Xvfb.*:{display}',
                    f'wireshark.*:{display}',
                    f'pulseaudio.*display=:{display}'
                ]
                await self._kill_process_tree_batch(container_id, patterns)
            if has_socket_residuals:
                await self._cleanup_x_lock(container_id, display)
        else:
            logger.debug(f"No residual processes/files found on display :{display}")

        # Prepare xpra command
        session_name = f"link-{link_id}"
        logger.info(f"Starting xpra session {session_name} on display :{display}")

        xpra_cmd = [
            "XPRA_CLIENT_CAN_SHUTDOWN=false",
            "xpra", "start", f":{display}",
            '--xvfb="Xvfb -screen 0 1920x1080x24 +extension RANDR"',
            "--html=off",
            f"--bind-ws=0.0.0.0:{port}",
            f"--session-name={session_name}",
            "--daemon=yes",
            "--dbus-launch=no",
            "--resize-display=yes"
        ]

        # Parallel execution: get container info + start xpra
        container_info_task = asyncio.create_task(
            self.docker.get_container(container_name)
        )
        xpra_start_task = asyncio.create_task(
            self._exec_in_container(container_id, " ".join(xpra_cmd))
        )

        # Wait for both tasks to complete
        container, (returncode, stdout, stderr) = await asyncio.gather(
            container_info_task,
            xpra_start_task
        )

        # Check xpra start result
        if returncode != 0:
            logger.error(f"xpra start failed (code {returncode}): {stdout} {stderr}")
            raise RuntimeError(f"xpra start failed: {stdout} {stderr}")

        logger.info(f"xpra session {session_name} started successfully on display :{display}")

        # Extract container IP
        networks = container["NetworkSettings"]["Networks"]
        container_ip = networks.get(self.network_name, {}).get("IPAddress", "")

        if not container_ip:
            logger.error(f"Container {container_name} has no IP in network {self.network_name}")
            raise RuntimeError("Container has no IP address")

        # Start Wireshark in background (fire-and-forget, no waiting)
        wireshark_cmd = (
            f"curl -N -H 'Authorization: Bearer {jwt_token}' "
            f"'{capture_stream_url}' | "
            f"wireshark -i - -k --fullscreen -display :{display} &"
        )

        logger.info(f"[Web Wireshark] Starting Wireshark with capture stream URL: {capture_stream_url}")
        logger.info(f"[Web Wireshark] Display: :{display}, Container IP: {container_ip}, Port: {port}")

        # Execute Wireshark command without waiting for completion
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", container_id,
            "bash", "-c", wireshark_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Don't wait - Wireshark runs in background
        logger.info(f"[Web Wireshark] Wireshark start command executed for link {link_id}")

        result = {
            "link_id": link_id,
            "display": display,
            "port": port,
            "ws_url": f"ws://{container_ip}:{port}",
            "container_name": container_name,
            "container_id": container_id,
            "session_name": session_name,
            "capture_stream_url": capture_stream_url
        }

        logger.info(f"Web Wireshark session started successfully: {result['ws_url']}")
        return result

    async def stop_wireshark_session(self, project_id: str, link_id: str):
        """Stop Web Wireshark session.

        Args:
            project_id: Project ID
            link_id: Link ID
        """
        logger.info(f"Stopping Web Wireshark session for link {link_id}")
        try:
            container_name = f"gns3-wireshark-{project_id}"
            container = await self.docker.get_container(container_name)

            if not container:
                logger.warning(f"Container {container_name} not found")
                return

            # Get display number
            display = link_id_to_display(link_id)

            # Kill all processes associated with this display using process tree kill
            # This ensures child processes are properly terminated, not left as zombies
            logger.info(f"Stopping all processes on display :{display}")
            patterns = [
                f'xpra.*:{display}',
                f'Xvfb.*:{display}',
                f'Xvfb-for-Xpra-{display}',
                f'wireshark.*:{display}',
                f'pulseaudio.*display=:{display}'
            ]
            await self._kill_process_tree_batch(container["Id"], patterns)
            await self._cleanup_x_lock(container["Id"], display)

            logger.info("Web Wireshark session stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping session: {e}")

    async def restart_wireshark_session(
        self,
        project_id: str,
        link_id: str,
        jwt_token: str,
        capture_stream_url: str = None,
        image: str = "gns3/web-wireshark:latest",
        memory: str = "2g",
        memory_swap: str = None,
        cpus: float = 1.0,
        pids_limit: int = 1000
    ):
        """Restart Web Wireshark session.

        This simply calls start_wireshark_session since it already handles
        cleanup of existing processes.

        Args:
            project_id: Project ID
            link_id: Link ID
            jwt_token: JWT authentication token
            capture_stream_url: Capture stream URL
            image: Docker image name
            memory: Memory limit
            memory_swap: Memory swap limit
            cpus: CPU cores
            pids_limit: Process limit

        Returns:
            Session info dict
        """
        return await self.start_wireshark_session(
            project_id=project_id,
            link_id=link_id,
            jwt_token=jwt_token,
            capture_stream_url=capture_stream_url,
            image=image,
            memory=memory,
            memory_swap=memory_swap,
            cpus=cpus,
            pids_limit=pids_limit
        )

    async def stop_all_sessions(self, project_id: str):
        """Stop all Web Wireshark sessions for a project.

        Args:
            project_id: Project ID
        """
        logger.info(f"Stopping all Web Wireshark sessions for project {project_id}")
        try:
            container_name = f"gns3-wireshark-{project_id}"
            container = await self.docker.get_container(container_name)

            if not container:
                logger.warning(f"Container {container_name} not found")
                return

            # Kill all wireshark, xpra and Xvfb processes for link sessions
            # This ensures clean removal of all session processes
            patterns = [
                "xpra.*--session-name=link-",
                "Xvfb-for-Xpra-",
                "wireshark.*display :",
                "pulseaudio.*display :"
            ]
            await self._kill_process_tree_batch(container["Id"], patterns)

            logger.info(f"All Web Wireshark sessions stopped for project {project_id}")

        except Exception as e:
            # Don't fail if container is already stopped or doesn't exist
            logger.warning(f"Error stopping all sessions: {e}")

    async def stop_container(self, project_id: str):
        """Stop Web Wireshark container.

        Args:
            project_id: Project ID
        """
        logger.info(f"Stopping Web Wireshark container for project {project_id}")
        try:
            container_name = f"gns3-wireshark-{project_id}"
            container = await self.docker.get_container(container_name)

            if not container:
                logger.warning(f"Container {container_name} not found")
                return

            if not container["State"]["Running"]:
                logger.info(f"Container {container_name} is not running")
                return

            await self.docker.stop_container(container["Id"])
            logger.info(f"Container {container_name} stopped")

        except Exception as e:
            logger.error(f"Error stopping container: {e}")

    async def delete_container(self, project_id: str):
        """Delete Web Wireshark container.

        Args:
            project_id: Project ID
        """
        logger.info(f"Deleting Web Wireshark container for project {project_id}")
        try:
            container_name = f"gns3-wireshark-{project_id}"
            container = await self.docker.get_container(container_name)

            if not container:
                logger.info(f"Container {container_name} not found, nothing to delete")
                return

            # Stop first if running
            if container["State"]["Running"]:
                await self.docker.stop_container(container["Id"])

            # Remove container
            await self.docker.remove_container(container["Id"], force=True)
            logger.info(f"Container {container_name} deleted")

        except Exception as e:
            logger.error(f"Error deleting container: {e}")
