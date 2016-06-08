/v2/compute/projects/{project_id}/vpcs/nodes/{node_id}/stop
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/vpcs/nodes/**{node_id}**/stop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a VPCS instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Instance stopped

Sample session
***************


.. literalinclude:: ../../../examples/compute_post_projectsprojectidvpcsnodesnodeidstop.txt

