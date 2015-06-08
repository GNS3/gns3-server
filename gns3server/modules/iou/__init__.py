# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 GNS3 Technologies Inc.
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
IOU server module.
"""

import os
import asyncio

from ..base_manager import BaseManager
from .iou_error import IOUError
from .iou_vm import IOUVM

import logging
log = logging.getLogger(__name__)


class IOU(BaseManager):

    _VM_CLASS = IOUVM

    def __init__(self):

        super().__init__()
        self._free_application_ids = list(range(1, 512))
        self._used_application_ids = {}

    @asyncio.coroutine
    def create_vm(self, *args, **kwargs):
        """
        Creates a new IOU VM.

        :returns: IOUVM instance
        """

        vm = yield from super().create_vm(*args, **kwargs)
        try:
            self._used_application_ids[vm.id] = self._free_application_ids.pop(0)
        except IndexError:
            raise IOUError("Cannot create a new IOU VM (limit of 512 VMs reached on this host)")
        return vm

    @asyncio.coroutine
    def close_vm(self, vm_id, *args, **kwargs):
        """
        Closes an IOU VM.

        :returns: IOUVM instance
        """

        vm = self.get_vm(vm_id)
        if vm_id in self._used_application_ids:
            i = self._used_application_ids[vm_id]
            self._free_application_ids.insert(0, i)
            del self._used_application_ids[vm_id]
        yield from super().close_vm(vm_id, *args, **kwargs)
        return vm

    @asyncio.coroutine
    def project_committed(self, project):
        """
        Called when a project has been committed.

        :param project: Project instance
        """

        # save the configs when the project is committed
        for vm in self._vms.copy().values():
            if vm.project.id == project.id:
                try:
                    vm.save_configs()
                except IOUError as e:
                    log.warning(e)
                    continue

    def get_application_id(self, vm_id):
        """
        Get an unique application identifier for IOU.

        :param vm_id: IOU VM identifier

        :returns: IOU application identifier
        """

        return self._used_application_ids.get(vm_id, 1)

    @staticmethod
    def get_legacy_vm_workdir(legacy_vm_id, name):
        """
        Returns the name of the legacy working directory (pre 1.3) name for a VM.

        :param legacy_vm_id: legacy VM identifier (integer)
        :param name: VM name (not used)

        :returns: working directory name
        """

        return os.path.join("iou", "device-{}".format(legacy_vm_id))

    def get_images_directory(self):
        """
        Return the full path of the images directory on disk
        """
        return os.path.join(os.path.expanduser(self.config.get_section_config("Server").get("images_path", "~/GNS3/images")), "IOU")
