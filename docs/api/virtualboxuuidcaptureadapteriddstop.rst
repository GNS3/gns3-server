/virtualbox/{uuid}/capture/{adapter_id:\d+}/stop
---------------------------------------------

.. contents::

POST /virtualbox/**{uuid}**/capture/**{adapter_id:\d+}**/stop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a packet capture on a VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID
- **adapter_id**: Adapter to stop a packet capture

Response status codes
**********************
- **400**: Invalid instance UUID
- **404**: Instance doesn't exist
- **204**: Capture stopped

