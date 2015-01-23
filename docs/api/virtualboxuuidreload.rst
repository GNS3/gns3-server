/virtualbox/{uuid}/reload
---------------------------------------------

.. contents::

POST /virtualbox/**{uuid}**/reload
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Reload a VirtualBox VM instance

Parameters
**********
- **uuid**: VirtualBox VM instance UUID

Response status codes
**********************
- **400**: Invalid VirtualBox VM instance UUID
- **404**: VirtualBox VM instance doesn't exist
- **204**: VirtualBox VM instance reloaded

