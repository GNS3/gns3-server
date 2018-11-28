Sample sessions using curl
==========================

Read the :doc:`glossary`, and :doc:`general` pages first.

A list of all endpoints is available in :doc:`endpoints`

.. warning::

    Note that the output of the samples can be truncated in
    order to simplify their understanding. Please read the
    documentation for the exact output meaning.

Server version
###############

Check the server version with a simple curl command:

.. code-block:: shell-session

    # curl "http://localhost:3080/v2/version"
    {
        "local": false,
        "version": "2.1.4"
    }


List computes
##############

List all the computes:

.. code-block:: shell-session

    # curl "http://localhost:3080/v2/computes"
    [
        {
            "compute_id": "local",
            "connected": true,
            "host": "127.0.0.1",
            "name": "local",
            "port": 3080,
            "protocol": "http",
            "user": "admin"
        }
    ]

There is only one compute where nodes can be run in this example.
This compute as a special id: local, this is the local server which is embedded in the GNS3 controller.

Create a project
#################

The next step is to create a project:

.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v2/projects" -d '{"name": "test"}'
    {
        "name": "test",
        "project_id": "b8c070f7-f34c-4b7b-ba6f-be3d26ed073f",
    }

Create nodes
#############

Using the project id, it is now possible to create two VPCS nodes:

.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/nodes" -d '{"name": "VPCS 1", "node_type": "vpcs", "compute_id": "local"}'
    {
        "compute_id": "local",
        "console": 5000,
        "console_host": "127.0.0.1",
        "console_type": "telnet",
        "name": "VPCS 1",
        "node_id": "f124dec0-830a-451e-a314-be50bbd58a00",
        "node_type": "vpcs",
        "project_id": "b8c070f7-f34c-4b7b-ba6f-be3d26ed073f",
        "status": "stopped"
    }

    # curl -X POST "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/nodes" -d '{"name": "VPCS 2", "node_type": "vpcs", "compute_id": "local"}'
    {
        "compute_id": "local",
        "console": 5001,
        "console_host": "127.0.0.1",
        "console_type": "telnet",
        "name": "VPCS 2",
        "node_id": "83892a4d-aea0-4350-8b3e-d0af3713da74",
        "node_type": "vpcs",
        "project_id": "b8c070f7-f34c-4b7b-ba6f-be3d26ed073f",
        "properties": {},
        "status": "stopped"
    }

Link nodes
###########

The two VPCS nodes can be linked together using their port number 0 (VPCS has only one network adapter with one port):

.. code-block:: shell-session

    # curl -X POST  "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/links" -d '{"nodes": [{"adapter_number": 0, "node_id": "f124dec0-830a-451e-a314-be50bbd58a00", "port_number": 0}, {"adapter_number": 0, "node_id": "83892a4d-aea0-4350-8b3e-d0af3713da74", "port_number": 0}]}'
    {
        "capture_file_name": null,
        "capture_file_path": null,
        "capturing": false,
        "link_id": "007f2177-6790-4e1b-ac28-41fa226b2a06",
        "nodes": [
            {
                "adapter_number": 0,
                "node_id": "f124dec0-830a-451e-a314-be50bbd58a00",
                "port_number": 0
            },
            {
                "adapter_number": 0,
                "node_id": "83892a4d-aea0-4350-8b3e-d0af3713da74",
                "port_number": 0
            }
        ],
        "project_id": "b8c070f7-f34c-4b7b-ba6f-be3d26ed073f"
    }

Start nodes
###########

Start the two nodes:

.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/nodes/f124dec0-830a-451e-a314-be50bbd58a00/start" -d "{}"
    # curl -X POST "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/nodes/83892a4d-aea0-4350-8b3e-d0af3713da74/start" -d "{}"

Connect to nodes
#################

Use a Telnet client to connect to the nodes once they have been started.
The port number can be found in the output when the nodes have been created above.

.. code-block:: shell-session

    # telnet 127.0.0.1 5000
    Trying 127.0.0.1...
    Connected to localhost.
    Escape character is '^]'.

    Welcome to Virtual PC Simulator, version 0.6
    Dedicated to Daling.
    Build time: Dec 29 2014 12:51:46
    Copyright (c) 2007-2014, Paul Meng (mirnshi@gmail.com)
    All rights reserved.

    VPCS is free software, distributed under the terms of the "BSD" licence.
    Source code and license can be found at vpcs.sf.net.
    For more information, please visit wiki.freecode.com.cn.

    Press '?' to get help.

    VPCS> ip 192.168.1.1
    Checking for duplicate address...
    PC1 : 192.168.1.1 255.255.255.0

    VPCS> disconnect

    Good-bye
    Connection closed by foreign host.

    # telnet 127.0.0.1 5001
    Trying 127.0.0.1...
    Connected to localhost.
    Escape character is '^]'.

    Welcome to Virtual PC Simulator, version 0.6
    Dedicated to Daling.
    Build time: Dec 29 2014 12:51:46
    Copyright (c) 2007-2014, Paul Meng (mirnshi@gmail.com)
    All rights reserved.

    VPCS is free software, distributed under the terms of the "BSD" licence.
    Source code and license can be found at vpcs.sf.net.
    For more information, please visit wiki.freecode.com.cn.

    Press '?' to get help.

    VPCS> ip 192.168.1.2
    Checking for duplicate address...
    PC1 : 192.168.1.2 255.255.255.0

    VPCS> ping 192.168.1.1
    84 bytes from 192.168.1.1 icmp_seq=1 ttl=64 time=0.179 ms
    84 bytes from 192.168.1.1 icmp_seq=2 ttl=64 time=0.218 ms
    84 bytes from 192.168.1.1 icmp_seq=3 ttl=64 time=0.190 ms
    84 bytes from 192.168.1.1 icmp_seq=4 ttl=64 time=0.198 ms
    84 bytes from 192.168.1.1 icmp_seq=5 ttl=64 time=0.185 ms

    VPCS> disconnect
    Good-bye
    Connection closed by foreign host.


Stop nodes
##########

Stop the two nodes:

.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/nodes/f124dec0-830a-451e-a314-be50bbd58a00/stop" -d "{}"
    # curl -X POST "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/nodes/83892a4d-aea0-4350-8b3e-d0af3713da74/stop" -d "{}"


Add visual elements
####################

Visual elements like rectangle, ellipses or images in the form of raw SVG can be added to a project.

This will display a red square in the middle of your canvas:

.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/drawings" -d '{"x":0, "y": 12, "svg": "<svg width=\"50\" height=\"50\"><rect width=\"50\" height=\"50\" style=\"fill: #ff0000\"></rect></svg>"}'

Tip: embed PNG, JPEG etc. images using base64 encoding in the SVG.


Add a packet filter
####################

Packet filters allow to filter packet on a given link. Here to drop a packet every 5 packets:

.. code-block:: shell-session

    # curl -X PUT "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/links/007f2177-6790-4e1b-ac28-41fa226b2a06" -d '{"filters": {"frequency_drop": [5]}}'

Template creation
###################

A template contains all the required settings to create a new node. This is useful to create many nodes with the same settings.

.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v2/templates" -d '{"name": "Qemu template", "compute_id": "local", "platform": "i386", "hda_disk_image": "IOSvL2-15.2.4.0.55E.qcow2", "ram": 512, "template_type": "qemu"}'

Node creation
##############

There are two ways to add nodes.

1. Manually by passing all the information required to create a new node.
2. Using a template stored on your server.

Using a template
-----------------

List all the available templates:

.. code-block:: shell-session

    # curl "http://localhost:3080/v2/templates"

    [
        {
            "adapter_type": "e1000",
            "adapters": 1,
            "template_id": "70c79a82-5ef6-4911-8284-f6f31eb0ebf2",
            "template_type": "qemu",
            "bios_image": "",
            "boot_priority": "c",
            "builtin": false,
            "category": "guest",
            "cdrom_image": "",
            "compute_id": "local",
            "console_auto_start": false,
            "console_type": "telnet",
            "cpu_throttling": 0,
            "cpus": 1,
            "custom_adapters": [],
            "default_name_format": "{name}-{0}",
            "first_port_name": "",
            "hda_disk_image": "IOSvL2-15.2.4.0.55E.qcow2",
            "hda_disk_interface": "ide",
            "hdb_disk_image": "",
            "hdb_disk_interface": "ide",
            "hdc_disk_image": "",
            "hdc_disk_interface": "ide",
            "hdd_disk_image": "",
            "hdd_disk_interface": "ide",
            "initrd": "",
            "kernel_command_line": "",
            "kernel_image": "",
            "legacy_networking": false,
            "linked_clone": true,
            "mac_address": "",
            "name": "Qemu template",
            "on_close": "power_off",
            "options": "",
            "platform": "i386",
            "port_name_format": "Ethernet{0}",
            "port_segment_size": 0,
            "process_priority": "normal",
            "qemu_path": "",
            "ram": 512,
            "symbol": ":/symbols/qemu_guest.svg",
            "usage": ""
        }
        {
            "adapters": 1,
            "template_id": "888984a8-c802-427b-97a7-ee097ee63faf",
            "template_type": "docker",
            "builtin": false,
            "category": "guest",
            "compute_id": "local",
            "console_auto_start": false,
            "console_http_path": "/",
            "console_http_port": 80,
            "console_resolution": "1024x768",
            "console_type": "telnet",
            "custom_adapters": [],
            "default_name_format": "{name}-{0}",
            "environment": "",
            "extra_hosts": "",
            "image": "debian:latest",
            "name": "Debian",
            "start_command": "",
            "symbol": ":/symbols/docker_guest.svg"
        },
    ]

Use the template and add coordinates to select where the node will be put on the canvas:

.. code-block:: shell-session

 # curl -X POST http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/templates/888984a8-c802-427b-97a7-ee097ee63faf -d '{"x": 12, "y": 42}'


Manual creation of a Qemu node
------------------------------

.. code-block:: shell-session

    # curl -X POST http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/nodes -d '{"node_type": "qemu", "compute_id": "local", "name": "Microcore1", "properties": {"hda_disk_image": "linux-microcore-6.4.img", "ram": 256, "qemu_path": "qemu-system-x86_64"}}' 

    {
        "command_line": "",
        "compute_id": "local",
        "console": 5001,
        "console_host": "127.0.0.1",
        "console_type": "telnet",
        "first_port_name": null,
        "height": 59,
        "label": {
            "rotation": 0,
            "style": "font-family: TypeWriter;font-size: 10;font-weight: bold;fill: #000000;fill-opacity: 1.0;",
            "text": "Microcore1",
            "x": null,
            "y": -40
        },
        "name": "Microcore1",
        "node_directory": "/Users/noplay/GNS3/projects/untitled/project-files/qemu/9e4eb45b-22f5-450d-8277-2934fbd0aa20",
        "node_id": "9e4eb45b-22f5-450d-8277-2934fbd0aa20",
        "node_type": "qemu",
        "port_name_format": "Ethernet{0}",
        "port_segment_size": 0,
        "ports": [
            {
                "adapter_number": 0,
                "data_link_types": {
                    "Ethernet": "DLT_EN10MB"
                },
                "link_type": "ethernet",
                "name": "Ethernet0",
                "port_number": 0,
                "short_name": "e0/0"
            }
        ],
        "project_id": "b8c070f7-f34c-4b7b-ba6f-be3d26ed073f",
        "properties": {
            "acpi_shutdown": false,
            "adapter_type": "e1000",
            "adapters": 1,
            "boot_priority": "c",
            "cdrom_image": "",
            "cdrom_image_md5sum": null,
            "cpu_throttling": 0,
            "cpus": 1,
            "hda_disk_image": "linux-microcore-6.4.img",
            "hda_disk_image_md5sum": "877419f975c4891c019947ceead5c696",
            "hda_disk_interface": "ide",
            "hdb_disk_image": "",
            "hdb_disk_image_md5sum": null,
            "hdb_disk_interface": "ide",
            "hdc_disk_image": "",
            "hdc_disk_image_md5sum": null,
            "hdc_disk_interface": "ide",
            "hdd_disk_image": "",
            "hdd_disk_image_md5sum": null,
            "hdd_disk_interface": "ide",
            "initrd": "",
            "initrd_md5sum": null,
            "kernel_command_line": "",
            "kernel_image": "",
            "kernel_image_md5sum": null,
            "legacy_networking": false,
            "mac_address": "00:af:69:aa:20:00",
            "options": "",
            "platform": "x86_64",
            "process_priority": "low",
            "qemu_path": "/usr/local/bin/qemu-system-x86_64",
            "ram": 256,
            "usage": ""
        },
        "status": "stopped",
        "symbol": ":/symbols/computer.svg",
        "width": 65,
        "x": 0,
        "y": 0,
        "z": 0
    }


Manual creation of a Dynamips node
-----------------------------------

.. code-block:: shell-session

    # curl http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/nodes -d '{"symbol": ":/symbols/router.svg", "name": "R1", "properties": {"platform": "c7200", "nvram": 512, "image": "c7200-adventerprisek9-mz.124-24.T8.image", "ram": 512, "slot3": "PA-GE", "system_id": "FTX0945W0MY", "slot0": "C7200-IO-FE", "slot2": "PA-GE", "slot1": "PA-GE",  "idlepc": "0x606e0538", "startup_config_content": "hostname %h\n"}, "compute_id": "local", "node_type": "dynamips"}'

    {
        "command_line": null,
        "compute_id": "local",
        "console": 5002,
        "console_host": "127.0.0.1",
        "console_type": "telnet",
        "first_port_name": null,
        "height": 45,
        "label": {
            "rotation": 0,
            "style": "font-family: TypeWriter;font-size: 10;font-weight: bold;fill: #000000;fill-opacity: 1.0;",
            "text": "R1",
            "x": null,
            "y": -32
        },
        "name": "R1",
        "node_directory": "/Users/noplay/GNS3/projects/untitled/project-files/dynamips",
        "node_id": "f7367e7e-804e-48be-9037-284d4d9b059e",
        "node_type": "dynamips",
        "port_name_format": "Ethernet{0}",
        "port_segment_size": 0,
        "ports": [
            {
                "adapter_number": 0,
                "data_link_types": {
                    "Ethernet": "DLT_EN10MB"
                },
                "link_type": "ethernet",
                "name": "FastEthernet0/0",
                "port_number": 0,
                "short_name": "f0/0"
            },
            {
                "adapter_number": 1,
                "data_link_types": {
                    "Ethernet": "DLT_EN10MB"
                },
                "link_type": "ethernet",
                "name": "GigabitEthernet0/0",
                "port_number": 0,
                "short_name": "g0/0"
            },
            {
                "adapter_number": 2,
                "data_link_types": {
                    "Ethernet": "DLT_EN10MB"
                },
                "link_type": "ethernet",
                "name": "GigabitEthernet1/0",
                "port_number": 0,
                "short_name": "g1/0"
            },
            {
                "adapter_number": 3,
                "data_link_types": {
                    "Ethernet": "DLT_EN10MB"
                },
                "link_type": "ethernet",
                "name": "GigabitEthernet2/0",
                "port_number": 0,
                "short_name": "g2/0"
            }
        ],
        "project_id": "b8c070f7-f34c-4b7b-ba6f-be3d26ed073f",
        "properties": {
            "auto_delete_disks": false,
            "aux": null,
            "clock_divisor": 4,
            "disk0": 64,
            "disk1": 0,
            "dynamips_id": 2,
            "exec_area": 64,
            "idlemax": 500,
            "idlepc": "0x606e0538",
            "idlesleep": 30,
            "image": "c7200-adventerprisek9-mz.124-24.T8.image",
            "image_md5sum": "b89d30823cbbda460364991ed18449c7",
            "mac_addr": "ca02.dcbb.0000",
            "midplane": "vxr",
            "mmap": true,
            "npe": "npe-400",
            "nvram": 512,
            "platform": "c7200",
            "power_supplies": [
                1,
                1
            ],
            "private_config": "",
            "private_config_content": "",
            "ram": 512,
            "sensors": [
                22,
                22,
                22,
                22
            ],
            "slot0": "C7200-IO-FE",
            "slot1": "PA-GE",
            "slot2": "PA-GE",
            "slot3": "PA-GE",
            "slot4": null,
            "slot5": null,
            "slot6": null,
            "sparsemem": true,
            "startup_config": "configs/i2_startup-config.cfg",
            "startup_config_content": "!\nhostname R1\n",
            "system_id": "FTX0945W0MY"
        },
        "status": "stopped",
        "symbol": ":/symbols/router.svg",
        "width": 66,
        "x": 0,
        "y": 0,
        "z": 0
    }

Controller notifications
########################

Controller notifications can be seen by connecting to the notification feed:

.. code-block:: shell-session

    # curl "http://localhost:3080/v2/notifications"
    {"action": "ping", "event": {"compute_id": "local", "cpu_usage_percent": 35.7, "memory_usage_percent": 80.7}}
    {"action": "compute.updated", "event": {"capabilities": {"node_types": ["cloud", "ethernet_hub", "ethernet_switch", "nat", "vpcs", "virtualbox", "dynamips", "frame_relay_switch", "atm_switch", "qemu", "vmware", "traceng", "docker", "iou"], "platform": "linux", "version": "2.2.0dev5-68ecbff"}, "compute_id": "local", "connected": true, "cpu_usage_percent": 12.0, "host": "127.0.0.1", "last_error": null, "memory_usage_percent": 45.7, "name": "coruscant", "port": 3080, "protocol": "http", "user": "admin"}}
    {"action": "template.created", "event": {"template_id": "384f9b02-6451-4b27-8d29-76623b5d9e79", "template_type": "dynamips", "auto_delete_disks": false, "builtin": false, "category": "router", "compute_id": "local", "console_auto_start": false, "console_type": "telnet", "default_name_format": "R{0}", "disk0": 0, "disk1": 0, "exec_area": 64, "idlemax": 500, "idlepc": "", "idlesleep": 30, "image": "c3725-adventerprisek9-mz.124-15.T14.image", "iomem": 5, "mac_addr": "", "mmap": true, "name": "My c3725", "nvram": 256, "platform": "c3725", "private_config": "", "ram": 128, "sparsemem": true, "startup_config": "ios_base_startup-config.txt", "symbol": ":/symbols/router.svg", "system_id": "FTX0945W0MY"}}

A Websocket notification stream is also available on http://localhost:3080/v2/notifications/ws

Read :doc:`controller_notifications` for more information.


Project notifications
#####################

Project notifications can be seen by connecting to the notification feed:

.. code-block:: shell-session

    # curl "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/notifications"
    {"action": "node.updated", "event": {"command_line": "/usr/local/bin/vpcs -p 5001 -m 1 -i 1 -F -R -s 10001 -c 10000 -t 127.0.0.1", "compute_id": "local", "console": 5001, "console_host": "127.0.0.1", "console_type": "telnet", "name": "VPCS 2", "node_id": "83892a4d-aea0-4350-8b3e-d0af3713da74", "node_type": "vpcs", "project_id": "b8c070f7-f34c-4b7b-ba6f-be3d26ed073f", "properties": {"startup_script": null, "startup_script_path": null}, "status": "started"}}

A Websocket notification stream is also available on http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/notifications/ws

Read :doc:`project_notifications` for more information.


Where to find the endpoints?
###########################

A list of all endpoints is available: :doc:`endpoints`

Tip: requests made by a client and by a controller to the computes nodes can been seen  if the server is started with the **--debug** parameter.
