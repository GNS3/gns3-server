#!/usr/bin/env python
#
# Copyright (C) 2023 GNS3 Technologies Inc.
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

from sqlalchemy import Table, Column, String, ForeignKey, event
from sqlalchemy.orm import relationship

from .base import Base, BaseTable, generate_uuid, GUID

import logging

log = logging.getLogger(__name__)


privilege_role_map = Table(
    "privilege_role_map",
    Base.metadata,
    Column("privilege_id", GUID, ForeignKey("privileges.privilege_id", ondelete="CASCADE")),
    Column("role_id", GUID, ForeignKey("roles.role_id", ondelete="CASCADE"))
)


class Privilege(BaseTable):

    __tablename__ = "privileges"

    privilege_id = Column(GUID, primary_key=True, default=generate_uuid)
    name = Column(String)
    description = Column(String)
    roles = relationship("Role", secondary=privilege_role_map, back_populates="privileges")


@event.listens_for(Privilege.__table__, 'after_create')
def create_default_roles(target, connection, **kw):

    default_privileges = [
        {
            "description": "Create or delete a user",
            "name": "User.Allocate"
        },
        {
            "description": "View a user",
            "name": "User.Audit"
        },
        {
            "description": "Update a user",
            "name": "User.Modify"
        },
        {
            "description": "Create or delete a group",
            "name": "Group.Allocate"
        },
        {
            "description": "View a group",
            "name": "Group.Audit"
        },
        {
            "description": "Update a group",
            "name": "Group.Modify"
        },
        {
            "description": "Create or delete a role",
            "name": "Role.Allocate"
        },
        {
            "description": "View a role",
            "name": "Role.Audit"
        },
        {
            "description": "Update a role",
            "name": "Role.Modify"
        },
        {
            "description": "Create or delete an ACE",
            "name": "ACE.Allocate"
        },
        {
            "description": "View an ACE",
            "name": "ACE.Audit"
        },
        {
            "description": "Update an ACE",
            "name": "ACE.Modify"
        },
        {
            "description": "Create or delete a resource pool",
            "name": "Pool.Allocate"
        },
        {
            "description": "View a resource pool",
            "name": "Pool.Audit"
        },
        {
            "description": "Update a resource pool",
            "name": "Pool.Modify"
        },
        {
            "description": "Create or delete a template",
            "name": "Template.Allocate"
        },
        {
            "description": "View a template",
            "name": "Template.Audit"
        },
        {
            "description": "Update a template",
            "name": "Template.Modify"
        },
        {
            "description": "Create or delete a project",
            "name": "Project.Allocate"
        },
        {
            "description": "View a project",
            "name": "Project.Audit"
        },
        {
            "description": "Update a project",
            "name": "Project.Modify"
        },
        {
            "description": "Create or delete project snapshots",
            "name": "Snapshot.Allocate"
        },
        {
            "description": "Restore a snapshot",
            "name": "Snapshot.Restore"
        },
        {
            "description": "View a snapshot",
            "name": "Snapshot.Audit"
        },
        {
            "description": "Create or delete a node",
            "name": "Node.Allocate"
        },
        {
            "description": "View a node",
            "name": "Node.Audit"
        },
        {
            "description": "Update a node",
            "name": "Node.Modify"
        },
        {
            "description": "Console access to a node",
            "name": "Node.Console"
        },
        {
            "description": "Power management for a node",
            "name": "Node.PowerMgmt"
        },
        {
            "description": "Create or delete a link",
            "name": "Link.Allocate"
        },
        {
            "description": "View a link",
            "name": "Link.Audit"
        },
        {
            "description": "Update a link",
            "name": "Link.Modify"
        },
        {
            "description": "Capture packets on a link",
            "name": "Link.Capture"
        },
        {
            "description": "Create or delete a drawing",
            "name": "Drawing.Allocate"
        },
        {
            "description": "View a drawing",
            "name": "Drawing.Audit"
        },
        {
            "description": "Update a drawing",
            "name": "Drawing.Modify"
        },
        {
            "description": "Create or delete a symbol",
            "name": "Symbol.Allocate"
        },
        {
            "description": "View a symbol",
            "name": "Symbol.Audit"
        },
        {
            "description": "Create or delete an image",
            "name": "Image.Allocate"
        },
        {
            "description": "View an image",
            "name": "Image.Audit"
        },
        {
            "description": "Create or delete a compute",
            "name": "Compute.Allocate"
        },
        {
            "description": "Update a compute",
            "name": "Compute.Modify"
        },
        {
            "description": "View a compute",
            "name": "Compute.Audit"
        },
        {
            "description": "Install an appliance",
            "name": "Appliance.Allocate"
        },
        {
            "description": "View an appliance",
            "name": "Appliance.Audit"
        }
    ]

    stmt = target.insert().values(default_privileges)
    connection.execute(stmt)
    connection.commit()
    log.debug("The default privileges have been created in the database")


def add_privileges_to_role(target, connection, role, privileges):

    from .roles import Role
    roles_table = Role.__table__
    privileges_table = Privilege.__table__

    stmt = roles_table.select().where(roles_table.c.name == role)
    result = connection.execute(stmt)
    role_id = result.first().role_id
    for privilege_name in privileges:
        stmt = privileges_table.select().where(privileges_table.c.name == privilege_name)
        result = connection.execute(stmt)
        privilege_id = result.first().privilege_id
        stmt = target.insert().values(privilege_id=privilege_id, role_id=role_id)
        connection.execute(stmt)


@event.listens_for(privilege_role_map, 'after_create')
def add_privileges_to_default_roles(target, connection, **kw):

    from .roles import Role
    roles_table = Role.__table__
    stmt = roles_table.select().where(roles_table.c.name == "Administrator")
    result = connection.execute(stmt)
    role_id = result.first().role_id

    # add all privileges to the "Administrator" role
    privileges_table = Privilege.__table__
    stmt = privileges_table.select()
    result = connection.execute(stmt)
    for row in result:
        privilege_id = row.privilege_id
        stmt = target.insert().values(privilege_id=privilege_id, role_id=role_id)
        connection.execute(stmt)

    # add required privileges to the "User" role
    user_privileges = (
        "Project.Allocate",
        "Project.Audit",
        "Project.Modify",
        "Snapshot.Allocate",
        "Snapshot.Audit",
        "Snapshot.Restore",
        "Node.Allocate",
        "Node.Audit",
        "Node.Modify",
        "Node.Console",
        "Node.PowerMgmt",
        "Link.Allocate",
        "Link.Audit",
        "Link.Modify",
        "Link.Capture",
        "Drawing.Allocate",
        "Drawing.Audit",
        "Drawing.Modify",
        "Template.Audit",
        "Symbol.Audit",
        "Image.Audit",
        "Compute.Audit",
        "Appliance.Allocate",
        "Appliance.Audit"
    )

    add_privileges_to_role(target, connection, "User", user_privileges)

    # add required privileges to the "Auditor" role
    auditor_privileges = (
        "Project.Audit",
        "Snapshot.Audit",
        "Node.Audit",
        "Link.Audit",
        "Drawing.Audit",
        "Template.Audit",
        "Symbol.Audit",
        "Image.Audit",
        "Compute.Audit",
        "Appliance.Audit"
    )

    add_privileges_to_role(target, connection, "Auditor", auditor_privileges)

    # add required privileges to the "Template manager" role
    template_manager_privileges = (
        "Template.Allocate",
        "Template.Audit",
        "Template.Modify",
        "Symbol.Allocate",
        "Symbol.Audit",
        "Image.Allocate",
        "Image.Audit",
        "Appliance.Allocate",
        "Appliance.Audit"
    )

    add_privileges_to_role(target, connection, "Template manager", template_manager_privileges)

    # add required privileges to the "User manager" role
    user_manager_privileges = (
        "User.Allocate",
        "User.Audit",
        "User.Modify",
        "Group.Allocate",
        "Group.Audit",
        "Group.Modify"
    )

    add_privileges_to_role(target, connection, "User manager", user_manager_privileges)

    # add required privileges to the "ACL manager" role
    acl_manager_privileges = (
        "Role.Allocate",
        "Role.Audit",
        "Role.Modify",
        "ACE.Allocate",
        "ACE.Audit",
        "ACE.Modify"
    )

    add_privileges_to_role(target, connection, "ACL manager", acl_manager_privileges)

    connection.commit()
    log.debug("Privileges have been added to the default roles in the database")
