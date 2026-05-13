# SPDX-License-Identifier: GPL-3.0-or-later
#
# UUID validation utilities
#

import argparse
import re


UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)


def validate_uuid(value: str) -> str:
    """Validate UUID format for argparse.

    Args:
        value: UUID string to validate

    Returns:
        The validated UUID string

    Raises:
        argparse.ArgumentTypeError: If UUID format is invalid
    """
    if not UUID_PATTERN.match(value):
        raise argparse.ArgumentTypeError(
            f"Invalid UUID format: '{value}'. "
            f"Expected 8-4-4-4-12 hex groups (e.g., 5af0fe00-f39d-4985-8669-7e8c512d729c)"
        )
    return value
