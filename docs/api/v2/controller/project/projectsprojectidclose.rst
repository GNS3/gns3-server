/v2/projects/{project_id}/close
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/projects/**{project_id}**/close
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Close a project

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **404**: The project doesn't exist
- **204**: The project has been closed

Sample session
***************


.. literalinclude:: ../../../examples/controller_post_projectsprojectidclose.txt

