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
from typing import Optional

from gns3server.utils.port_allocator import link_id_to_display, link_id_to_port
from .docker_client import DockerHTTPClient

logger = logging.getLogger(__name__)

# Default GNS3 server address
DEFAULT_GNS3_URL = "http://127.0.0.1:3080"


class WebWiresharkManager:
    """Manages Web Wireshark sessions and containers."""

    # Container command execution timeout (seconds)
    CONTAINER_EXEC_TIMEOUT = 5

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

    def _get_gns3_url_from_controller(self) -> Optional[str]:
        """Get GNS3 server URL from Controller instance.

        Reference: gns3-copilot implementation.
        """
        try:
            from gns3server.controller import Controller
            controller = Controller.instance()
            local_compute = controller.get_compute("local")

            url = f"{local_compute.protocol}://{local_compute.host}:{local_compute.port}"
            logger.info(f"Got GNS3 URL from Controller: {url}")
            return url
        except ImportError as e:
            logger.debug(f"Cannot import Controller: {e}")
            return None
        except AttributeError as e:
            logger.debug(f"Controller instance not available: {e}")
            return None
        except KeyError as e:
            logger.debug(f"Local compute not found in Controller: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error getting URL from Controller: {e}")
            return None

    def _get_gns3_url_from_config(self) -> Optional[str]:
        """Get GNS3 server URL from config file."""
        try:
            from gns3server.config import Config
            server_config = Config.instance().settings.Server
            url = f"{server_config.protocol.value}://{server_config.host}:{server_config.port}"
            logger.info(f"Got GNS3 URL from Config: {url}")
            return url
        except Exception as e:
            logger.debug(f"Cannot get URL from Config: {e}")
        return None

    def detect_gns3_url(self) -> str:
        """Detect GNS3 server URL using multiple strategies.

        Returns:
            GNS3 server URL
        """
        # Strategy 1: Get from Controller
        url = self._get_gns3_url_from_controller()
        if url:
            return url

        # Strategy 2: Get from Config
        url = self._get_gns3_url_from_config()
        if url:
            return url

        # Strategy 3: Use default
        logger.warning(f"Using fallback default URL: {DEFAULT_GNS3_URL}")
        return DEFAULT_GNS3_URL

    async def ensure_network(self):
        """Ensure Docker network exists."""
        from gns3server.config import Config

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
                logger.info("Container is running, checking health...")
                if await self._is_container_healthy(container["Id"]):
                    logger.info(f"Container {container_name} already running and healthy")
                    return container["Id"]
                else:
                    # Container is running but unresponsive, force remove
                    logger.warning(f"Container {container_name} is not responding, force removing...")
                    try:
                        await self.docker.remove_container(container["Id"], force=True)
                        logger.info(f"Container {container_name} force removed")
                    except Exception as e:
                        logger.warning(f"Failed to remove unhealthy container: {e}")
                    container = None  # Trigger recreation
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

        # Allocate display and port using deterministic hash
        display = link_id_to_display(link_id)
        port = link_id_to_port(link_id)

        # Start xpra session
        session_name = f"link-{link_id}"
        logger.info(f"Starting xpra session {session_name} on display :{display}")

        xpra_cmd = [
            "XPRA_CLIENT_CAN_SHUTDOWN=false",
            "xpra", "start", f":{display}",
            '--xvfb="Xvfb -screen 0 1920x1080x24 +extension RANDR"',
            "--html=no",
            f"--bind-tcp=0.0.0.0:{port}",
            f"--session-name={session_name}",
            "--daemon=yes",
            "--dbus-launch=no",
            "--resize-display=yes"
        ]

        # Start xpra session (xpra start will reuse existing display)
        returncode, stdout, stderr = await self._exec_in_container(
            container_id,
            " ".join(xpra_cmd)
        )

        if returncode != 0:
            logger.error(f"xpra start failed (code {returncode}): {stdout} {stderr}")
            raise RuntimeError(f"xpra start failed: {stdout} {stderr}")

        # Verify xpra session started successfully (xpra list shows display number, not session name)
        returncode, stdout, stderr = await self._exec_in_container(
            container_id,
            f"xpra list 2>&1 | grep -q ':{display}'"
        )

        if returncode != 0:
            _, xpra_output, _ = await self._exec_in_container(container_id, "xpra list 2>&1")
            logger.error(f"xpra session verification failed. xpra list output:\n{xpra_output}")
            raise RuntimeError(f"xpra session {session_name} failed to start")

        logger.info(f"xpra session {session_name} started successfully on display :{display}")

        # Start Wireshark and connect to capture stream (run in background with &)
        wireshark_cmd = (
            f"curl -N -H 'Authorization: Bearer {jwt_token}' "
            f"'{capture_stream_url}' | "
            f"wireshark -i - -k --fullscreen -display :{display} &"
        )

        logger.info(f"Starting Wireshark with capture stream: {capture_stream_url}")

        # Don't wait for wireshark to complete - it runs continuously
        returncode, stdout, stderr = await self._exec_in_container(
            container_id,
            wireshark_cmd,
            timeout=5  # Short timeout since it runs in background
        )

        if returncode != 0:
            logger.warning(f"Wireshark start returned code {returncode}: {stdout} {stderr}")

        # Get container IP
        container = await self.docker.get_container(container_name)
        networks = container["NetworkSettings"]["Networks"]
        container_ip = networks.get(self.network_name, {}).get("IPAddress", "")

        if not container_ip:
            logger.error(f"Container {container_name} has no IP in network {self.network_name}")
            raise RuntimeError("Container has no IP address")

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

            # Stop xpra session
            logger.info(f"Stopping xpra session :{display}")
            await self._exec_in_container(
                container["Id"],
                f"pkill -f 'xpra.*:{display}'"
            )

            logger.info("Web Wireshark session stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping session: {e}")

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

            # Stop all xpra sessions (display 100-199)
            for display in range(100, 200):
                await self._exec_in_container(
                    container["Id"],
                    f"pkill -f 'xpra.*:{display}'"
                )
                logger.info(f"Stopped xpra session :{display}")

            logger.info(f"All Web Wireshark sessions stopped for project {project_id}")

        except Exception as e:
            logger.error(f"Error stopping all sessions: {e}")

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
