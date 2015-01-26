/vpcs/{uuid}/stop
---------------------------------------------

.. contents::

POST /vpcs/**{uuid}**/stop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a VPCS instance

Parameters
**********
- **uuid**: Instance UUID

Response status codes
**********************
- **400**: Invalid VPCS instance UUID
- **404**: Instance doesn't exist
- **204**: Instance stopped

