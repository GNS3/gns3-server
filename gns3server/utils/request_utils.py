"""
Utilities for extracting request information from ASGI scope.

This module provides reusable functions for extracting client information
from ASGI scope dictionaries for logging and debugging purposes.
"""

import logging
from urllib.parse import parse_qs
from typing import Dict, Any, Optional

log = logging.getLogger(__name__)


def extract_client_info(scope: Dict[str, Any], auth_service_instance: Optional[Any] = None) -> Dict[str, str]:
    """
    Extract client information from ASGI scope for logging purposes.

    Args:
        scope: ASGI scope dictionary containing request metadata
        auth_service_instance: Optional auth service instance for token validation

    Returns:
        Dictionary with client information:
        - host: Client IP address
        - port: Client port
        - path: Request path
        - method: Request method
        - username: Authenticated username (if token provided and valid)
        - user_info: Human-readable user info string
    """
    # Extract client address and port
    client = scope.get("client", (None, None))
    client_host = client[0] if client and client[0] else "unknown"
    client_port = str(client[1]) if client and len(client) > 1 else "unknown"

    # Extract request info
    path = scope.get("path", "unknown")
    method = scope.get("method", "unknown")

    # Try to extract username from token
    username = None
    if auth_service_instance:
        try:
            headers = dict(scope.get("headers", []))
            auth = headers.get(b"authorization", b"").decode()
            token = None

            # Try Authorization header
            if auth.startswith("Bearer "):
                token = auth[7:]

            # Try query parameter
            if not token:
                params = parse_qs(scope.get("query_string", b"").decode())
                tokens = params.get("token", [])
                if tokens:
                    token = tokens[0]

            # Validate and extract username
            if token:
                username = auth_service_instance.get_username_from_token(token)
        except Exception as e:
            log.debug(f"Failed to extract username from token: {e}")
            username = None

    # Create user-friendly info string
    user_info = f"user '{username}'" if username else "unauthenticated user"

    return {
        "host": client_host,
        "port": client_port,
        "path": path,
        "method": method,
        "username": username,
        "user_info": user_info
    }


def format_client_log(client_info: Dict[str, str], message: str) -> str:
    """
    Format a log message with client information.

    Args:
        client_info: Client information dict from extract_client_info()
        message: Log message

    Returns:
        Formatted log string with client prefix
    """
    return f"{message} - Client: {client_info['host']}:{client_info['port']} ({client_info['user_info']}, Path: {client_info['path']})"
