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

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field

from .computes import Compute
from .drawings import Drawing
from .links import Link
from .nodes import Node
from .projects import Project
from .snapshots import Snapshot


class NotificationAction(str, Enum):
    """
    Values of the "action" field of a notification.
    """

    ping = "ping"
    log_info = "log.info"
    log_warning = "log.warning"
    log_error = "log.error"
    node_created = "node.created"
    node_updated = "node.updated"
    node_deleted = "node.deleted"
    node_interface_status = "node.interface_status"
    link_created = "link.created"
    link_updated = "link.updated"
    link_deleted = "link.deleted"
    link_web_wireshark_started = "link.web_wireshark_started"
    drawing_created = "drawing.created"
    drawing_updated = "drawing.updated"
    drawing_deleted = "drawing.deleted"
    marker_match = "marker.match"
    snapshot_restored = "snapshot.restored"
    project_created = "project.created"
    project_updated = "project.updated"
    project_opened = "project.opened"
    project_closed = "project.closed"
    project_deleted = "project.deleted"
    compute_created = "compute.created"
    compute_updated = "compute.updated"
    compute_deleted = "compute.deleted"
    template_created = "template.created"
    template_updated = "template.updated"
    template_deleted = "template.deleted"
    settings_updated = "settings.updated"


class PingEvent(BaseModel):
    """
    Event of a "ping" notification, sent when the stream is opened and then at least every 5 seconds.
    """

    cpu_usage_percent: float = Field(..., description="CPU usage of the server in percent")
    memory_usage_percent: float = Field(..., description="Memory usage of the server in percent")
    disk_usage_percent: float = Field(..., description="Disk usage of the project directory in percent")
    compute_id: Optional[str] = Field(None, description="Compute that sent the ping (project streams only)")


class LogEvent(BaseModel):
    """
    Event of a "log.info", "log.warning" or "log.error" notification.
    """

    message: str = Field(..., description="Log message")


class NodeInterfaceStatusEvent(BaseModel):
    """
    Event of a "node.interface_status" notification.
    """

    project_id: UUID
    node_id: UUID
    adapter_number: int
    port_number: int
    status: str = Field(..., description="Status of the interface")


class MarkerMatchEvent(BaseModel):
    """
    Event of a "marker.match" notification, only sent on the markers WebSocket.
    """

    project_id: UUID
    node_id: UUID
    link_id: Optional[UUID] = None
    filter: str = Field(..., description="Name of the packet filter that matched")
    tag: Optional[int] = Field(None, description="Tag of the marker")
    ts: float = Field(..., description="Timestamp reported by uBridge (seconds since the epoch)")
    len: int = Field(0, description="Length of the matching packet")
    dir: Optional[str] = Field(None, description="Direction of the packet relative to the capture node")


class LinkWebWiresharkStartedEvent(BaseModel):
    """
    Event of a "link.web_wireshark_started" notification.
    """

    link_id: UUID
    ws_url: Optional[str] = Field(None, description="URL of the Web Wireshark session")


class SettingsUpdatedEvent(BaseModel):
    """
    Event of a "settings.updated" notification.
    """

    changed: List[str] = Field(..., description="Names of the settings that changed (values are never sent)")
    restart_required: List[str] = Field(..., description="Names of the changed settings that need a server restart")


class Notification(BaseModel):
    """
    A message of the notification streams. HTTP streams send one JSON object per line (application/x-ndjson),
    WebSocket streams send one JSON object per text frame.
    """

    action: NotificationAction = Field(..., description="Type of the notification")
    event: Union[
        PingEvent,
        LogEvent,
        NodeInterfaceStatusEvent,
        MarkerMatchEvent,
        LinkWebWiresharkStartedEvent,
        SettingsUpdatedEvent,
        Node,
        Link,
        Drawing,
        Project,
        Compute,
        Snapshot,
        Dict[str, Any],
    ] = Field(..., description="Payload of the notification, its content depends on the action")
    project_id: Optional[UUID] = Field(None, description="Project the notification belongs to, when set by the sender")
    compute_id: Optional[str] = Field(None, description="Compute that emitted the notification, when set by the sender")
