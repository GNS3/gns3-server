import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from gns3server.controller.configuration_rpc import compute_get
from gns3server.controller.controller_error import (
    ComputeConflictError,
    ComputeError,
    ControllerNotFoundError,
    ControllerTimeoutError,
)
from gns3server.services.configurations.shared.errors import ConfigurationError

pytestmark = pytest.mark.asyncio


async def failing(error):
    node = SimpleNamespace(id="n1", get=AsyncMock(side_effect=error))
    with pytest.raises(ConfigurationError) as raised:
        await compute_get(node, "/configuration-startup-state")
    return raised.value.code


@pytest.mark.parametrize(
    "error",
    [ComputeError("refused"), ControllerTimeoutError("slow"), TimeoutError(), ConnectionRefusedError()],
)
async def test_unreachable_compute_is_reported_unavailable(error):
    assert await failing(error) == "configuration_compute_unavailable"


@pytest.mark.parametrize(
    "error",
    [HTTPException(status_code=502, detail="invalid_configuration_response"), ControllerNotFoundError("gone")],
)
async def test_reachable_compute_failures_are_not_reported_unavailable(error, caplog):
    with caplog.at_level(logging.WARNING):
        assert await failing(error) == "configuration_operation_failed"
    assert type(error).__name__ in caplog.text
    assert "n1" in caplog.text


async def test_conflict_keeps_its_public_code():
    error = ComputeConflictError("http://compute", {"message": "stop_required"})
    assert await failing(error) == "stop_required"
