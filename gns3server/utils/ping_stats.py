# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 GNS3 Technologies Inc.
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


class PingStats:
    """
    Ping messages are regularly sent to the client to keep the connection open.
    We send with it some information about server load.
    """

    _last_measurement = 0.0		# time of last measurement
    _last_cpu_percent = 0.0		# last cpu_percent
    _last_mem_percent = 0.0		# last virtual_memory().percent

    @classmethod
    def get(cls):
        """
        Get ping statistics

        :returns: hash
        """
        stats = {}
        cur_time = time.time()
        # minimum interval for getting CPU and memory statistics
        if cur_time < cls._last_measurement or \
           cur_time > cls._last_measurement + 1.9:
            cls._last_measurement = cur_time
            # Non blocking call to get cpu usage. First call will return 0
            cls._last_cpu_percent = psutil.cpu_percent(interval=None)
            cls._last_mem_percent = psutil.virtual_memory().percent
        stats["cpu_usage_percent"] = cls._last_cpu_percent
        stats["memory_usage_percent"] = cls._last_mem_percent
        return stats
