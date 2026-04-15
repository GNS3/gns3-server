# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# This file is part of GNS3-Copilot project.
#
# GNS3-Copilot is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GNS3-Copilot is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNS3-Copilot. If not, see <https://www.gnu.org/licenses/>.
#
# Copyright (C) 2025 Yue Guobin (岳国宾)
# Author: Yue Guobin (岳国宾)
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

"""
Packet Capture Analysis Tool

Analyzes packets from an active GNS3 capture using tshark.
Downloads the capture file from GNS3 server and runs tshark analysis.

Usage:
    The user can ask AI to analyze specific packets, e.g., "explain packet #42".
    The tool will download the capture file and use tshark to extract
    detailed information about the specified packet.
"""

import logging
import os
import shlex
import subprocess
import tempfile

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

from gns3server.agent.gns3_copilot.gns3_client.context_helpers import (
    get_current_jwt_token,
)

logger = logging.getLogger(__name__)

# Default tshark arguments
DEFAULT_TSHARK_ARGS = "-qz io,phs"


class PacketCaptureTool(BaseTool):
    """
    LangChain tool for analyzing packets from an active GNS3 capture.

    This tool:
    1. Downloads the capture file from GNS3 server via /capture/file endpoint
    2. Saves it to a temporary file
    3. Runs tshark with the provided arguments
    4. Returns the analysis results

    Input:
        project_id (str, required): UUID of the GNS3 project
        link_id (str, required): UUID of the link to analyze
        tshark_args (str, optional): tshark command arguments
            - Default: "-qz io,phs" (protocol hierarchy statistics)
            - For specific packet: '-Y "frame.number == 42" -T fields -e *'
            - For context: '-Y "frame.number >= 40 && frame.number <= 44" -T fields -e frame.number -e ip.src -e ip.dst -e _ws.col.Info'
        max_lines (int, optional): Maximum lines to return (default: 100)
        timeout (int, optional): Timeout for tshark execution in seconds (default: 30)

    Output:
        str: tshark analysis results

    Example:
        # Analyze packet #42
        tool._run(
            project_id="xxx",
            link_id="yyy",
            tshark_args='-Y "frame.number == 42" -T fields -e *',
            max_lines=100
        )
    """

    name: str = "analyze_packets"
    description: str = """
    Analyze packets from an active GNS3 capture using tshark.

    Downloads the capture file from GNS3 server and runs tshark analysis.

    Input (JSON format):
        - project_id (str, required): UUID of the GNS3 project
        - link_id (str, required): UUID of the link to analyze
        - tshark_args (str, optional): tshark arguments. Default is "-qz io,phs" (protocol statistics).
          Common patterns:
          - Specific packet: '-Y "frame.number == 42" -T fields -e *'
          - Context packets: '-Y "frame.number >= 40 && frame.number <= 44" -T fields -e frame.number -e ip.src -e ip.dst'
          - TCP traffic: '-Y "tcp" -c 50 -T fields -e ip.src -e ip.dst -e tcp.port'
          - HTTP analysis: '-Y "http" -T fields -e ip.src -e http.host -e http.request.uri'
          - Expert info: '-z expert'
        - max_lines (int, optional): Maximum output lines (default: 100, use 0 for unlimited)
        - timeout (int, optional): tshark timeout in seconds (default: 30)

    Output:
        tshark analysis results as text

    Note:
        The capture must be active (started via GNS3 Web UI) before using this tool.
    """

    def _run(
        self,
        project_id: str,
        link_id: str,
        tshark_args: str = DEFAULT_TSHARK_ARGS,
        max_lines: int = 100,
        timeout: int = 30,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        """
        Analyze packets from an active GNS3 capture.

        Args:
            project_id: UUID of the GNS3 project
            link_id: UUID of the link to analyze
            tshark_args: tshark command arguments
            max_lines: Maximum lines to return
            timeout: Timeout for tshark execution in seconds
            run_manager: LangChain run manager (unused)

        Returns:
            str: tshark analysis results
        """
        logger.info(
            f"PacketCaptureTool invoked: project_id={project_id}, link_id={link_id}, "
            f"tshark_args={tshark_args}, max_lines={max_lines}, timeout={timeout}"
        )

        # Validate inputs
        if not project_id:
            return '{"error": "project_id is required"}'
        if not link_id:
            return '{"error": "link_id is required"}'

        temp_file = None
        try:
            # Download capture file
            temp_file = self._download_capture(project_id, link_id)
            if not temp_file:
                return '{"error": "Failed to download capture file"}'

            # Check if file exists and has content
            if not os.path.exists(temp_file):
                return '{"error": "Capture file not found"}'

            file_size = os.path.getsize(temp_file)
            if file_size == 0:
                return '{"error": "Capture file is empty, no packets captured yet"}'

            logger.info(f"Capture file downloaded: {temp_file}, size={file_size} bytes")

            # Run tshark analysis
            result = self._run_tshark(temp_file, tshark_args, max_lines, timeout)
            return result

        except Exception as e:
            logger.error(f"PacketCaptureTool error: {e}", exc_info=True)
            return f'{{"error": "Analysis failed: {str(e)}"}}'

        finally:
            # Clean up temp file
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    logger.debug(f"Temporary file removed: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to remove temp file: {e}")

    def _download_capture(self, project_id: str, link_id: str) -> str | None:
        """
        Download capture file from GNS3 server.

        Args:
            project_id: Project UUID
            link_id: Link UUID

        Returns:
            str: Path to temporary capture file, or None on failure
        """
        jwt_token = get_current_jwt_token()
        if not jwt_token:
            logger.error("JWT token not found in context")
            return None

        # Detect GNS3 server URL
        url = self._detect_gns3_url()
        if not url:
            return None

        capture_url = f"{url}/v3/projects/{project_id}/links/{link_id}/capture/file"
        logger.info(f"Downloading capture from: {capture_url}")

        # Create temp file
        temp_fd, temp_file = tempfile.mkstemp(suffix=".pcap", prefix="gns3_capture_")
        os.close(temp_fd)

        try:
            # Run synchronous download using requests
            import requests

            headers = {"Authorization": f"Bearer {jwt_token}"}
            response = requests.get(
                capture_url,
                headers=headers,
                stream=True,
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(f"Failed to download capture: HTTP {response.status_code}")
                os.remove(temp_file)
                return None

            # Write to temp file
            with open(temp_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"Capture file saved: {temp_file}, size={os.path.getsize(temp_file)} bytes")
            return temp_file

        except Exception as e:
            logger.error(f"Failed to download capture: {e}", exc_info=True)
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return None

    def _detect_gns3_url(self) -> str | None:
        """
        Detect GNS3 server URL from Controller or Config.

        Returns:
            str: GNS3 server URL, or None on failure
        """
        try:
            from gns3server.controller import Controller

            controller = Controller.instance()
            local_compute = controller.get_compute("local")
            url = f"{local_compute.protocol}://{local_compute.host}:{local_compute.port}"
            logger.debug(f"Detected GNS3 URL from Controller: {url}")
            return url
        except Exception as e:
            logger.debug(f"Cannot get URL from Controller: {e}")

        try:
            from gns3server.config import Config

            server_config = Config.instance().settings.Server
            url = f"{server_config.protocol.value}://{server_config.host}:{server_config.port}"
            logger.debug(f"Detected GNS3 URL from Config: {url}")
            return url
        except Exception as e:
            logger.debug(f"Cannot get URL from Config: {e}")

        # Fallback default
        default_url = "http://127.0.0.1:3080"
        logger.warning(f"Using fallback default URL: {default_url}")
        return default_url

    def _run_tshark(
        self, pcap_file: str, tshark_args: str, max_lines: int, timeout: int
    ) -> str:
        """
        Run tshark to analyze the capture file.

        Args:
            pcap_file: Path to the capture file
            tshark_args: tshark command arguments
            max_lines: Maximum lines to return
            timeout: Timeout in seconds

        Returns:
            str: tshark output
        """
        # Parse arguments and handle display filter conflicts
        # If both -Y and positional filter are provided, combine them with "and"
        # Use shlex.split() to properly handle quoted arguments
        args_list = shlex.split(tshark_args)
        cmd = ["tshark", "-r", pcap_file]
        display_filter = None

        i = 0
        while i < len(args_list):
            arg = args_list[i]
            if arg == "-Y" or arg == "-R":
                # -Y or -R specifies a display filter
                if i + 1 < len(args_list):
                    display_filter = args_list[i + 1]
                    i += 2
                else:
                    i += 1
            elif arg.startswith("-"):
                # Other flags that take arguments
                if arg in ("-e", "-T", "-c", "-w", "-F", "-b", "-a", "-f"):
                    cmd.extend([arg, args_list[i + 1]])
                    i += 2
                else:
                    cmd.append(arg)
                    i += 1
            else:
                # Positional argument (likely a display filter without -Y)
                if display_filter:
                    # Combine with existing -Y filter using "and"
                    display_filter = f"({display_filter}) and ({arg})"
                else:
                    display_filter = arg
                i += 1

        # Add the combined display filter with -Y
        if display_filter:
            cmd.extend(["-Y", display_filter])

        logger.info(f"Running tshark: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            output = result.stdout
            if result.stderr and "tshark:" in result.stderr:
                # Only log tshark errors, not warnings like filter conflicts
                if "error" in result.stderr.lower():
                    logger.warning(f"tshark stderr: {result.stderr}")

            # Handle empty output
            if not output.strip():
                return "No packets match the filter criteria."

            # Limit output lines
            if max_lines > 0:
                lines = output.split("\n")
                if len(lines) > max_lines:
                    output = "\n".join(lines[:max_lines])
                    output += f"\n... (truncated, {len(lines) - max_lines} more lines)"

            logger.info(f"tshark output: {len(output)} characters")
            return output

        except subprocess.TimeoutExpired:
            logger.error(f"tshark timeout after {timeout} seconds")
            return f'{{"error": "tshark timeout after {timeout} seconds"}}'
        except FileNotFoundError:
            logger.error("tshark not found. Please install tshark: apt install tshark")
            return '{"error": "tshark not installed. Please install tshark: apt install tshark"}'
        except Exception as e:
            logger.error(f"tshark execution error: {e}", exc_info=True)
            return f'{{"error": "tshark failed: {str(e)}"}}'


if __name__ == "__main__":
    # Test the tool
    tool = PacketCaptureTool()

    # Example: Analyze packet #42 from a link
    # Replace with actual project_id and link_id
    print("Testing PacketCaptureTool...")
    print("Note: Set project_id and link_id to test with actual GNS3 capture")
    print(tool.description)
