/virtualbox/{uuid}/capture/{port_id:\d+}/stop
---------------------------------------------

.. contents::

POST /virtualbox/**{uuid}**/capture/**{port_id:\d+}**/stop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a packet capture on a VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID
- **port_id**: ID of the port to stop a packet capture

Response status codes
**********************
- **400**: Invalid instance UUID
- **404**: Instance doesn't exist
- **204**: Capture stopped

