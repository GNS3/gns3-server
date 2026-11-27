"""Compute RPC helper shared by the configuration controller modules.

Compute failures are mapped to public configuration codes in exactly one place.
"""

import logging

from fastapi import HTTPException

from gns3server.controller.controller_error import (
    ComputeConflictError,
    ComputeError,
    ControllerError,
    ControllerTimeoutError,
    ControllerUnauthorizedError,
)
from gns3server.services.configurations.shared.errors import CONTROLLER_ERRORS, ConfigurationError

log = logging.getLogger(__name__)

# The compute could not be reached or did not answer in time.
UNREACHABLE = (ComputeError, ControllerTimeoutError, ControllerUnauthorizedError, TimeoutError, OSError)


def safe_error(code):
    return code if isinstance(code, str) and code in CONTROLLER_ERRORS else "configuration_operation_failed"


def compute_failure(node, path, error):
    """Map a compute failure to a public code, logging the underlying error.

    Only a compute that cannot be reached is reported as unavailable; any other
    failure (an error status or an invalid answer from a reachable compute) is
    an operation failure and must not be hidden behind the unavailable code.
    """
    log.warning(
        "Compute request for node %s %s failed: %s: %s",
        getattr(node, "id", node),
        path,
        type(error).__name__,
        getattr(error, "detail", None) or error,
    )
    if isinstance(error, ComputeConflictError):
        return ConfigurationError(safe_error(error.response().get("message")))
    if isinstance(error, UNREACHABLE):
        return ConfigurationError("configuration_compute_unavailable")
    return ConfigurationError("configuration_operation_failed")


async def compute_get(node, path):
    try:
        response = await node.get(path, timeout=30)
        return response.json
    except (ControllerError, HTTPException, OSError, TimeoutError) as error:
        raise compute_failure(node, path, error) from None
