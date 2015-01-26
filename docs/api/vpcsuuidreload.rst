/vpcs/{uuid}/reload
---------------------------------------------

.. contents::

POST /vpcs/**{uuid}**/reload
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Reload a VPCS instance

Parameters
**********
- **uuid**: Instance UUID

Response status codes
**********************
- **400**: Invalid instance UUID
- **404**: Instance doesn't exist
- **204**: Instance reloaded

