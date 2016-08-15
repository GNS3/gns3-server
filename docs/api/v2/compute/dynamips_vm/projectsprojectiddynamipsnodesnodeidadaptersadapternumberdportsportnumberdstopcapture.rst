/v2/compute/projects/{project_id}/dynamips/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/dynamips/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/stop_capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a packet capture on a Dynamips VM instance

Parameters
**********
- **adapter_number**: Adapter to stop a packet capture
- **port_number**: Port on the adapter (always 0)
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Capture stopped

