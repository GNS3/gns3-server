# SPDX-License-Identifier: GPL-3.0-or-later
#
# Deterministic port allocation utilities
#

import hashlib


# Display/port allocation range (stable across process restarts)
DISPLAY_RANGE = 10000
DISPLAY_MODULO = 10000


def link_id_to_display(link_id: str) -> int:
    """Convert link_id to display number using deterministic hash.

    Uses MD5 to ensure stable display assignment across process restarts.

    Args:
        link_id: The link ID (UUID)

    Returns:
        Display number (10000-19999)
    """
    hash_value = int(hashlib.md5(link_id.encode()).hexdigest(), 16)
    return DISPLAY_RANGE + (hash_value % DISPLAY_MODULO)


def link_id_to_port(link_id: str) -> int:
    """Convert link_id to TCP port using deterministic hash.

    Uses same algorithm as link_id_to_display for consistency.

    Args:
        link_id: The link ID (UUID)

    Returns:
        TCP port (10000-19999)
    """
    return link_id_to_display(link_id)
