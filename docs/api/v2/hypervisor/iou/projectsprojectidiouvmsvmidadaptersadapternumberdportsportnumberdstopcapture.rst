/v2/hypervisor/projects/{project_id}/iou/vms/{vm_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/hypervisor/projects/**{project_id}**/iou/vms/**{vm_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/stop_capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a packet capture on a IOU VM instance

Parameters
**********
- **vm_id**: UUID for the instance
- **adapter_number**: Adapter to stop a packet capture
- **port_number**: Port on the adapter (always 0)
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Capture stopped
- **409**: VM not started

Sample session
***************


.. literalinclude:: ../../../examples/hypervisor_post_projectsprojectidiouvmsvmidadaptersadapternumberdportsportnumberdstopcapture.txt

