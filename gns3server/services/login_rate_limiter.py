#!/usr/bin/env python
#
# Copyright (C) 2026 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
In-memory sliding-window rate limiter for user authentication endpoints.
Protects upstream Active Directory and LDAP accounts from automated lockout DoS attacks.
"""

import time
from collections import defaultdict, deque
from typing import Deque, Optional, Tuple


class LoginRateLimiter:
    """
    Sliding-window rate limiter for authentication endpoints.
    Tracks failed login attempts keyed by (username.lower(), client_ip).
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 60) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._failures: defaultdict[Tuple[str, str], Deque[float]] = defaultdict(deque)

    def is_rate_limited(self, username: str, client_ip: str, now: Optional[float] = None) -> Tuple[bool, int]:
        """
        Check if the (username, client_ip) pair has exceeded the allowed failure attempts.

        Returns (is_limited, retry_after_seconds).
        """
        if not username:
            return False, 0

        ts = now if now is not None else time.time()
        key = (username.strip().lower(), client_ip.strip())
        history = self._failures[key]

        # Prune timestamps outside the sliding window
        cutoff = ts - self._window_seconds
        while history and history[0] <= cutoff:
            history.popleft()

        if len(history) >= self._max_attempts:
            oldest = history[0]
            retry_after = max(1, int(oldest + self._window_seconds - ts))
            return True, retry_after

        return False, 0

    def record_failure(self, username: str, client_ip: str, now: Optional[float] = None) -> None:
        """
        Record a failed authentication attempt.
        """
        if not username:
            return
        ts = now if now is not None else time.time()
        key = (username.strip().lower(), client_ip.strip())
        self._failures[key].append(ts)

    def reset(self, username: str, client_ip: str) -> None:
        """
        Clear failure history upon successful authentication.
        """
        key = (username.strip().lower(), client_ip.strip())
        self._failures.pop(key, None)

    def clear(self) -> None:
        """
        Clear all rate limit state across all users and IPs.
        """
        self._failures.clear()


# Global singleton instance (5 failed attempts per 60 seconds)
login_rate_limiter = LoginRateLimiter(max_attempts=5, window_seconds=60)
