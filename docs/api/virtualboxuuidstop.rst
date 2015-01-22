/virtualbox/{uuid}/stop
---------------------------------------------

.. contents::

POST /virtualbox/**{uuid}**/stop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a VirtualBox VM instance

Parameters
**********
- **uuid**: VirtualBox VM instance UUID

Response status codes
**********************
- **400**: Invalid VirtualBox VM instance UUID
- **404**: VirtualBox VM instance doesn't exist
- **204**: VirtualBox VM instance stopped

Sample session
***************


.. literalinclude:: examples/post_virtualboxuuidstop.txt

