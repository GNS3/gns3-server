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
Unit tests for LoginRateLimiter service and login rate limiting behavior.
"""

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient

from gns3server.services.login_rate_limiter import LoginRateLimiter, login_rate_limiter


def test_sliding_window_rate_limiter_threshold_and_retry_after():
    limiter = LoginRateLimiter(max_attempts=3, window_seconds=60)
    username = "attacker_target"
    client_ip = "192.0.2.100"

    t0 = 1000.0

    # First 2 failed attempts: not limited
    limiter.record_failure(username, client_ip, now=t0)
    is_limited, _ = limiter.is_rate_limited(username, client_ip, now=t0 + 1)
    assert is_limited is False

    limiter.record_failure(username, client_ip, now=t0 + 2)
    is_limited, _ = limiter.is_rate_limited(username, client_ip, now=t0 + 3)
    assert is_limited is False

    # 3rd failed attempt hits the threshold
    limiter.record_failure(username, client_ip, now=t0 + 4)
    is_limited, retry_after = limiter.is_rate_limited(username, client_ip, now=t0 + 5)
    assert is_limited is True
    assert retry_after == 55  # 1000 + 60 - 1005 = 55

    # Other users or other IPs are not affected
    is_limited_other, _ = limiter.is_rate_limited("other_user", client_ip, now=t0 + 5)
    assert is_limited_other is False

    is_limited_other_ip, _ = limiter.is_rate_limited(username, "192.0.2.200", now=t0 + 5)
    assert is_limited_other_ip is False

    # Sliding window expiration: at t0 + 61, the oldest attempt has expired
    is_limited_expired, _ = limiter.is_rate_limited(username, client_ip, now=t0 + 61)
    assert is_limited_expired is False


def test_rate_limiter_reset_on_success():
    limiter = LoginRateLimiter(max_attempts=3, window_seconds=60)
    username = "normal_user"
    client_ip = "192.0.2.50"

    # Record 2 failures
    limiter.record_failure(username, client_ip)
    limiter.record_failure(username, client_ip)

    # Successful login resets the tracking
    limiter.reset(username, client_ip)

    # Subsequent check should have 0 recorded attempts
    is_limited, _ = limiter.is_rate_limited(username, client_ip)
    assert is_limited is False


@pytest.mark.asyncio
async def test_api_login_endpoint_rate_limiting(app: FastAPI, unauthorized_client: AsyncClient):
    login_rate_limiter.clear()
    form_headers = {"content-type": "application/x-www-form-urlencoded"}

    # Attempt 5 consecutive failed logins
    for _ in range(5):
        resp = await unauthorized_client.post(
            app.url_path_for("login"),
            data={"username": "dos_victim", "password": "wrong_password_123"},
            headers=form_headers,
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # 6th attempt must be rejected with 429 Too Many Requests without hitting directory
    rate_limited_resp = await unauthorized_client.post(
        app.url_path_for("login"),
        data={"username": "dos_victim", "password": "wrong_password_123"},
        headers=form_headers,
    )
    assert rate_limited_resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in rate_limited_resp.headers
    body = rate_limited_resp.json()
    msg = body.get("message") or body.get("detail", "")
    assert "Too many failed login attempts" in msg

    # Cleanup rate limiter state
    login_rate_limiter.clear()
