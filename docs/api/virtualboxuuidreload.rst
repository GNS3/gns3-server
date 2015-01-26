/virtualbox/{uuid}/reload
---------------------------------------------

.. contents::

POST /virtualbox/**{uuid}**/reload
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Reload a VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID

Response status codes
**********************
- **400**: Invalid instance UUID
- **404**: Instance doesn't exist
- **204**: Instance reloaded

