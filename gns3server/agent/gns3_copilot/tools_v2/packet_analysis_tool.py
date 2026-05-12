# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# This file is part of GNS3-Copilot project.
#
# GNS3-Copilot is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
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
Protocol-Oriented Packet Analysis Tool

Analyzes packets from an active GNS3 capture using tshark with user-provided arguments.
The LLM constructs tshark commands based on protocol knowledge from packet analysis skills.
"""

import json
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

# Cache of valid tshark field names, loaded lazily from `tshark -G fields`
_tshark_valid_fields: set | None = None


class PacketAnalysisTool(BaseTool):
    """
    LangChain tool for analyzing packets using tshark with user-provided arguments.

    The LLM constructs tshark command arguments based on protocol knowledge
    from packet analysis skills (available_fields, base_filter, etc.).

    Input:
        project_id (str, required): UUID of the GNS3 project
        link_id (str, required): UUID of the link to analyze
        tshark_args (str, required): tshark command arguments (after '-r <pcap>')

    Output:
        str: tshark output in text format (tab-separated fields or JSON)
    """

    name: str = "packet_analysis"
    description: str = """
    Analyze packets from an active GNS3 capture using tshark.

    Use this to analyze captured packets when diagnosing network issues.

    **Before calling this tool**, first query `get_packet_analysis_protocol`
    to get the correct tshark field names and display filter for the protocol.
    Construct `tshark_args` from the skills data, not from memory.

    Input (JSON format):
        - project_id (str, required): UUID of the GNS3 project
        - link_id (str, required): UUID of the link to analyze
        - tshark_args (str, required): tshark command arguments (after '-r <pcap>')

    Common tshark argument patterns:
        -Y "<filter>"     Display filter
        -T fields         Tab-separated field output
        -e <field>        Extract field (use multiple -e for multiple fields)
        -T json           JSON output
        -c <count>        Limit packets READ (not matched count). Since -c limits
                          total packets scanned, it can hide results when used
                          with -Y. Prefer piping to head -10 or rely on -Y
                          alone instead.
    """

    @classmethod
    def _load_valid_tshark_fields(cls) -> set:
        """
        Load and cache valid tshark field names from `tshark -G fields`.

        Returns:
            Set of valid field names, or empty set on failure.
        """
        global _tshark_valid_fields
        if _tshark_valid_fields is not None:
            return _tshark_valid_fields

        try:
            result = subprocess.run(
                ["tshark", "-G", "fields"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            fields = set()
            for line in result.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    fields.add(parts[2])
            _tshark_valid_fields = fields
            logger.debug(f"Loaded {len(fields)} valid tshark field names")
        except Exception as e:
            logger.warning(f"Could not load tshark field names: {e}")
            _tshark_valid_fields = set()

        return _tshark_valid_fields

    def _validate_tshark_args(self, tshark_args: str) -> str | None:
        """
        Validate tshark arguments before execution.

        Checks `-e` field names against the tshark field registry.
        Returns an error JSON string if invalid, or None if valid.

        Args:
            tshark_args: tshark command arguments string

        Returns:
            Error JSON string, or None if validation passes.
        """
        import shlex

        try:
            args = shlex.split(tshark_args)
        except ValueError as e:
            return json.dumps({"error": f"Invalid tshark_args syntax: {e}"})

        valid_fields = self._load_valid_tshark_fields()
        if not valid_fields:
            return None

        invalid_fields = []
        i = 0
        while i < len(args):
            if args[i] == "-e" and i + 1 < len(args):
                field = args[i + 1]
                if field not in valid_fields:
                    invalid_fields.append(field)
                i += 2
            else:
                i += 1

        if invalid_fields:
            return json.dumps({
                "error": f"Invalid tshark field names: {', '.join(invalid_fields)}",
                "hint": "Use packet_analysis_skills tool to look up valid field names for the protocol",
                "invalid_fields": invalid_fields,
            })

        return None

    def _run(
        self,
        project_id: str,
        link_id: str,
        tshark_args: str,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        """
        Analyze packets using tshark with user-provided arguments.

        Args:
            project_id: UUID of the GNS3 project
            link_id: UUID of the link to analyze
            tshark_args: tshark command arguments (after '-r <pcap>')
            run_manager: LangChain run manager (unused)

        Returns:
            str: tshark output
        """
        logger.info(
            f"PacketAnalysisTool invoked: project_id={project_id}, "
            f"link_id={link_id}, tshark_args={tshark_args}"
        )

        # Validate inputs
        if not project_id:
            return '{"error": "project_id is required"}'
        if not link_id:
            return '{"error": "link_id is required"}'
        if not tshark_args or not tshark_args.strip():
            return '{"error": "tshark_args is required"}'

        # Pre-validate tshark field names before downloading capture
        validation_error = self._validate_tshark_args(tshark_args)
        if validation_error:
            return validation_error

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

            # Run tshark with user-provided arguments
            result = self._run_tshark(temp_file, tshark_args)
            return result

        except Exception as e:
            logger.error(f"PacketAnalysisTool error: {e}", exc_info=True)
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
            # Use verify=False for HTTPS to skip certificate validation (for self-signed certs)
            verify_cert = not capture_url.startswith("https://")
            response = requests.get(
                capture_url,
                headers=headers,
                stream=True,
                timeout=30,
                verify=verify_cert,
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

    def _run_tshark(self, pcap_file: str, tshark_args: str) -> str:
        """
        Run tshark with user-provided arguments.

        Args:
            pcap_file: Path to the capture file
            tshark_args: tshark command arguments (after '-r <pcap>')

        Returns:
            str: tshark output
        """
        # Build command: tshark -r <file> <user_args>
        import shlex
        cmd = ["tshark", "-r", pcap_file] + shlex.split(tshark_args)

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
                return "No matching packets found"

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
    tool = PacketAnalysisTool()
    print("Testing PacketAnalysisTool...")
    print("Note: Set project_id, link_id and tshark_args to test with actual GNS3 capture")
    print(tool.description)
