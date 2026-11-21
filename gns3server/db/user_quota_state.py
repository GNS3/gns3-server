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
#

"""
In-memory snapshot of the per-user node quotas.

The quota checks run on the controller paths (node creation and node
start), which have no database session: they read this process-wide
snapshot instead. The database stays the source of truth — every
repository write that can change a quota (user columns, group defaults,
group membership) marks the snapshot dirty, which schedules a background
rebuild against the engine bound at startup. Until that rebuild lands
(typically milliseconds) the checks keep using the previous limits.

Resolution rules, applied when the snapshot is built:

* a user-level value wins (``-1`` normalizes to unlimited),
* otherwise the group defaults apply: with no group the user is
  unlimited; with several groups the widest default wins (an unlimited
  group overrides any numeric default, otherwise the largest number),
* superadmins are never limited — they are simply not checked, so their
  entry is irrelevant here.

A NULL resolved limit means unlimited.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import selectinload

import gns3server.db.models as models

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuotaLimits:
    """
    Resolved quotas for a user: a None field means unlimited.
    """

    max_nodes: Optional[int]
    max_running_nodes: Optional[int]


def _normalize(value: Optional[int]) -> Optional[int]:
    """
    Map a stored value to a limit: -1 (explicitly unlimited) and NULL
    both become None (unlimited).
    """

    return None if value is None or value < 0 else value


def _aggregate(values: list) -> Optional[int]:
    """
    Combine the group defaults into one limit: the widest wins. An empty
    list (no group) or any unlimited group means unlimited.
    """

    if not values:
        return None
    normalized = [_normalize(value) for value in values]
    limits = [limit for limit in normalized if limit is not None]
    if len(limits) != len(normalized):
        return None
    return max(limits)


class UserQuotaState:
    """
    Process-wide snapshot of username -> resolved QuotaLimits.
    """

    _instance: Optional["UserQuotaState"] = None

    def __init__(self) -> None:

        self._limits: Dict[str, QuotaLimits] = {}
        self._engine: Optional[AsyncEngine] = None
        self._reload_task: Optional[asyncio.Task] = None

    @classmethod
    def instance(cls) -> "UserQuotaState":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def _reset(cls) -> None:
        """
        Drop the singleton (test isolation).
        """

        cls._instance = None

    def bind_engine(self, engine: AsyncEngine) -> None:
        """
        Remember the engine used by the background rebuilds triggered by
        mark_dirty(). Called once at startup.
        """

        self._engine = engine

    async def reload(self, db_session: AsyncSession) -> None:
        """
        Rebuild the snapshot from the database.
        """

        result = await db_session.execute(select(models.User).options(selectinload(models.User.groups)))
        limits: Dict[str, QuotaLimits] = {}
        for user in result.scalars().all():
            if user.is_superadmin or not user.username:
                continue
            if user.max_nodes is not None:
                max_nodes = _normalize(user.max_nodes)
            else:
                max_nodes = _aggregate([group.default_max_nodes for group in user.groups])
            if user.max_running_nodes is not None:
                max_running_nodes = _normalize(user.max_running_nodes)
            else:
                max_running_nodes = _aggregate([group.default_max_running_nodes for group in user.groups])
            limits[user.username] = QuotaLimits(max_nodes=max_nodes, max_running_nodes=max_running_nodes)
        self._limits = limits
        log.debug(f"Loaded node quotas for {len(limits)} user(s)")

    def mark_dirty(self) -> None:
        """
        Schedule a background reload when an engine is bound. Repository
        writes call this after committing a quota-relevant change.
        """

        if self._engine is None or (self._reload_task is not None and not self._reload_task.done()):
            return
        try:
            self._reload_task = asyncio.create_task(self._reload())
        except RuntimeError:
            # No running loop (should not happen: writes happen in requests)
            pass

    async def _reload(self) -> None:

        assert self._engine is not None
        try:
            async with AsyncSession(self._engine) as db_session:
                await self.reload(db_session)
        except Exception as e:
            log.error(f"Could not reload the user quota snapshot: {e}")

    def get(self, username: Optional[str]) -> Optional[QuotaLimits]:
        """
        Return the resolved quotas for a user, or None when the user is
        unlimited (or unknown: an unloaded snapshot never blocks).
        """

        if not username:
            return None
        return self._limits.get(username)
