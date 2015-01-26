/virtualbox/{uuid}/resume
---------------------------------------------

.. contents::

POST /virtualbox/**{uuid}**/resume
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Resume a suspended VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID

Response status codes
**********************
- **400**: Invalid instance UUID
- **404**: Instance doesn't exist
- **204**: Instance resumed

