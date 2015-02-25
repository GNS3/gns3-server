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

Limitations
============

Concurrency
------------

A VM can't process multiple request in the same time. But you can make
multiple request on multiple VM. It's transparent for the client
when the first request on a VM start a lock is acquire for this VM id
and released for the next request at the end. You can safely send all
the requests in the same time and let the server manage an efficent concurrency.

We think it can be a little slower for some operations, but it's remove a big
complexity for the client due to the fact only some command on some VM can be
concurrent.


