Sample session using curl
=========================

You need to read the :doc:`glossary`, and :doc:`general` before.

Full endpoints list is available: :doc:`endpoints`

.. warning::

    Beware the output of this sample is truncated in order
    to simplify the understanding. Please read the
    documentation for the exact output.

You can check the server version with a simple curl command:

.. code-block:: shell-session

    # curl "http://localhost:3080/v2/version"
    {
        "version": "2.0.0dev1"
    }


List computes
##############

We will list the computes node where we can run our nodes:

.. code-block:: shell-session

    # curl "http://localhost:3080/v2/computes"
    [
        {
            "compute_id": "local",
            "connected": true,
            "host": "127.0.0.1",
            "name": "Local",
            "port": 3080,
            "protocol": "http",
            "user": "admin"
        }
    ]

In this sample we have only one compute where we can run our nodes. This compute as a special id: local. This
mean it's the local server embed in the GNS3 controller.

Create project
###############

The next step is to create a project.

.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v2/projects" -d '{"name": "test"}'
    {
        "name": "test",
        "project_id": "b8c070f7-f34c-4b7b-ba6f-be3d26ed073f",
    }

Create nodes
#############

With this project id we can now create two VPCS Node.

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
        "properties": {
            "startup_script": null,
            "startup_script_path": null
        },
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
        "properties": {
            "startup_script": null,
            "startup_script_path": null
        },
        "status": "stopped"
    }

The properties dictionnary contains all setting specific to a node type (dynamips, docker, vpcs...)

Link nodes
###########

Now we need to link the two VPCS by connecting their port 0 together.

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

Now we can start the two nodes.

.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/nodes/f124dec0-830a-451e-a314-be50bbd58a00/start" -d "{}"
    # curl -X POST "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/nodes/83892a4d-aea0-4350-8b3e-d0af3713da74/start" -d "{}"

Connect to nodes
#################

Everything should be started now. You can connect via telnet to the different Node.
The port is the field console in the create Node request.

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

And we stop the two nodes.

.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/nodes/f124dec0-830a-451e-a314-be50bbd58a00/stop" -d "{}"
    # curl -X POST "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/nodes/83892a4d-aea0-4350-8b3e-d0af3713da74/stop" -d "{}"


Add a visual element
######################

When you want add visual elements to the topology like rectangle, circle, images you can just send a raw SVG.
This will display a red square in the middle of your topologies:


.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/drawings" -d '{"x":0, "y": 12, "svg": "<svg width=\"50\" height=\"50\"><rect width=\"50\" height=\"50\" style=\"fill: #ff0000\"></rect></svg>"}'

Tips: you can embed png/jpg... by using a base64 encoding in the SVG.


Create a Qemu node
###################

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
    }%


Notifications
#############

You can see notification about the changes via the notification feed:

.. code-block:: shell-session

    # curl "http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/notifications"
    {"action": "ping", "event": {"compute_id": "local", "cpu_usage_percent": 35.7, "memory_usage_percent": 80.7}}
    {"action": "node.updated", "event": {"command_line": "/usr/local/bin/vpcs -p 5001 -m 1 -i 1 -F -R -s 10001 -c 10000 -t 127.0.0.1", "compute_id": "local", "console": 5001, "console_host": "127.0.0.1", "console_type": "telnet", "name": "VPCS 2", "node_id": "83892a4d-aea0-4350-8b3e-d0af3713da74", "node_type": "vpcs", "project_id": "b8c070f7-f34c-4b7b-ba6f-be3d26ed073f", "properties": {"startup_script": null, "startup_script_path": null}, "status": "started"}}

A websocket version is also available on http://localhost:3080/v2/projects/b8c070f7-f34c-4b7b-ba6f-be3d26ed073f/notifications/ws

Read :doc:`notifications` for more informations


How to found the endpoints?
###########################

Full endpoints list is available: :doc:`endpoints`

If you start the server with **--debug** you can see all the requests made by the client and by the controller to the computes nodes.
