/v2/compute/projects/{project_id}/ethernet_hub/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/stop_capture
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/ethernet_hub/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/stop_capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a packet capture on an Ethernet hub instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID
- **adapter_number**: Adapter on the hub (always 0)
- **port_number**: Port on the hub

Response status codes
**********************
- **204**: Capture stopped
- **400**: Invalid request
- **404**: Instance doesn't exist

