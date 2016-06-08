/v2/compute/projects/{project_id}/dynamips/nodes/{node_id}/configs/save
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/dynamips/nodes/**{node_id}**/configs/save
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Save the startup and private configs content

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **200**: Configs saved
- **400**: Invalid request
- **404**: Instance doesn't exist

