/vpcs/{uuid}/reload
---------------------------------------------

.. contents::

POST /vpcs/**{uuid}**/reload
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a VPCS

Parameters
**********
- **uuid**: VPCS instance UUID

Response status codes
**********************
- **400**: Invalid VPCS instance UUID
- **404**: VPCS instance doesn't exist
- **204**: VPCS reloaded

