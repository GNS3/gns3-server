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

import psutil
import time


class CpuPercent:
    """
    Ensures a minimum interval between two cpu_percent() calls
    """

    _last_measurement = None  # time of last measurement
    _last_cpu_percent = 0.0  # last cpu_percent

    @classmethod
    def get(cls, interval=None):
        """
        Get CPU utilization as a percentage

        :returns: float
        """

        if interval:
            cls._last_cpu_percent = psutil.cpu_percent(interval=interval)
            cls._last_measurement = time.monotonic()
        else:
            cur_time = time.monotonic()
            if cls._last_measurement is None or (cur_time - cls._last_measurement) >= 1.9:
                cls._last_cpu_percent = psutil.cpu_percent(interval=None)
                cls._last_measurement = cur_time

        return cls._last_cpu_percent
