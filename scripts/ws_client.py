# -*- coding: utf-8 -*-
#
# Copyright (C) 2014 GNS3 Technologies Inc.
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

from ws4py.client.threadedclient import WebSocketClient


class WSClient(WebSocketClient):

    def opened(self):

        print("Connection successful with {}:{}".format(self.host, self.port))

        self.send('{"jsonrpc": 2.0, "method": "dynamips.settings", "params": {"path": "/usr/local/bin/dynamips", "allocate_hypervisor_per_device": true, "working_dir": "/tmp/gns3-1b4grwm3-files", "udp_end_port_range": 20000, "sparse_memory_support": true, "allocate_hypervisor_per_ios_image": true, "aux_start_port_range": 2501, "use_local_server": true, "hypervisor_end_port_range": 7700, "aux_end_port_range": 3000, "mmap_support": true, "console_start_port_range": 2001, "console_end_port_range": 2500, "hypervisor_start_port_range": 7200, "ghost_ios_support": true, "memory_usage_limit_per_hypervisor": 1024, "jit_sharing_support": false, "udp_start_port_range": 10001}}')
        self.send('{"jsonrpc": 2.0, "method": "dynamips.vm.create", "id": "e8caf5be-de3d-40dd-80b9-ab6df8029570", "params": {"image": "/home/grossmj/GNS3/images/IOS/c3725-advipservicesk9-mz.124-15.T14.image", "name": "R1", "platform": "c3725", "ram": 256}}')

    def closed(self, code, reason=None):

        print("Closed down. Code: {} Reason: {}".format(code, reason))

    def received_message(self, m):

        print(m)
        if len(m) == 175:
            self.close(reason='Bye bye')

if __name__ == '__main__':
    try:
        ws = WSClient('ws://localhost:8000/', protocols=['http-only', 'chat'])
        ws.connect()
        ws.run_forever()
    except KeyboardInterrupt:
        ws.close()
