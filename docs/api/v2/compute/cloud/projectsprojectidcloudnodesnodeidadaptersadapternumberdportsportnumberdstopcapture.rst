/v2/compute/projects/{project_id}/cloud/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/cloud/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/stop_capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a packet capture on a cloud instance

Parameters
**********
- **adapter_number**: Adapter on the cloud (always 0)
- **port_number**: Port on the cloud
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Capture stopped

