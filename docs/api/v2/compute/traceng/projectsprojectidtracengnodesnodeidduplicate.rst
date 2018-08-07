/v2/compute/projects/{project_id}/traceng/nodes/{node_id}/duplicate
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/traceng/nodes/**{node_id}**/duplicate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Duplicate a TraceNG instance

Parameters
**********
- **node_id**: Node UUID
- **project_id**: Project UUID

Response status codes
**********************
- **201**: Instance duplicated
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/compute_post_projectsprojectidtracengnodesnodeidduplicate.txt

