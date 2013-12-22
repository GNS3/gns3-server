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


from __future__ import unicode_literals
from ..dynamips_error import DynamipsError
from .router import Router
from ..adapters.c7200_io_2fe import C7200_IO_2FE
from ..adapters.c7200_io_ge_e import C7200_IO_GE_E


class C7200(Router):
    """
    Dynamips c7200 router (model is 7206).

    :param hypervisor: Dynamips hypervisor object
    :param name: name for this router
    :param npe: default NPE
    """

    def __init__(self, hypervisor, name, npe="npe-400"):
        Router.__init__(self, hypervisor, name, platform="c7200")

        # Set default values for this platform
        self._ram = 256
        self._nvram = 128
        self._disk0 = 64
        self._disk1 = 0
        self._npe = npe
        self._midplane = "vxr"
        self._clock_divisor = 4

        if npe != "npe-400":
            self.npe = npe

        # 4 sensors with a default temperature of 22C:
        # sensor 1 = I/0 controller inlet
        # sensor 2 = I/0 controller outlet
        # sensor 3 = NPE inlet
        # sensor 4 = NPE outlet
        self._sensors = [22, 22, 22, 22]

        # 2 power supplies powered on
        self._power_supplies = [1, 1]

        self._create_slots(7)

        # first slot is a mandatory Input/Output controller (based on NPE type)
        if npe == "npe-g2":
            self._slots[0] = C7200_IO_GE_E()
        else:
            self._slots[0] = C7200_IO_2FE()

    def list(self):
        """
        Returns all c7200 instances.

        :returns: c7200 instance list
        """

        return self._hypervisor.send("c7200 list")

    @property
    def npe(self):
        """
        Returns the NPE model.

        :returns: NPE model string (e.g. "npe-200")
        """

        return self._npe

    @npe.setter
    def npe(self, npe):
        """
        Set the NPE model.

        :params npe: NPE model string (e.g. "npe-200")
        NPE models are npe-100, npe-150, npe-175, npe-200,
        npe-225, npe-300, npe-400 and npe-g2 (PowerPC c7200 only)
        """

        if self.is_running():
            raise DynamipsError("Cannot change NPE on running router")

        self._hypervisor.send("c7200 set_npe {name} {npe}".format(name=self._name,
                                                                  npe=npe))
        self._npe = npe

    @property
    def midplane(self):
        """
        Returns the midplane model.

        :returns: midplane model string (e.g. "vxr" or "std")
        """

        return self._midplane

    @midplane.setter
    def midplane(self, midplane):
        """
        Set the midplane model.

        :returns: midplane model string (e.g. "vxr" or "std")
        """

        self._hypervisor.send("c7200 set_midplane {name} {midplane}".format(name=self._name,
                                                                            midplane=midplane))
        self._midplane = midplane

    @property
    def sensors(self):
        """
        Returns the 4 sensors with temperature in degree Celcius.

        :returns: list of 4 sensor temperatures
        """

        return self._sensors

    @sensors.setter
    def sensors(self, sensors):
        """
        Set the 4 sensors with temperature in degree Celcius.

        :param sensors: list of 4 sensor temperatures corresponding to
        sensor 1 = I/0 controller inlet
        sensor 2 = I/0 controller outlet
        sensor 3 = NPE inlet
        sensor 4 = NPE outlet
        Example: [22, 22, 22, 22]
        """

        sensor_id = 0
        for sensor in sensors:
            self._hypervisor.send("c7200 set_temp_sensor {name} {sensor_id} {temp}".format(name=self._name,
                                                                                           sensor_id=sensor_id,
                                                                                           temp=sensor))
            sensor_id += 1
        self._sensors = sensors

    @property
    def power_supplies(self):
        """
        Returns the 2 power supplies with 0 = off, 1 = on.

        :returns: list of 2 power supplies.
        """

        return self._power_supplies

    @power_supplies.setter
    def power_supplies(self, power_supplies):
        """
        Set the 2 power supplies with 0 = off, 1 = on.

        :param power_supplies: list of 2 power supplies.
        Example: [1, 0] = first power supply is on, second is off.
        """

        power_supply_id = 0
        for power_supply in power_supplies:
            self._hypervisor.send("c7200 set_power_supply {name} {power_supply_id} {powered_on}".format(name=self._name,
                                                                                                        power_supply_id=power_supply_id,
                                                                                                        powered_on=power_supply))
            power_supply_id += 1
        self._power_supplies = power_supplies
