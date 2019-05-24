/v2/compute/projects/{project_id}/vpcs/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/pcap
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/projects/**{project_id}**/vpcs/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/pcap
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stream the pcap capture file

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID
- **adapter_number**: Adapter to steam a packet capture
- **port_number**: Port on the adapter

Response status codes
**********************
- **200**: File returned
- **403**: Permission denied
- **404**: The file doesn't exist

