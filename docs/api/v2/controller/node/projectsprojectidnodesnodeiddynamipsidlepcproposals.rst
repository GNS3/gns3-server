/v2/projects/{project_id}/nodes/{node_id}/dynamips/idlepc_proposals
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/projects/**{project_id}**/nodes/**{node_id}**/dynamips/idlepc_proposals
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Compute a list of potential idle PC for a node

Parameters
**********
- **node_id**: Node UUID
- **project_id**: Project UUID

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Instance reloaded

Sample session
***************


.. literalinclude:: ../../../examples/controller_get_projectsprojectidnodesnodeiddynamipsidlepcproposals.txt

