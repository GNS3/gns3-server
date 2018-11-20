/v2/projects/{project_id}/nodes/{node_id}/resize_disk
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/projects/**{project_id}**/nodes/**{node_id}**/resize_disk
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Reload a node instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **201**: Disk image resized
- **400**: Invalid request
- **404**: Instance doesn't exist

