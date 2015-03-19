/v1/projects/{project_id}/close
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/close
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Close a project

Parameters
**********
- **project_id**: The UUID of the project

Response status codes
**********************
- **404**: The project doesn't exist
- **204**: The project has been closed

Sample session
***************


.. literalinclude:: ../../examples/post_projectsprojectidclose.txt

