"""
Web Wireshark statistics collection utilities.

This module provides functions to collect and aggregate statistics
about Web Wireshark containers and sessions.
"""

import logging
import subprocess
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


async def collect_webwireshark_stats(projects: List) -> Dict:
    """
    Collect Web Wireshark container statistics across all projects.

    Args:
        projects: List of project objects to check for containers

    Returns:
        Dictionary with aggregated statistics:
        {
            "total_containers": int,
            "running_containers": int,
            "active_sessions": int,
            "containers": [list of container details]
        }
    """
    from .manager import WebWiresharkManager

    stats = {
        "total_containers": 0,
        "running_containers": 0,
        "active_sessions": 0,
        "containers": []
    }

    # Create a single manager instance and reuse it
    manager = WebWiresharkManager()

    try:
        # Check Web Wireshark containers for each opened project
        for project in projects:
            if project.status != "opened":
                continue

            container_name = f"gns3-wireshark-{project.id}"
            container = await manager.docker.get_container(container_name)

            if container:
                stats["total_containers"] += 1

                container_info = {
                    "project_id": project.id,
                    "project_name": project.name,
                    "container_id": container["Id"][:12],
                    "status": container["State"]["Status"],
                    "running": container["State"]["Running"],
                }

                if container["State"]["Running"]:
                    stats["running_containers"] += 1

                    # Get container resource limits from HostConfig
                    host_config = container.get("HostConfig", {})
                    memory_limit = host_config.get("Memory", 0)
                    cpu_quota = host_config.get("NanoCpus", 0)
                    pids_limit = host_config.get("PidsLimit", 0)

                    # Count active capture sessions
                    active_sessions = sum(
                        1 for link in project.links.values()
                        if getattr(link, "capturing", False)
                    )
                    stats["active_sessions"] += active_sessions
                    container_info["active_sessions"] = active_sessions

                    # Add resource limits
                    container_info["memory_limit"] = f"{memory_limit / (1024**3):.1f} GB" if memory_limit > 0 else "unlimited"
                    container_info["cpu_limit"] = f"{cpu_quota / 1000000000:.1f}" if cpu_quota > 0 else "unlimited"
                    container_info["pids_limit"] = pids_limit if pids_limit > 0 else "unlimited"

                    # Get resource usage via docker stats
                    resource_stats = await _get_container_resource_stats(container["Id"])
                    if resource_stats:
                        container_info.update(resource_stats)

                stats["containers"].append(container_info)

    except Exception as e:
        logger.warning(f"Could not retrieve Web Wireshark statistics: {e}")

    finally:
        # Always close the manager to cleanup aiohttp sessions
        await manager.close()

    return stats


async def _get_container_resource_stats(container_id: str) -> Optional[Dict]:
    """
    Get resource usage statistics for a container.

    Args:
        container_id: Docker container ID

    Returns:
        Dictionary with memory, cpu, and pids, or None if failed
    """
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format",
             "{{.MemUsage}}\t{{.CPUPerc}}\t{{.PIDs}}",
             container_id],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split("\t")
            if len(parts) >= 3:
                return {
                    "memory": parts[0],
                    "cpu": parts[1],
                    "pids": int(parts[2])
                }
    except subprocess.TimeoutExpired:
        logger.debug(f"Docker stats timeout for container {container_id[:12]}")
    except Exception as e:
        logger.debug(f"Failed to get stats for container {container_id[:12]}: {e}")

    return None
