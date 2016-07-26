/v2/compute/projects/{project_id}/iou/nodes/{node_id}/configs/save
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/iou/nodes/**{node_id}**/configs/save
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Save the startup and private configs content

Parameters
**********
- **node_id**: Node UUID
- **project_id**: Project UUID

Response status codes
**********************
- **200**: Configs saved
- **400**: Invalid request
- **404**: Instance doesn't exist

