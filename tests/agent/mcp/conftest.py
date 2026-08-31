"""MCP test fixtures."""
import pytest


@pytest.fixture
def ctx():
    """Standard gns3_ctx for handlers."""
    return {
        "server_url": "http://192.168.1.3:3080",
        "jwt_token": "test-token",
        "jwt_username": "admin",
    }
