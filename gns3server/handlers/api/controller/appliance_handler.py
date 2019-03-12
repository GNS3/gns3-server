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

from gns3server.web.route import Route
from gns3server.controller import Controller

import logging
log = logging.getLogger(__name__)


class ApplianceHandler:
    """
    API entry points for appliance management.
    """

    @Route.get(
        r"/appliances",
        description="List of appliances",
        status_codes={
            200: "Appliance list returned"
        })
    async def list_appliances(request, response):

        controller = Controller.instance()
        if request.query.get("update", "no").lower() == "yes":
            await controller.appliance_manager.download_appliances()
        symbol_theme = request.query.get("symbol_theme", "Classic")
        controller.appliance_manager.load_appliances(symbol_theme=symbol_theme)
        response.json([c for c in controller.appliance_manager.appliances.values()])
