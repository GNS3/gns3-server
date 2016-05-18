Communications
===============

All the communication are done over HTTP using JSON.

Errors
======

In case of error a standard HTTP error is raise and you got a
JSON like that

.. code-block:: json
    
    {
        "status": 409,
        "message": "Conflict"
    }

Sample session using curl
=========================

.. warning::

    Beware the output of this sample is truncated in order
    to simplify the understanding. Please read the
    documentation for the exact output.

You can check the server version with a simple curl command:

.. code-block:: shell-session

    # curl "http://localhost:3080/v1/version"
    {
        "version": "2.0.0dev1"
    }


The next step is to create a project.

.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v1/projects" -d '{"name": "test"}'
    {
        "name": "test",
        "path": null,
        "project_id": "994d95b6-7dd4-467b-898c-14cf34900b7b",
        "temporary": false
    }

With this project id we can now create two VPCS Node.

.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v1/projects/42f9feee-3217-4104-981e-85d5f0a806ec/vpcs/vms" -d '{"name": "VPCS 1"}'
    {
        "console": 2000,
        "name": "VPCS 1",
        "project_id": "42f9feee-3217-4104-981e-85d5f0a806ec",
        "vm_id": "24d2e16b-fbef-4259-ae34-7bc21a41ee28"
    }%

    # curl -X POST "http://localhost:3080/v1/projects/42f9feee-3217-4104-981e-85d5f0a806ec/vpcs/vms" -d '{"name": "VPCS 2"}'
    {
        "console": 2001,
        "name": "VPCS 2",
        "vm_id": "daefc24a-103c-4717-8e01-6517d931c1ae"
    }

Now we need to link the two VPCS. The first step is to allocate on the remote servers
two UDP ports.

.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v1/projects/42f9feee-3217-4104-981e-85d5f0a806ec/ports/udp" -d '{}'
    {
        "udp_port": 10000
    }                                                                                  
    
    # curl -X POST "http://localhost:3080/v1/projects/42f9feee-3217-4104-981e-85d5f0a806ec/ports/udp" -d '{}'
    {
        "udp_port": 10001
    }


We can create the bidirectionnal communication between the two VPCS. The
communication is made by creating two UDP tunnels.

.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v1/projects/42f9feee-3217-4104-981e-85d5f0a806ec/vpcs/vms/24d2e16b-fbef-4259-ae34-7bc21a41ee28/adapters/0/ports/0/nio" -d '{"lport": 10000, "rhost": "127.0.0.1", "rport": 10001, "type": "nio_udp"}'
    {
        "lport": 10000,
        "rhost": "127.0.0.1",
        "rport": 10001,
        "type": "nio_udp"
    }

    # curl -X POST "http://localhost:3080/v1/projects/42f9feee-3217-4104-981e-85d5f0a806ec/vpcs/vms/daefc24a-103c-4717-8e01-6517d931c1ae/adapters/0/ports/0/nio" -d '{"lport": 10001, "rhost": "127.0.0.1", "rport": 10000, "type": "nio_udp"}'
    {
        "lport": 10001,
        "rhost": "127.0.0.1",
        "rport": 10000,
        "type": "nio_udp"
    }

Now we can start the two Node

.. code-block:: shell-session

    # curl -X POST "http://localhost:3080/v1/projects/42f9feee-3217-4104-981e-85d5f0a806ec/vpcs/vms/24d2e16b-fbef-4259-ae34-7bc21a41ee28/start" -d "{}"
    # curl -X POST "http://localhost:3080/v1/projects/42f9feee-3217-4104-981e-85d5f0a806ec/vpcs/vms/daefc24a-103c-4717-8e01-6517d931c1ae/start" -d '{}'

Everything should be started now. You can connect via telnet to the different Node.
The port is the field console in the create Node request.

.. code-block:: shell-session

    # telnet 127.0.0.1 2000
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

    # telnet 127.0.0.1 2001
    telnet 127.0.0.1 2001
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

Limitations
============

Concurrency
------------

A node can't process multiple request in the same time. But you can make
multiple request on multiple node. It's transparent for the client
when the first request on a Node start a lock is acquire for this node id
and released for the next request at the end. You can safely send all
the requests in the same time and let the server manage an efficent concurrency.

We think it can be a little slower for some operations, but it's remove a big
complexity for the client due to the fact only some command on some node can be
concurrent.


Authentication
-----------------

You can use HTTP basic auth to protect the access to the API. And run
the API over HTTPS.


Notifications
=============

You can receive notification from the server if you listen the HTTP stream /notifications or the websocket.

The available notification are:
    * ping
    * node.created
    * node.updated
    * node.deleted
    * link.created
    * link.updated
    * link.deleted
    * log.error
    * log.warning
    * log.info

Previous versions
=================

API version 1
-------------
Shipped with GNS3 1.3, 1.4 and 1.5. This API doesn't support the controller system.

