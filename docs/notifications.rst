Notifications
=============

You can receive notification from the controller allowing you to update your local data.

Notifications endpoints
***********************

You can listen the HTTP stream /notifications or the websocket.

   * :doc:`api/v2/controller/project/projectsprojectidnotifications`
   * :doc:`api/v2/controller/project/projectsprojectidnotificationsws`

We recommend using the websocket.

Available notifications
***********************

.. contents::
    :local:

ping
----
Keep the connection between client and controller.

.. literalinclude:: api/notifications/ping.json


compute.created
----------------

Compute has been created.

.. literalinclude:: api/notifications/compute.created.json


compute.updated
----------------

Compute has been updated. You will receive a lot of this
event because it's include change of CPU and memory usage
on the compute node.

.. literalinclude:: api/notifications/compute.updated.json


compute.deleted
---------------

Compute has been deleted.

.. literalinclude:: api/notifications/compute.deleted.json


node.created
------------

Node has been created.

.. literalinclude:: api/notifications/node.created.json


node.updated
------------

Node has been updated.

.. literalinclude:: api/notifications/node.updated.json


node.deleted
------------

Node has been deleted.

.. literalinclude:: api/notifications/node.deleted.json


link.created
------------

Link has been created. Note that a link when created
is not yet connected to both part.

.. literalinclude:: api/notifications/link.created.json


link.updated
------------

Link has been updated.

.. literalinclude:: api/notifications/link.updated.json


link.deleted
------------

Link has been deleted.

.. literalinclude:: api/notifications/link.deleted.json


drawing.created
---------------

Drawing has been created.

.. literalinclude:: api/notifications/drawing.created.json


drawing.updated
---------------

Drawing has been updated. To reduce data transfert if the
svg field has not change the field is not included.

.. literalinclude:: api/notifications/drawing.updated.json


drawing.deleted
---------------

Drawing has been deleted.

.. literalinclude:: api/notifications/drawing.deleted.json


project.updated
---------------

Project has been updated.

.. literalinclude:: api/notifications/project.updated.json


project.closed
---------------

Project has been closed.

.. literalinclude:: api/notifications/project.closed.json


snapshot.restored
--------------------------

Snapshot has been restored

.. literalinclude:: api/notifications/project.snapshot_restored.json

log.error
---------

Send an error to the user

.. literalinclude:: api/notifications/log.error.json


log.warning
------------

Send a warning to the user

.. literalinclude:: api/notifications/log.warning.json


log.info
---------

Send an information to the user

.. literalinclude:: api/notifications/log.info.json


settings.updated
-----------------

GUI settings updated. Will be removed in a later release.

.. literalinclude:: api/notifications/settings.updated.json


