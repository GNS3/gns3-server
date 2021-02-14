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
VPCS VM management (creates command line, processes, files etc.) in
order to run a VPCS VM.
"""

import os
import sys
import socket
import subprocess
import signal
import re
import asyncio
import shutil

from gns3server.utils.asyncio import wait_for_process_termination
from gns3server.utils.asyncio import monitor_process
from gns3server.utils.asyncio import subprocess_check_output
from gns3server.utils import parse_version

from .vpcs_error import VPCSError
from ..adapters.ethernet_adapter import EthernetAdapter
from ..nios.nio_udp import NIOUDP
from ..base_node import BaseNode


import logging
log = logging.getLogger(__name__)


class VPCSVM(BaseNode):
    module_name = 'vpcs'

    """
    VPCS VM implementation.

    :param name: VPCS VM name
    :param node_id: Node identifier
    :param project: Project instance
    :param manager: Manager instance
    :param console: TCP console port
    :param startup_script: content of the startup script file
    """

    def __init__(self, name, node_id, project, manager, console=None, console_type="telnet", startup_script=None):

        super().__init__(name, node_id, project, manager, console=console, console_type=console_type, wrap_console=True)
        self._process = None
        self._vpcs_stdout_file = ""
        self._vpcs_version = None
        self._started = False
        self._local_udp_tunnel = None

        # VPCS settings
        if startup_script is not None and not self.script_file:  # We disallow override at startup
            self.startup_script = startup_script
        self._ethernet_adapter = EthernetAdapter()  # one adapter with 1 Ethernet interface

    @property
    def ethernet_adapter(self):
        return self._ethernet_adapter

    async def close(self):
        """
        Closes this VPCS VM.
        """

        if not (await super().close()):
            return False

        nio = self._ethernet_adapter.get_nio(0)
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)

        if self._local_udp_tunnel:
            self.manager.port_manager.release_udp_port(self._local_udp_tunnel[0].lport, self._project)
            self.manager.port_manager.release_udp_port(self._local_udp_tunnel[1].lport, self._project)
            self._local_udp_tunnel = None

        await self._stop_ubridge()

        if self.is_running():
            self._terminate_process()

        return True

    async def _check_requirements(self):
        """
        Check if VPCS is available with the correct version.
        """

        path = self._vpcs_path()
        if not path:
            raise VPCSError("No path to a VPCS executable has been set")

        # This raise an error if ubridge is not available
        self.ubridge_path

        if not os.path.isfile(path):
            raise VPCSError("VPCS program '{}' is not accessible".format(path))

        if not os.access(path, os.X_OK):
            raise VPCSError("VPCS program '{}' is not executable".format(path))

        await self._check_vpcs_version()

    def __json__(self):

        return {"name": self.name,
                "node_id": self.id,
                "node_directory": self.working_path,
                "status": self.status,
                "console": self._console,
                "console_type": self._console_type,
                "project_id": self.project.id,
                "command_line": self.command_line}

    def _vpcs_path(self):
        """
        Returns the VPCS executable path.

        :returns: path to VPCS
        """

        vpcs_path = self._manager.config.get_section_config("VPCS").get("vpcs_path", "vpcs")
        if not os.path.isabs(vpcs_path):
            vpcs_path = shutil.which(vpcs_path)
        return vpcs_path

    @BaseNode.name.setter
    def name(self, new_name):
        """
        Sets the name of this VPCS VM.

        :param new_name: name
        """

        if self.script_file:
            content = self.startup_script
            content = content.replace(self._name, new_name)
            escaped_name = new_name.replace('\\', '')
            content = re.sub(r"^set pcname .+$", "set pcname " + escaped_name, content, flags=re.MULTILINE)
            self.startup_script = content

        super(VPCSVM, VPCSVM).name.__set__(self, new_name)

    @property
    def startup_script(self):
        """
        Returns the content of the current startup script
        """

        script_file = self.script_file
        if script_file is None:
            return None

        try:
            with open(script_file, "rb") as f:
                return f.read().decode("utf-8", errors="replace")
        except OSError as e:
            raise VPCSError('Cannot read the startup script file "{}": {}'.format(script_file, e))

    @startup_script.setter
    def startup_script(self, startup_script):
        """
        Updates the startup script.

        :param startup_script: content of the startup script
        """

        try:
            startup_script_path = os.path.join(self.working_dir, 'startup.vpc')
            with open(startup_script_path, "w+", encoding='utf-8') as f:
                if startup_script is None:
                    f.write('')
                else:
                    startup_script = startup_script.replace("%h", self._name)
                    f.write(startup_script)
        except OSError as e:
            raise VPCSError('Cannot write the startup script file "{}": {}'.format(startup_script_path, e))

    async def _check_vpcs_version(self):
        """
        Checks if the VPCS executable version is >= 0.8b or == 0.6.1.
        """
        try:
            output = await subprocess_check_output(self._vpcs_path(), "-v", cwd=self.working_dir)
            match = re.search(r"Welcome to Virtual PC Simulator, version ([0-9a-z\.]+)", output)
            if match:
                version = match.group(1)
                self._vpcs_version = parse_version(version)
                if self._vpcs_version < parse_version("0.6.1"):
                    raise VPCSError("VPCS executable version must be >= 0.6.1 but not a 0.8")
            else:
                raise VPCSError("Could not determine the VPCS version for {}".format(self._vpcs_path()))
        except (OSError, subprocess.SubprocessError) as e:
            raise VPCSError("Error while looking for the VPCS version: {}".format(e))

    async def start(self):
        """
        Starts the VPCS process.
        """

        await self._check_requirements()
        if not self.is_running():
            nio = self._ethernet_adapter.get_nio(0)
            command = self._build_command()
            try:
                log.info("Starting VPCS: {}".format(command))
                self._vpcs_stdout_file = os.path.join(self.working_dir, "vpcs.log")
                log.info("Logging to {}".format(self._vpcs_stdout_file))
                flags = 0
                if sys.platform.startswith("win32"):
                    flags = subprocess.CREATE_NEW_PROCESS_GROUP
                with open(self._vpcs_stdout_file, "w", encoding="utf-8") as fd:
                    self.command_line = ' '.join(command)
                    self._process = await asyncio.create_subprocess_exec(*command,
                                                                              stdout=fd,
                                                                              stderr=subprocess.STDOUT,
                                                                              cwd=self.working_dir,
                                                                              creationflags=flags)
                    monitor_process(self._process, self._termination_callback)

                await self._start_ubridge()
                if nio:
                    await self.add_ubridge_udp_connection("VPCS-{}".format(self._id), self._local_udp_tunnel[1], nio)

                await self.start_wrap_console()

                log.info("VPCS instance {} started PID={}".format(self.name, self._process.pid))
                self._started = True
                self.status = "started"
            except (OSError, subprocess.SubprocessError) as e:
                vpcs_stdout = self.read_vpcs_stdout()
                log.error("Could not start VPCS {}: {}\n{}".format(self._vpcs_path(), e, vpcs_stdout))
                raise VPCSError("Could not start VPCS {}: {}\n{}".format(self._vpcs_path(), e, vpcs_stdout))

    async def _termination_callback(self, returncode):
        """
        Called when the process has stopped.

        :param returncode: Process returncode
        """

        if self._started:
            log.info("VPCS process has stopped, return code: %d", returncode)
            self._started = False
            self.status = "stopped"
            self._process = None
            await self._stop_ubridge()
            await super().stop()
            if returncode != 0:
                self.project.emit("log.error", {"message": "VPCS process has stopped, return code: {}\n{}".format(returncode, self.read_vpcs_stdout())})

    async def stop(self):
        """
        Stops the VPCS process.
        """

        await self._stop_ubridge()
        if self.is_running():
            self._terminate_process()
            if self._process.returncode is None:
                try:
                    await wait_for_process_termination(self._process, timeout=3)
                except asyncio.TimeoutError:
                    if self._process.returncode is None:
                        try:
                            self._process.kill()
                        except OSError as e:
                            log.error("Cannot stop the VPCS process: {}".format(e))
                        if self._process.returncode is None:
                            log.warning('VPCS VM "{}" with PID={} is still running'.format(self._name, self._process.pid))

        self._process = None
        self._started = False
        await super().stop()

    async def reload(self):
        """
        Reloads the VPCS process (stop & start).
        """

        await self.stop()
        await self.start()

    def _terminate_process(self):
        """
        Terminate the process if running
        """

        log.info("Stopping VPCS instance {} PID={}".format(self.name, self._process.pid))
        if sys.platform.startswith("win32"):
            try:
                self._process.send_signal(signal.CTRL_BREAK_EVENT)
            except (SystemError, OSError):
                pass
        else:
            try:
                self._process.terminate()
            # Sometime the process may already be dead when we garbage collect
            except ProcessLookupError:
                pass

    def read_vpcs_stdout(self):
        """
        Reads the standard output of the VPCS process.
        Only use when the process has been stopped or has crashed.
        """

        output = ""
        if self._vpcs_stdout_file:
            try:
                with open(self._vpcs_stdout_file, "rb") as file:
                    output = file.read().decode("utf-8", errors="replace")
            except OSError as e:
                log.warning("Could not read {}: {}".format(self._vpcs_stdout_file, e))
        return output

    def is_running(self):
        """
        Checks if the VPCS process is running

        :returns: True or False
        """

        if self._process and self._process.returncode is None:
            return True
        return False

    @BaseNode.console_type.setter
    def console_type(self, new_console_type):
        """
        Sets the console type for this VPCS VM.

        :param new_console_type: console type (string)
        """

        if self.is_running() and self.console_type != new_console_type:
            raise VPCSError('"{name}" must be stopped to change the console type to {new_console_type}'.format(name=self._name, new_console_type=new_console_type))

        super(VPCSVM, VPCSVM).console_type.__set__(self, new_console_type)

    async def port_add_nio_binding(self, port_number, nio):
        """
        Adds a port NIO binding.

        :param port_number: port number
        :param nio: NIO instance to add to the slot/port
        """

        if not self._ethernet_adapter.port_exists(port_number):
            raise VPCSError("Port {port_number} doesn't exist on adapter {adapter}".format(adapter=self._ethernet_adapter,
                                                                                           port_number=port_number))

        if self.is_running():
            await self.add_ubridge_udp_connection("VPCS-{}".format(self._id), self._local_udp_tunnel[1], nio)

        self._ethernet_adapter.add_nio(port_number, nio)
        log.info('VPCS "{name}" [{id}]: {nio} added to port {port_number}'.format(name=self._name,
                                                                                  id=self.id,
                                                                                  nio=nio,
                                                                                  port_number=port_number))

        return nio

    async def port_update_nio_binding(self, port_number, nio):
        """
        Updates a port NIO binding.

        :param port_number: port number
        :param nio: NIO instance to update on the slot/port
        """

        if not self._ethernet_adapter.port_exists(port_number):
            raise VPCSError("Port {port_number} doesn't exist on adapter {adapter}".format(adapter=self._ethernet_adapter,
                                                                                           port_number=port_number))
        if self.is_running():
            await self.update_ubridge_udp_connection("VPCS-{}".format(self._id), self._local_udp_tunnel[1], nio)

    async def port_remove_nio_binding(self, port_number):
        """
        Removes a port NIO binding.

        :param port_number: port number

        :returns: NIO instance
        """

        if not self._ethernet_adapter.port_exists(port_number):
            raise VPCSError("Port {port_number} doesn't exist on adapter {adapter}".format(adapter=self._ethernet_adapter,
                                                                                           port_number=port_number))

        await self.stop_capture(port_number)
        if self.is_running():
            await self._ubridge_send("bridge delete {name}".format(name="VPCS-{}".format(self._id)))

        nio = self._ethernet_adapter.get_nio(port_number)
        if isinstance(nio, NIOUDP):
            self.manager.port_manager.release_udp_port(nio.lport, self._project)
        self._ethernet_adapter.remove_nio(port_number)

        log.info('VPCS "{name}" [{id}]: {nio} removed from port {port_number}'.format(name=self._name,
                                                                                      id=self.id,
                                                                                      nio=nio,
                                                                                      port_number=port_number))
        return nio

    def get_nio(self, port_number):
        """
        Gets a port NIO binding.

        :param port_number: port number

        :returns: NIO instance
        """

        if not self._ethernet_adapter.port_exists(port_number):
            raise VPCSError("Port {port_number} doesn't exist on adapter {adapter}".format(adapter=self._ethernet_adapter,
                                                                                           port_number=port_number))
        nio = self._ethernet_adapter.get_nio(port_number)
        if not nio:
            raise VPCSError("Port {} is not connected".format(port_number))
        return nio

    async def start_capture(self, port_number, output_file):
        """
        Starts a packet capture.

        :param port_number: port number
        :param output_file: PCAP destination file for the capture
        """

        nio = self.get_nio(port_number)
        if nio.capturing:
            raise VPCSError("Packet capture is already active on port {port_number}".format(port_number=port_number))

        nio.start_packet_capture(output_file)
        if self.ubridge:
            await self._ubridge_send('bridge start_capture {name} "{output_file}"'.format(name="VPCS-{}".format(self._id),
                                                                                               output_file=output_file))

        log.info("VPCS '{name}' [{id}]: starting packet capture on port {port_number}".format(name=self.name,
                                                                                              id=self.id,
                                                                                              port_number=port_number))

    async def stop_capture(self, port_number):
        """
        Stops a packet capture.

        :param port_number: port number
        """

        nio = self.get_nio(port_number)
        if not nio.capturing:
            return

        nio.stop_packet_capture()
        if self.ubridge:
            await self._ubridge_send('bridge stop_capture {name}'.format(name="VPCS-{}".format(self._id)))

        log.info("VPCS '{name}' [{id}]: stopping packet capture on port {port_number}".format(name=self.name,
                                                                                              id=self.id,
                                                                                              port_number=port_number))

    def _build_command(self):
        """
        Command to start the VPCS process.
        (to be passed to subprocess.Popen())

        VPCS command line:
        usage: vpcs [options] [scriptfile]
        Option:
            -h         print this help then exit
            -v         print version information then exit

            -i num     number of vpc instances to start (default is 9)
            -p port    run as a daemon listening on the tcp 'port'
            -m num     start byte of ether address, default from 0
            -r file    load and execute script file
                       compatible with older versions, DEPRECATED.

            -e         tap mode, using /dev/tapx by default (linux only)
            -u         udp mode, default

        udp mode options:
            -s port    local udp base port, default from 20000
            -c port    remote udp base port (dynamips udp port), default from 30000
            -t ip      remote host IP, default 127.0.0.1

        tap mode options:
            -d vm  device name, works only when -i is set to 1

        hypervisor mode option:
            -H port    run as the hypervisor listening on the tcp 'port'

          If no 'scriptfile' specified, vpcs will read and execute the file named
          'startup.vpc' if it exsits in the current directory.

        """

        command = [self._vpcs_path()]
        command.extend(["-p", str(self._internal_console_port)])  # listen to console port
        command.extend(["-m", str(self._manager.get_mac_id(self.id))])   # the unique ID is used to set the MAC address offset
        command.extend(["-i", "1"])  # option to start only one VPC instance
        command.extend(["-F"])  # option to avoid the daemonization of VPCS
        if self._vpcs_version >= parse_version("0.8b"):
            command.extend(["-R"])  # disable the relay feature of VPCS (starting with VPCS 0.8)
        else:
            log.warning("The VPCS relay feature could not be disabled because the VPCS version is below 0.8b")

        # use the local UDP tunnel to uBridge instead
        if not self._local_udp_tunnel:
            self._local_udp_tunnel = self._create_local_udp_tunnel()
        nio = self._local_udp_tunnel[0]
        if nio and isinstance(nio, NIOUDP):
            # UDP tunnel
            command.extend(["-s", str(nio.lport)])  # source UDP port
            command.extend(["-c", str(nio.rport)])  # destination UDP port
            try:
                command.extend(["-t", socket.gethostbyname(nio.rhost)])  # destination host, we need to resolve the hostname because VPCS doesn't support it
            except socket.gaierror as e:
                raise VPCSError("Can't resolve hostname {}".format(nio.rhost))

        if self.script_file:
            command.extend([os.path.basename(self.script_file)])
        return command

    @property
    def script_file(self):
        """
        Returns the startup script file for this VPCS VM.

        :returns: path to startup script file
        """

        # use the default VPCS file if it exists
        path = os.path.join(self.working_dir, 'startup.vpc')
        if os.path.exists(path):
            return path
        else:
            return None
