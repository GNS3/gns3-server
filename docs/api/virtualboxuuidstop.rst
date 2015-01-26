/virtualbox/{uuid}/stop
---------------------------------------------

.. contents::

POST /virtualbox/**{uuid}**/stop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID

Response status codes
**********************
- **400**: Invalid instance UUID
- **404**: Instance doesn't exist
- **204**: Instance stopped

Sample session
***************


.. literalinclude:: examples/post_virtualboxuuidstop.txt

