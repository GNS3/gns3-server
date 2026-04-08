"""
Web Wireshark integration for GNS3.
Allows viewing packet captures in browser via xpra HTML5 client.
"""

from .manager import WiresharkManager
from .session import WiresharkSession
from .container_manager import ProjectContainerManager
from .display_manager import DisplayManager

__all__ = [
    'WiresharkManager',
    'WiresharkSession',
    'ProjectContainerManager',
    'DisplayManager',
]
