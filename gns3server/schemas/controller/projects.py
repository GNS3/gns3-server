#
# Copyright (C) 2020 GNS3 Technologies Inc.
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


from datetime import datetime
from enum import StrEnum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator

from ..common import ErrorMessage
from ..update import PartialUpdateModel


class ProjectStatus(StrEnum):
    """
    Supported project statuses.
    """

    opened = "opened"
    closed = "closed"


class Supplier(BaseModel):
    logo: str = Field(..., description="Path to the project supplier logo")
    url: Optional[HttpUrl] = Field(None, description="URL to the project supplier site")


class Variable(BaseModel):
    name: str = Field(..., description="Variable name")
    value: Optional[str] = Field(None, description="Variable value")


class ProjectBase(BaseModel):
    """
    Common properties for projects.
    """

    name: Optional[str] = None
    project_id: Optional[UUID] = None
    path: Optional[str] = Field(None, description="Project directory")
    auto_close: Optional[bool] = Field(None, description="Close project when last client leaves")
    auto_open: Optional[bool] = Field(None, description="Project opens when GNS3 starts")
    auto_start: Optional[bool] = Field(None, description="Project starts when opened")
    scene_height: Optional[int] = Field(None, description="Height of the drawing area")
    scene_width: Optional[int] = Field(None, description="Width of the drawing area")
    zoom: Optional[int] = Field(None, description="Zoom of the drawing area")
    show_layers: Optional[bool] = Field(None, description="Show layers on the drawing area")
    snap_to_grid: Optional[bool] = Field(None, description="Snap to grid on the drawing area")
    show_grid: Optional[bool] = Field(None, description="Show the grid on the drawing area")
    grid_size: Optional[int] = Field(None, description="Grid size for the drawing area for nodes")
    drawing_grid_size: Optional[int] = Field(None, description="Grid size for the drawing area for drawings")
    show_interface_labels: Optional[bool] = Field(None, description="Show interface labels on the drawing area")
    supplier: Optional[Supplier] = Field(None, description="Supplier of the project")
    variables: Optional[List[Variable]] = Field(None, description="Variables required to run the project")


class ProjectCreate(ProjectBase):
    """
    Properties for project creation.
    """

    name: str


class ProjectDuplicate(ProjectBase):
    """
    Properties for project duplication.
    """

    name: str
    reset_mac_addresses: Optional[bool] = Field(False, description="Reset MAC addresses for this project")


class ProjectDistribute(ProjectBase):
    """
    Properties for project distribution: a copy is created for every
    recipient, owned by that recipient.
    """

    name: str
    reset_mac_addresses: Optional[bool] = Field(False, description="Reset MAC addresses for this project")
    target_user: Optional[str] = Field(None, description="Distribute the copy to this user")
    target_users: Optional[List[str]] = Field(
        None,
        min_length=1,
        description="Distribute one copy to each of these users (each user gets their own)",
    )
    target_group: Optional[str] = Field(
        None, description="Distribute one copy to every member of this user group (each member gets their own)"
    )
    owner_role: Optional[str] = Field(
        None, description="Role of the owner ACE put on a distributed copy (default: the built-in Lab member role)"
    )
    lock_topology: Optional[bool] = Field(
        True,
        description=(
            "Lock all nodes and drawings in each distributed copy (advisory: the client hides move and delete "
            "actions, enforcement stays with the owner role). Default: true"
        ),
    )

    @model_validator(mode="after")
    def check_distribution_targets(self) -> "ProjectDistribute":
        """
        A distribution targets a single user, a list of users or a whole
        group, and only one of them.
        """

        targets = [self.target_user, self.target_users, self.target_group]
        if sum(bool(target) for target in targets) > 1:
            raise ValueError("target_user, target_users and target_group cannot be combined")
        return self


class ProjectUpdate(PartialUpdateModel, ProjectBase):
    """
    Properties for project update.
    """

    update_excluded_fields = ("project_id", "path")


class Project(ProjectBase):
    project_id: UUID
    status: Optional[ProjectStatus] = None
    filename: Optional[str] = None
    created_by: Optional[str] = Field(None, description="Username of the user who created the project")
    frozen: Optional[bool] = Field(
        None,
        description="The project is a distributed template: modification is frozen until every copy is deleted",
    )
    distribution_master_id: Optional[UUID] = Field(
        None,
        description="Project id of the distributed template this copy was created from, if this is a distributed copy",
    )
    share_count: Optional[int] = Field(
        None,
        description="Number of shares on this project, only returned to the project owner and superadmins",
    )


class ProjectDistributionResult(BaseModel):
    """
    Outcome of one recipient of a distribution request.
    """

    username: str = Field(..., description="User the copy was distributed to")
    project: Optional[Project] = Field(None, description="The distributed copy as it was created, set on success")
    project_exists: Optional[bool] = Field(
        None,
        description="Whether the distributed copy still exists on the server, set on success "
        "(the copy may have been deleted since, by the API or by removing its directory)",
    )
    error: Optional[ErrorMessage] = Field(None, description="The error, set when the copy could not be created")


class ProjectDistributionStatus(StrEnum):
    """
    Status of a project distribution job.
    """

    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class ProjectDistribution(BaseModel):
    """
    A project distribution job: one copy per recipient, created in the
    background. Poll the job to follow the progress and read the results.
    """

    distribution_id: UUID
    project_id: UUID
    name: str = Field(..., description="Base name of the copies")
    created_by: str = Field(..., description="Username of the user who started the distribution")
    status: ProjectDistributionStatus
    total: int = Field(..., description="Number of recipients")
    completed: int = Field(..., description="Recipients processed so far, successful or not")
    results: List[ProjectDistributionResult] = Field(default_factory=list)
    error: Optional[ErrorMessage] = Field(None, description="Set when the job itself failed")
    created_at: datetime = Field(..., description="When the distribution was started")
    project_name: Optional[str] = Field(
        None,
        description="Name of the distributed (source) project, set by the cross-project listing; "
        "None when that project no longer exists on the server",
    )


class ProjectShare(BaseModel):
    """
    Properties for project sharing: the project itself becomes accessible to
    the target(s), no copy is created.
    """

    role: Optional[str] = Field(None, description="Role carried by the share (default: the built-in Lab member role)")
    target_user: Optional[str] = Field(None, description="Share the project with this user")
    target_users: Optional[List[str]] = Field(
        None, min_length=1, description="Share the project with each of these users"
    )
    target_group: Optional[str] = Field(None, description="Share the project with this user group (one group ACE)")

    @model_validator(mode="after")
    def check_share_targets(self) -> "ProjectShare":
        """
        A share targets a single user, a list of users or a whole group, and
        only one of them.
        """

        targets = [self.target_user, self.target_users, self.target_group]
        if sum(bool(target) for target in targets) > 1:
            raise ValueError("target_user, target_users and target_group cannot be combined")
        return self


class ProjectShareResult(BaseModel):
    """
    One share of a project: a user or a user group, with the role the share
    carries.
    """

    ace_id: UUID
    username: Optional[str] = Field(None, description="The user, when the share targets a user")
    group_name: Optional[str] = Field(None, description="The group, when the share targets a user group")
    role: str = Field(..., description="The role carried by the share")
    created_at: datetime
    updated_at: datetime


class ProjectFile(BaseModel):
    path: str = Field(..., description="File path")
    md5sum: str = Field(..., description="File checksum")


class NodeFile(BaseModel):
    """
    Detailed file information for node files.
    """

    path: str = Field(..., description="File name")
    size: int = Field(..., description="File size in bytes")
    created_at: Optional[datetime] = Field(None, description="File creation time (ISO 8601)")
    modified_at: Optional[datetime] = Field(None, description="File modification time (ISO 8601)")
    file_type: str = Field(..., description="File type determined by the file command")


class ProjectCompression(StrEnum):
    """
    Supported project compression.
    """

    none = "none"
    zip = "zip"
    bzip2 = "bzip2"
    lzma = "lzma"
    zstd = "zstd"


class ProjectStats(BaseModel):
    """
    Project object counts.
    """

    nodes: int
    links: int
    drawings: int
    snapshots: int
    markers: int


class ProjectPrivileges(BaseModel):
    """
    Effective privileges of the logged in user on a single project, evaluated
    on the project's resource path (so ACEs scoped to that project and
    resource pools containing it are reflected).

    This is a hint for rendering purposes only (e.g. showing or hiding buttons
    in the project view): the server remains the authority for permission
    checks on each request.
    """

    is_superadmin: bool
    privileges: List[str]
