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
