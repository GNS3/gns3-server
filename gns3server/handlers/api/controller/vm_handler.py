# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 GNS3 Technologies Inc.
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

from ....web.route import Route
from ....schemas.vm import VM_OBJECT_SCHEMA, VM_UPDATE_SCHEMA
from ....controller.project import Project
from ....controller import Controller


class VMHandler:
    """
    API entry point for VM
    """

    @classmethod
    @Route.post(
        r"/projects/{project_id}/vms",
        parameters={
            "project_id": "UUID for the project"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request"
        },
        description="Create a new VM instance",
        input=VM_OBJECT_SCHEMA,
        output=VM_OBJECT_SCHEMA)
    def create(request, response):

        controller = Controller.instance()
        compute = controller.getCompute(request.json.pop("compute_id"))
        project = controller.getProject(request.match_info["project_id"])
        vm = yield from project.addVM(compute, request.json.pop("vm_id", None), **request.json)
        response.set_status(201)
        response.json(vm)

    @classmethod
    @Route.put(
        r"/projects/{project_id}/vms/{vm_id}",
        status_codes={
            201: "Instance created",
            400: "Invalid request"
        },
        description="Update a VM instance",
        input=VM_UPDATE_SCHEMA,
        output=VM_OBJECT_SCHEMA)
    def update(request, response):
        project = Controller.instance().getProject(request.match_info["project_id"])
        vm = project.getVM(request.match_info["vm_id"])

        # Ignore this, because we use it only in create
        request.json.pop("vm_id", None)
        request.json.pop("vm_type", None)
        request.json.pop("compute_id", None)

        yield from vm.update(**request.json)
        response.set_status(201)
        response.json(vm)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/vms/{vm_id}/start",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the VM"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request"
        },
        description="Start a VM instance",
        output=VM_OBJECT_SCHEMA)
    def start(request, response):

        project = Controller.instance().getProject(request.match_info["project_id"])
        vm = project.getVM(request.match_info["vm_id"])
        yield from vm.start()
        response.set_status(201)
        response.json(vm)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/vms/{vm_id}/stop",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the VM"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request"
        },
        description="Start a VM instance",
        output=VM_OBJECT_SCHEMA)
    def stop(request, response):

        project = Controller.instance().getProject(request.match_info["project_id"])
        vm = project.getVM(request.match_info["vm_id"])
        yield from vm.stop()
        response.set_status(201)
        response.json(vm)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/vms/{vm_id}/suspend",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the VM"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request"
        },
        description="Start a VM instance",
        output=VM_OBJECT_SCHEMA)
    def suspend(request, response):

        project = Controller.instance().getProject(request.match_info["project_id"])
        vm = project.getVM(request.match_info["vm_id"])
        yield from vm.suspend()
        response.set_status(201)
        response.json(vm)

    @classmethod
    @Route.post(
        r"/projects/{project_id}/vms/{vm_id}/reload",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the VM"
        },
        status_codes={
            201: "Instance created",
            400: "Invalid request"
        },
        description="Reload a VM instance",
        output=VM_OBJECT_SCHEMA)
    def reload(request, response):

        project = Controller.instance().getProject(request.match_info["project_id"])
        vm = project.getVM(request.match_info["vm_id"])
        yield from vm.reload()
        response.set_status(201)
        response.json(vm)

    @classmethod
    @Route.delete(
        r"/projects/{project_id}/vms/{vm_id}",
        parameters={
            "project_id": "UUID for the project",
            "vm_id": "UUID for the VM"
        },
        status_codes={
            201: "Instance deleted",
            400: "Invalid request"
        },
        description="Delete a VM instance")
    def delete(request, response):
        project = Controller.instance().getProject(request.match_info["project_id"])
        vm = project.getVM(request.match_info["vm_id"])
        yield from vm.destroy()
        response.set_status(201)
