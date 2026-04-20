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

Analyzes specific packets from an active GNS3 capture using tshark.
Downloads the capture file from GNS3 server and returns detailed packet information.
"""

import logging
import os
import subprocess
import tempfile

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

from gns3server.agent.gns3_copilot.gns3_client.context_helpers import (
    get_current_jwt_token,
)

logger = logging.getLogger(__name__)


class PacketCaptureTool(BaseTool):
    """
    LangChain tool for analyzing a specific packet from an active GNS3 capture.

    This tool:
    1. Downloads the capture file from GNS3 server via /capture/file endpoint
    2. Saves it to a temporary file
    3. Runs tshark with verbose output (-V) for the specified packet
    4. Returns the complete packet structure

    Input:
        project_id (str, required): UUID of the GNS3 project
        link_id (str, required): UUID of the link to analyze
        packet_number (int, required): The packet number to analyze

    Output:
        str: Detailed packet information in text format
    """

    name: str = "analyze_packets"
    description: str = """
    Analyze a specific packet from an active GNS3 capture using tshark.

    Downloads the capture file from GNS3 server and returns detailed packet information.

    Input (JSON format):
        - project_id (str, required): UUID of the GNS3 project
        - link_id (str, required): UUID of the link to analyze
        - packet_number (int, required): The packet number to analyze

    Output:
        Complete packet structure in verbose text format

    Example:
        # Analyze packet #42
        tool._run(
            project_id="xxx",
            link_id="yyy",
            packet_number=42
        )
    """

    def _run(
        self,
        project_id: str,
        link_id: str,
        packet_number: int,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        """
        Analyze a specific packet from an active GNS3 capture.

        Args:
            project_id: UUID of the GNS3 project
            link_id: UUID of the link to analyze
            packet_number: The packet number to analyze
            run_manager: LangChain run manager (unused)

        Returns:
            str: Detailed packet information
        """
        logger.info(
            f"PacketCaptureTool invoked: project_id={project_id}, "
            f"link_id={link_id}, packet_number={packet_number}"
        )

        # Validate inputs
        if not project_id:
            return '{"error": "project_id is required"}'
        if not link_id:
            return '{"error": "link_id is required"}'
        if packet_number is None or packet_number <= 0:
            return '{"error": "packet_number must be a positive integer"}'

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

            # Run tshark verbose analysis for the specific packet
            result = self._run_tshark_verbose(temp_file, packet_number)
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

    def _run_tshark_verbose(self, pcap_file: str, packet_number: int) -> str:
        """
        Run tshark verbose output for a specific packet.

        Args:
            pcap_file: Path to the capture file
            packet_number: The packet number to analyze

        Returns:
            str: tshark verbose output
        """
        # Build command: tshark -r <file> -Y "frame.number == N" -V
        cmd = [
            "tshark",
            "-r", pcap_file,
            "-Y", f"frame.number == {packet_number}",
            "-V"
        ]

        logger.info(f"Running tshark: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            output = result.stdout
            if result.stderr:
                if "tshark:" in result.stderr.lower():
                    logger.warning(f"tshark stderr: {result.stderr}")

            if not output.strip():
                return f'No packet found with frame.number == {packet_number}'

            logger.info(f"tshark output: {len(output)} characters")
            return output

        except subprocess.TimeoutExpired:
            logger.error("tshark timeout after 30 seconds")
            return '{"error": "tshark timeout after 30 seconds"}'
        except FileNotFoundError:
            logger.error("tshark not found. Please install tshark: apt install tshark")
            return '{"error": "tshark not installed. Please install tshark: apt install tshark"}'
        except Exception as e:
            logger.error(f"tshark execution error: {e}", exc_info=True)
            return f'{{"error": "tshark failed: {str(e)}"}}'


if __name__ == "__main__":
    # Test the tool
    tool = PacketCaptureTool()
    print("Testing PacketCaptureTool...")
    print("Note: Set project_id, link_id and packet_number to test with actual GNS3 capture")
    print(tool.description)
