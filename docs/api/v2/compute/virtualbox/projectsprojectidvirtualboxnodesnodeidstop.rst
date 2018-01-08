/v2/compute/projects/{project_id}/virtualbox/nodes/{node_id}/stop
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/virtualbox/nodes/**{node_id}**/stop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a VirtualBox VM instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **204**: Instance stopped
- **400**: Invalid request
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/compute_post_projectsprojectidvirtualboxnodesnodeidstop.txt

