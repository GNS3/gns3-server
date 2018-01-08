/v2/compute/projects/{project_id}/close
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/close
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Close a project

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **204**: Project closed
- **404**: The project doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/compute_post_projectsprojectidclose.txt

