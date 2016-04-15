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


from .dynamips_error import DynamipsError
from .nodes.c1700 import C1700
from .nodes.c2600 import C2600
from .nodes.c2691 import C2691
from .nodes.c3600 import C3600
from .nodes.c3725 import C3725
from .nodes.c3745 import C3745
from .nodes.c7200 import C7200

import logging
log = logging.getLogger(__name__)

PLATFORMS = {'c1700': C1700,
             'c2600': C2600,
             'c2691': C2691,
             'c3725': C3725,
             'c3745': C3745,
             'c3600': C3600,
             'c7200': C7200}


class DynamipsVM:

    """
    Factory to create an Router object based on the correct platform.
    """

    def __new__(cls, name, vm_id, project, manager, dynamips_id, platform, **kwargs):

        if platform not in PLATFORMS:
            raise DynamipsError("Unknown router platform: {}".format(platform))

        return PLATFORMS[platform](name, vm_id, project, manager, dynamips_id, **kwargs)
