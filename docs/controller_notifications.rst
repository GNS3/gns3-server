Controller notifications
========================

Controller notifications can be received from the controller, they can be used to get information
about computes and appliance.

Notification endpoints
**********************

Listen to the HTTP stream endpoint or to the WebSocket endpoint.

   * :doc:`api/v2/controller/notification/notifications`
   * :doc:`api/v2/controller/notification/notificationsws`

It is recommended to use the WebSocket endpoint.

Available notifications
***********************

.. contents::
    :local:

ping
----
Keep-alive between client and controller. Also used to receive the current CPU and memory usage.

.. literalinclude:: api/notifications/ping.json


compute.created
---------------

A compute has been created.

.. literalinclude:: api/notifications/compute.created.json

compute.updated
---------------

A compute has been updated.

.. literalinclude:: api/notifications/compute.updated.json


compute.deleted
---------------

A compute has been deleted.

.. literalinclude:: api/notifications/compute.deleted.json


template.created
-----------------

A template has been created.

.. literalinclude:: api/notifications/template.created.json


template.updated
-----------------

A template has been updated.

.. literalinclude:: api/notifications/template.updated.json


template.deleted
-----------------

A template has been deleted.

.. literalinclude:: api/notifications/template.deleted.json


log.error
---------

Sends an error

.. literalinclude:: api/notifications/log.error.json


log.warning
------------

Sends a warning

.. literalinclude:: api/notifications/log.warning.json


log.info
---------

Sends an information

.. literalinclude:: api/notifications/log.info.json
