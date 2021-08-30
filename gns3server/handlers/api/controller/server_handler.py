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
from gns3server.config import Config
from gns3server.controller import Controller
from gns3server.schemas.version import VERSION_SCHEMA
from gns3server.schemas.iou_license import IOU_LICENSE_SETTINGS_SCHEMA
from gns3server.version import __version__

from aiohttp.web import HTTPConflict, HTTPForbidden

import os
import psutil
import shutil
import asyncio
import platform

import logging
log = logging.getLogger(__name__)


class ServerHandler:

    @classmethod
    @Route.post(
        r"/shutdown",
        description="Shutdown the local server",
        status_codes={
            201: "Server is shutting down",
            403: "Server shutdown refused"
        })
    async def shutdown(request, response):

        config = Config.instance()
        if config.get_section_config("Server").getboolean("local", False) is False:
            raise HTTPForbidden(text="You can only stop a local server")

        log.info("Start shutting down the server")

        # close all the projects first
        controller = Controller.instance()
        projects = controller.projects.values()

        tasks = []
        for project in projects:
            tasks.append(asyncio.ensure_future(project.close()))

        if tasks:
            done, _ = await asyncio.wait(tasks)
            for future in done:
                try:
                    future.result()
                except Exception as e:
                    log.error("Could not close project {}".format(e), exc_info=1)
                    continue

        # then shutdown the server itself
        from gns3server.web.web_server import WebServer
        server = WebServer.instance()
        try:
            asyncio.ensure_future(server.shutdown_server())
        except asyncio.CancelledError:
            pass
        response.set_status(201)

    @classmethod
    @Route.post(
        r"/reload",
        description="Reload the local server",
        status_codes={
            200: "Server has reloaded"
        })
    async def reload(request, response):

        from gns3server.web.web_server import WebServer
        server = WebServer.instance()
        try:
            asyncio.ensure_future(server.reload_server())
        except asyncio.CancelledError:
            pass

    @Route.get(
        r"/version",
        description="Retrieve the server version number",
        output=VERSION_SCHEMA)
    def version(request, response):

        config = Config.instance()
        local_server = config.get_section_config("Server").getboolean("local", False)
        response.json({"version": __version__, "local": local_server})

    @Route.post(
        r"/version",
        description="Check if version is the same as the server",
        output=VERSION_SCHEMA,
        input=VERSION_SCHEMA,
        status_codes={
            200: "Same version",
            409: "Invalid version"
        })
    def check_version(request, response):
        if request.json["version"] != __version__:
            raise HTTPConflict(text="Client version {} is not the same as server version {}".format(request.json["version"], __version__))
        response.json({"version": __version__})

    @Route.get(
        r"/iou_license",
        description="Get the IOU license settings",
        status_codes={
            200: "IOU license settings returned"
        },
        output_schema=IOU_LICENSE_SETTINGS_SCHEMA)
    def show(request, response):

        response.json(Controller.instance().iou_license)

    @Route.put(
        r"/iou_license",
        description="Update the IOU license settings",
        input_schema=IOU_LICENSE_SETTINGS_SCHEMA,
        output_schema=IOU_LICENSE_SETTINGS_SCHEMA,
        status_codes={
            201: "IOU license settings updated"
        })
    async def update(request, response):

        controller = Controller().instance()
        iou_license = controller.iou_license
        iou_license.update(request.json)
        controller.save()
        response.json(iou_license)
        response.set_status(201)

    @Route.get(
        r"/statistics",
        description="Retrieve server statistics",
        status_codes={
            200: "Statistics information returned",
            409: "Conflict"
        })
    async def statistics(request, response):

        compute_statistics = []
        for compute in list(Controller.instance().computes.values()):
            try:
                r = await compute.get("/statistics")
                compute_statistics.append({"compute_id": compute.id, "compute_name": compute.name, "statistics": r.json})
            except HTTPConflict as e:
                log.error("Could not retrieve statistics on compute {}: {}".format(compute.name, e.text))
        response.json(compute_statistics)

    @Route.post(
        r"/debug",
        description="Dump debug information to disk (debug directory in config directory). Work only for local server",
        status_codes={
            201: "Written"
        })
    async def debug(request, response):

        config = Config.instance()
        if config.get_section_config("Server").getboolean("local", False) is False:
            raise HTTPForbidden(text="You can only debug a local server")

        debug_dir = os.path.join(config.config_dir, "debug")
        try:
            if os.path.exists(debug_dir):
                shutil.rmtree(debug_dir)
            os.makedirs(debug_dir)
            with open(os.path.join(debug_dir, "controller.txt"), "w+") as f:
                f.write(ServerHandler._getDebugData())
        except Exception as e:
            # If something is wrong we log the info to the log and we hope the log will be include correctly to the debug export
            log.error("Could not export debug information {}".format(e), exc_info=1)

        try:
            if Controller.instance().gns3vm.engine == "vmware":
                vmx_path = Controller.instance().gns3vm.current_engine().vmx_path
                if vmx_path:
                    shutil.copy(vmx_path, os.path.join(debug_dir, os.path.basename(vmx_path)))
        except OSError as e:
            # If something is wrong we log the info to the log and we hope the log will be include correctly to the debug export
            log.error("Could not copy VMware VMX file {}".format(e), exc_info=1)

        for compute in list(Controller.instance().computes.values()):
            try:
                r = await compute.get("/debug", raw=True)
                data = r.body.decode("utf-8")
            except Exception as e:
                data = str(e)
            with open(os.path.join(debug_dir, "compute_{}.txt".format(compute.id)), "w+") as f:
                f.write("Compute ID: {}\n".format(compute.id))
                f.write(data)

        response.set_status(201)

    @staticmethod
    def _getDebugData():
        try:
            connections = psutil.net_connections()
        # You need to be root for OSX
        except psutil.AccessDenied:
            connections = None

        try:
            addrs = ["* {}: {}".format(key, val) for key, val in psutil.net_if_addrs().items()]
        except UnicodeDecodeError:
            addrs = ["INVALID ADDR WITH UNICODE CHARACTERS"]

        data = """Version: {version}
OS: {os}
Python: {python}
CPU: {cpu}
Memory: {memory}

Networks:
{addrs}

Open connections:
{connections}

Processus:
""".format(
            version=__version__,
            os=platform.platform(),
            python=platform.python_version(),
            memory=psutil.virtual_memory(),
            cpu=psutil.cpu_times(),
            connections=connections,
            addrs="\n".join(addrs)
        )
        for proc in psutil.process_iter():
            try:
                psinfo = proc.as_dict(attrs=["name", "exe"])
                data += "* {} {}\n".format(psinfo["name"], psinfo["exe"])
            except (OSError, psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        data += "\n\nProjects"
        for project in Controller.instance().projects.values():
            data += "\n\nProject name: {}\nProject ID: {}\n".format(project.name, project.id)
            for link in project.links.values():
                data += "Link {}: {}".format(link.id, link.debug_link_data)

        return data
