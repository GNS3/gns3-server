/virtualbox/{uuid}/suspend
---------------------------------------------

.. contents::

POST /virtualbox/**{uuid}**/suspend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Suspend a VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID

Response status codes
**********************
- **400**: Invalid instance UUID
- **404**: Instance doesn't exist
- **204**: Instance suspended

