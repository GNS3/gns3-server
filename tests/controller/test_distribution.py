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
The retention of the in-memory distribution registry: a finished job
stays queryable for the retention period and is then pruned, but a job
with a copy still in flight (running or cancelling) is never pruned.
"""

import time
import uuid

import pytest

from gns3server.controller.distribution import JOB_RETENTION_SECONDS, DistributionRegistry


def _old_job(registry: DistributionRegistry) -> object:
    """
    A job created more than the retention period ago.
    """

    job = registry.create(str(uuid.uuid4()), "lab", "teacher", 3)
    job.created_at = time.time() - JOB_RETENTION_SECONDS - 1.0
    return job


def test_prune_keeps_a_running_job_past_retention():
    """
    A running job is live state, whatever its age.
    """

    registry = DistributionRegistry()
    job = _old_job(registry)
    registry.prune()
    assert registry.get(job.distribution_id) is job


def test_prune_keeps_a_cancelling_job_past_retention():
    """
    A cancelling job still has a copy in flight: the copy completes
    before the job stops, so the job is live state too and must stay in
    the registry (its absence is read as "cut short by a restart").
    """

    registry = DistributionRegistry()
    job = _old_job(registry)
    assert registry.request_cancel(job) is True
    registry.prune()
    assert registry.get(job.distribution_id) is job


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
def test_prune_drops_finished_jobs_past_retention(status):
    """
    Only finished jobs leave the registry once the retention period is
    over.
    """

    registry = DistributionRegistry()
    job = _old_job(registry)
    if status == "failed":
        registry.fail(job, "boom")
    elif status == "completed":
        registry.complete(job)
    else:
        registry.cancelled(job)
    assert job.status == status
    registry.prune()
    assert registry.get(job.distribution_id) is None


def test_prune_keeps_a_recently_finished_job():
    """
    A finished job younger than the retention period stays queryable.
    """

    registry = DistributionRegistry()
    job = registry.create(str(uuid.uuid4()), "lab", "teacher", 3)
    registry.complete(job)
    registry.prune()
    assert registry.get(job.distribution_id) is job
