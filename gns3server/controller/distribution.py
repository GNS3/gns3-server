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
In-memory registry of project distributions.

A distribution creates one project copy per recipient in the background
(a whole class can mean minutes of file copies). The job state lives in
this process-wide registry, like the rest of the controller state: the
client polls the job to follow the progress and read the per-recipient
results. Every state change is also written through to the
distribution_records table (see the API routes), so the history survives a
controller restart; this registry only holds the live jobs and frees the
finished ones after the retention period.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

# completed jobs stay queryable for that long, then they are pruned
JOB_RETENTION_SECONDS = 3600.0


@dataclass
class Distribution:
    """
    State of one distribution job.
    """

    distribution_id: str
    project_id: str
    name: str
    created_by: str
    total: int
    status: str = "running"
    error: Optional[str] = None
    # set by a cancel request: the copy in flight completes, the remaining
    # recipients are skipped (cancelling never cuts a copy in half)
    cancel_requested: bool = False
    results: List[dict] = field(default_factory=list)
    # wall clock: surfaced in the API responses and interchangeable with the
    # timestamp of a persisted record
    created_at: float = field(default_factory=time.time)
    # keeps the background task alive (a task without a reference can be
    # garbage collected before it finishes)
    task: Optional[asyncio.Task] = None

    def asdict(self) -> dict:
        return {
            "distribution_id": self.distribution_id,
            "project_id": self.project_id,
            "name": self.name,
            "created_by": self.created_by,
            "status": self.status,
            "total": self.total,
            "completed": len(self.results),
            "results": self.results,
            "error": {"message": self.error} if self.error else None,
            "created_at": self.created_at,
        }


class DistributionRegistry:
    """
    Process-wide registry of distribution jobs (see ``instance``).
    """

    _instance = None

    @classmethod
    def instance(cls) -> "DistributionRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._jobs: Dict[str, Distribution] = {}

    def create(self, project_id: str, name: str, created_by: str, total: int) -> Distribution:
        job = Distribution(
            distribution_id=str(uuid.uuid4()),
            project_id=project_id,
            name=name,
            created_by=created_by,
            total=total,
        )
        self._jobs[job.distribution_id] = job
        return job

    def get(self, distribution_id: str) -> Optional[Distribution]:
        return self._jobs.get(distribution_id)

    def get_for_project(self, project_id: str) -> List[Distribution]:
        jobs = [job for job in self._jobs.values() if job.project_id == project_id]
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)

    def live_ids(self) -> List[str]:
        """
        IDs of the jobs in this registry (running or recently finished).
        A record still marked running in the database but absent from this
        list was cut short by a controller restart.
        """

        return list(self._jobs.keys())

    def record_result(self, job: Distribution, result: dict) -> None:
        job.results.append(result)
        done = len(job.results)
        log.info(f"Distribution '{job.distribution_id}' of project '{job.project_id}': {done}/{job.total} done")

    def complete(self, job: Distribution) -> None:
        job.status = "completed"

    def request_cancel(self, job: Distribution) -> bool:
        """
        Ask a running job to stop at the next recipient boundary: the copy in
        flight completes, the remaining recipients are skipped. Returns False
        when the job already finished (requesting cancellation again while the
        job is cancelling is a no-op that keeps returning True).
        """

        if job.status == "cancelling":
            return True
        if job.status != "running":
            return False
        job.cancel_requested = True
        job.status = "cancelling"
        log.info(f"Cancellation of distribution '{job.distribution_id}' of project '{job.project_id}' requested")
        return True

    def cancelled(self, job: Distribution) -> None:
        job.status = "cancelled"
        log.info(f"Distribution '{job.distribution_id}' of project '{job.project_id}' cancelled")

    def fail(self, job: Distribution, error: str) -> None:
        job.status = "failed"
        job.error = error
        log.error(f"Distribution '{job.distribution_id}' of project '{job.project_id}' failed: {error}")

    def remove(self, distribution_id: str) -> None:
        """
        Drop a finished job from the registry: its record was deleted, so the
        job must not resurface through the single-distribution endpoint
        during the retention window. Only call this on a job that already
        finished (running jobs are cancelled, not removed).
        """

        self._jobs.pop(distribution_id, None)

    def prune(self) -> None:
        """
        Drop the finished jobs older than the retention period.
        """

        cutoff = time.time() - JOB_RETENTION_SECONDS
        stale = [
            distribution_id
            for distribution_id, job in self._jobs.items()
            if job.status not in ("running", "cancelling") and job.created_at < cutoff
        ]
        for distribution_id in stale:
            del self._jobs[distribution_id]
