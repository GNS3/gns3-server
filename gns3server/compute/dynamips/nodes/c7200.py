# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 GNS3 Technologies Inc.
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
Interface for Dynamips virtual Cisco 7200 instances module ("c7200")
http://github.com/GNS3/dynamips/blob/master/README.hypervisor#L294
"""

import asyncio

from .router import Router
from ..adapters.c7200_io_fe import C7200_IO_FE
from ..adapters.c7200_io_ge_e import C7200_IO_GE_E
from ..dynamips_error import DynamipsError

import logging
log = logging.getLogger(__name__)


class C7200(Router):

    """
    Dynamips c7200 router (model is 7206).

    :param name: The name of this router
    :param node_id: Node identifier
    :param project: Project instance
    :param manager: Parent VM Manager
    :param dynamips_id: ID to use with Dynamips
    :param console: console port
    :param aux: auxiliary console port
    :param npe: Default NPE
    """

    def __init__(self, name, node_id, project, manager, dynamips_id, console=None, aux=None, npe="npe-400", chassis=None):

        super().__init__(name, node_id, project, manager, dynamips_id, console, aux, platform="c7200")

        # Set default values for this platform (must be the same as Dynamips)
        self._ram = 256
        self._nvram = 128
        self._disk0 = 64
        self._disk1 = 0
        self._npe = npe
        self._midplane = "vxr"
        self._clock_divisor = 4
        self._npe = npe

        # 4 sensors with a default temperature of 22C:
        # sensor 1 = I/0 controller inlet
        # sensor 2 = I/0 controller outlet
        # sensor 3 = NPE inlet
        # sensor 4 = NPE outlet
        self._sensors = [22, 22, 22, 22]

        # 2 power supplies powered on
        self._power_supplies = [1, 1]

        self._create_slots(7)

        if chassis is not None:
            raise DynamipsError("c7200 routers do not have chassis")

    def __json__(self):

        c7200_router_info = {"npe": self._npe,
                             "midplane": self._midplane,
                             "sensors": self._sensors,
                             "power_supplies": self._power_supplies}

        router_info = Router.__json__(self)
        router_info.update(c7200_router_info)
        return router_info

    @asyncio.coroutine
    def create(self):

        yield from Router.create(self)

        if self._npe != "npe-400":
            yield from self.set_npe(self._npe)

        # first slot is a mandatory Input/Output controller (based on NPE type)
        if self.npe == "npe-g2":
            yield from self.slot_add_binding(0, C7200_IO_GE_E())
        else:
            yield from self.slot_add_binding(0, C7200_IO_FE())

    @property
    def npe(self):
        """
        Returns the NPE model.

        :returns: NPE model string (e.g. "npe-200")
        """

        return self._npe

    @asyncio.coroutine
    def set_npe(self, npe):
        """
        Sets the NPE model.

        :params npe: NPE model string (e.g. "npe-200")
        NPE models are npe-100, npe-150, npe-175, npe-200,
        npe-225, npe-300, npe-400 and npe-g2 (PowerPC c7200 only)
        """

        if (yield from self.is_running()):
            raise DynamipsError("Cannot change NPE on running router")

        yield from self._hypervisor.send('c7200 set_npe "{name}" {npe}'.format(name=self._name, npe=npe))

        log.info('Router "{name}" [{id}]: NPE updated from {old_npe} to {new_npe}'.format(name=self._name,
                                                                                          id=self._id,
                                                                                          old_npe=self._npe,
                                                                                          new_npe=npe))
        self._npe = npe

    @property
    def midplane(self):
        """
        Returns the midplane model.

        :returns: midplane model string (e.g. "vxr" or "std")
        """

        return self._midplane

    @asyncio.coroutine
    def set_midplane(self, midplane):
        """
        Sets the midplane model.

        :returns: midplane model string (e.g. "vxr" or "std")
        """

        yield from self._hypervisor.send('c7200 set_midplane "{name}" {midplane}'.format(name=self._name, midplane=midplane))

        log.info('Router "{name}" [{id}]: midplane updated from {old_midplane} to {new_midplane}'.format(name=self._name,
                                                                                                         id=self._id,
                                                                                                         old_midplane=self._midplane,
                                                                                                         new_midplane=midplane))
        self._midplane = midplane

    @property
    def sensors(self):
        """
        Returns the 4 sensors with temperature in degree Celcius.

        :returns: list of 4 sensor temperatures
        """

        return self._sensors

    @asyncio.coroutine
    def set_sensors(self, sensors):
        """
        Sets the 4 sensors with temperature in degree Celcius.

        :param sensors: list of 4 sensor temperatures corresponding to
        sensor 1 = I/0 controller inlet
        sensor 2 = I/0 controller outlet
        sensor 3 = NPE inlet
        sensor 4 = NPE outlet
        Example: [22, 22, 22, 22]
        """

        sensor_id = 0
        for sensor in sensors:
            yield from self._hypervisor.send('c7200 set_temp_sensor "{name}" {sensor_id} {temp}'.format(name=self._name,
                                                                                                        sensor_id=sensor_id,
                                                                                                        temp=sensor))

            log.info('Router "{name}" [{id}]: sensor {sensor_id} temperature updated from {old_temp}C to {new_temp}C'.format(name=self._name,
                                                                                                                             id=self._id,
                                                                                                                             sensor_id=sensor_id,
                                                                                                                             old_temp=self._sensors[sensor_id],
                                                                                                                             new_temp=sensors[sensor_id]))

            sensor_id += 1
        self._sensors = sensors

    @property
    def power_supplies(self):
        """
        Returns the 2 power supplies with 0 = off, 1 = on.

        :returns: list of 2 power supplies.
        """

        return self._power_supplies

    @asyncio.coroutine
    def set_power_supplies(self, power_supplies):
        """
        Sets the 2 power supplies with 0 = off, 1 = on.

        :param power_supplies: list of 2 power supplies.
        Example: [1, 0] = first power supply is on, second is off.
        """

        power_supply_id = 0
        for power_supply in power_supplies:
            yield from self._hypervisor.send('c7200 set_power_supply "{name}" {power_supply_id} {powered_on}'.format(name=self._name,
                                                                                                                     power_supply_id=power_supply_id,
                                                                                                                     powered_on=power_supply))

            log.info('Router "{name}" [{id}]: power supply {power_supply_id} state updated to {powered_on}'.format(name=self._name,
                                                                                                                   id=self._id,
                                                                                                                   power_supply_id=power_supply_id,
                                                                                                                   powered_on=power_supply))
            power_supply_id += 1

        self._power_supplies = power_supplies

    @asyncio.coroutine
    def start(self):
        """
        Starts this router.
        At least the IOS image must be set before starting it.
        """

        # trick: we must send sensors and power supplies info after starting the router
        # otherwise they are not taken into account (Dynamips bug?)
        yield from Router.start(self)
        if self._sensors != [22, 22, 22, 22]:
            yield from self.set_sensors(self._sensors)
        if self._power_supplies != [1, 1]:
            yield from self.set_power_supplies(self._power_supplies)
