/v1/{project_id}/virtualbox/{vm_id}/capture/{adapter_id:\d+}/stop
-----------------------------------------------------------

.. contents::

POST /v1/**{project_id}**/virtualbox/**{vm_id}**/capture/**{adapter_id:\d+}**/stop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a packet capture on a VirtualBox VM instance

Parameters
**********
- **vm_id**: UUID for the instance
- **project_id**: UUID for the project
- **adapter_id**: Adapter to stop a packet capture

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Capture stopped

