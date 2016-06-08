/v2/compute/projects/{project_id}/qemu/nodes/{node_id}/resume
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/qemu/nodes/**{node_id}**/resume
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Resume a Qemu VM instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Instance resumed

Sample session
***************


.. literalinclude:: ../../../examples/compute_post_projectsprojectidqemunodesnodeidresume.txt

