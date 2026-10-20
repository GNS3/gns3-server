import socket
from unittest.mock import patch

from gns3server.utils import is_ipv6_enabled


def test_is_ipv6_enabled_no_ipv6_support():

    with patch("socket.has_ipv6", False):
        assert is_ipv6_enabled() is False


def test_is_ipv6_enabled_no_configured_ipv6_address():
    """
    IPv6 stack loaded (binding ::1 works) but getaddrinfo with AI_ADDRCONFIG
    fails, like SPICE does when no non-loopback IPv6 address is configured.
    """

    error = socket.gaierror(
        getattr(socket, "EAI_ADDRFAMILY", socket.EAI_FAMILY), "Address family for hostname not supported"
    )
    with patch("socket.has_ipv6", True), patch("socket.socket"), patch("socket.getaddrinfo", side_effect=error):
        assert is_ipv6_enabled() is False


def test_is_ipv6_enabled():

    with patch("socket.has_ipv6", True), patch("socket.socket"), patch("socket.getaddrinfo", return_value=[]):
        assert is_ipv6_enabled() is True
