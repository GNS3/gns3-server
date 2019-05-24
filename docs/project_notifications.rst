Project notifications
=====================

Project notifications can be received from the controller, they can be used to update projects.

Notification endpoints
**********************

Listen to the HTTP stream endpoint or to the WebSocket endpoint.

   * :doc:`api/v2/controller/project/projectsprojectidnotifications`
   * :doc:`api/v2/controller/project/projectsprojectidnotificationsws`

It is recommended to use the WebSocket endpoint.

Available notifications
***********************

.. contents::
    :local:

ping
----
Keep-alive between client and controller. Also used to receive the current CPU and memory usage.

.. literalinclude:: api/notifications/ping.json


node.created
------------

A node has been created.

.. literalinclude:: api/notifications/node.created.json


node.updated
------------

A node has been updated.

.. literalinclude:: api/notifications/node.updated.json


node.deleted
------------

A node has been deleted.

.. literalinclude:: api/notifications/node.deleted.json


link.created
------------

A link has been created. Note that a link is not connected
to any node when it is created.

.. literalinclude:: api/notifications/link.created.json


link.updated
------------

A link has been updated.

.. literalinclude:: api/notifications/link.updated.json


link.deleted
------------

A link has been deleted.

.. literalinclude:: api/notifications/link.deleted.json


drawing.created
---------------

A drawing has been created.

.. literalinclude:: api/notifications/drawing.created.json


drawing.updated
---------------

A drawing has been updated. The svg field is only included if it
has changed in order to reduce data transfer.

.. literalinclude:: api/notifications/drawing.updated.json


drawing.deleted
---------------

A drawing has been deleted.

.. literalinclude:: api/notifications/drawing.deleted.json


project.updated
---------------

A project has been updated.

.. literalinclude:: api/notifications/project.updated.json


project.closed
---------------

A project has been closed.

.. literalinclude:: api/notifications/project.closed.json


snapshot.restored
--------------------------

A snapshot has been restored

.. literalinclude:: api/notifications/project.snapshot_restored.json

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
