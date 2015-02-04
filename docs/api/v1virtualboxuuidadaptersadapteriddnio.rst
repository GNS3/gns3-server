/v1/virtualbox/{uuid}/adapters/{adapter_id:\d+}/nio
-----------------------------------------------------------

.. contents::

POST /v1/virtualbox/**{uuid}**/adapters/**{adapter_id:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID
- **adapter_id**: Adapter where the nio should be added

Response status codes
**********************
- **400**: Invalid instance UUID
- **201**: NIO created
- **404**: Instance doesn't exist


DELETE /v1/virtualbox/**{uuid}**/adapters/**{adapter_id:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID
- **adapter_id**: Adapter from where the nio should be removed

Response status codes
**********************
- **400**: Invalid instance UUID
- **404**: Instance doesn't exist
- **204**: NIO deleted

