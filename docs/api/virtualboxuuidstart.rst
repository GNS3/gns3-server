/virtualbox/{uuid}/start
---------------------------------------------

.. contents::

POST /virtualbox/**{uuid}**/start
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Start a VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID

Response status codes
**********************
- **400**: Invalid instance UUID
- **404**: Instance doesn't exist
- **204**: Instance started

Sample session
***************


.. literalinclude:: examples/post_virtualboxuuidstart.txt

