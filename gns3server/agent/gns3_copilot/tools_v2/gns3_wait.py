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

GNS3-Copilot wait tool.

start_gns3_node returns as soon as the start commands are accepted — nodes
keep booting in the background. This tool gives the agent a deliberate
pause it controls itself (instead of a hard-coded progress bar inside the
start tool), so the usual flow is: start_gns3_node → wait_seconds → check
node status / run show commands.
"""

import json
import logging
import time
from typing import Any

from langchain.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun

# Configure logging
logger = logging.getLogger(__name__)

# Hard ceiling so a hallucinated "wait 999999" cannot wedge the agent loop.
MAX_WAIT_SECONDS = 600
# Log a liveness line every few seconds so long waits are visible in the
# server log.
LOGBOOK_TICK = 5


class GNS3WaitTool(BaseTool):
    """
    A LangChain tool that sleeps for a given number of seconds.

    **Input**:
    A JSON object with seconds (integer, 1-600).
    Example:
        {"seconds": 30}

    **Output**:
    {"waited": 30}
    """

    name: str = "wait_seconds"
    description: str = """
    Pause execution for a given number of seconds (1-600), then continue.
    Use after start_gns3_node (which returns immediately) to let nodes
    boot before checking status: VPCS/IOU ~15-30s, IOS/IOL routers
    ~60-120s, heavy NOS images (XRd, SR Linux) 2-5min. Prefer several
    short waits with a status check in between over one long blind wait.
    Input: JSON with seconds (integer).
    Returns: {"waited": <seconds>}.
    """

    def _run(
        self,
        tool_input: str,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> dict[str, Any]:
        try:
            input_data = json.loads(tool_input)
            seconds = input_data.get("seconds")
            if isinstance(seconds, str) and seconds.strip().isdigit():
                seconds = int(seconds.strip())
            if not isinstance(seconds, int) or isinstance(seconds, bool):
                return {"error": "seconds must be an integer (1-600)."}
            if not 1 <= seconds <= MAX_WAIT_SECONDS:
                return {"error": f"seconds must be between 1 and {MAX_WAIT_SECONDS}."}

            logger.info("Waiting %d seconds...", seconds)
            waited = 0
            while waited < seconds:
                tick = min(LOGBOOK_TICK, seconds - waited)
                time.sleep(tick)
                waited += tick
                logger.info("Waited %d/%d seconds", waited, seconds)
            return {"waited": waited}

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON input: %s", e)
            return {"error": f"Invalid JSON input: {e}"}
        except Exception as e:
            logger.error("Wait tool failed: %s", e)
            return {"error": f"Wait tool failed: {e!s}"}
