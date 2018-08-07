/v2/projects/{project_id}/nodes/{node_id}/links
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/projects/**{project_id}**/nodes/**{node_id}**/links
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Return all the links connected to this node

Parameters
**********
- **node_id**: Node UUID
- **project_id**: Project UUID

Response status codes
**********************
- **200**: Links returned
- **400**: Invalid request
- **404**: Instance doesn't exist

