/v1/projects/{project_id}/virtualbox/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/virtualbox/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/stop_capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a packet capture on a VirtualBox VM instance

Parameters
**********
- **project_id**: UUID for the project
- **vm_id**: UUID for the instance
- **adapter_number**: Adapter to stop a packet capture
- **port_number**: Port on the adapter (always 0)

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Capture stopped

