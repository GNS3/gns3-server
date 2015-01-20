/vpcs/{uuid}/stop
---------------------------------------------

.. contents::

POST /vpcs/**{uuid}**/stop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a VPCS instance

Parameters
**********
- **uuid**: VPCS instance UUID

Response status codes
**********************
- **400**: Invalid VPCS instance UUID
- **404**: VPCS instance doesn't exist
- **204**: VPCS instance stopped

