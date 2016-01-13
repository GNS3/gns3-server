/v1/projects/{project_id}/files
----------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v1/projects/**{project_id}**/files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
List files of a project

Parameters
**********
- **project_id**: The UUID of the project

Response status codes
**********************
- **200**: Return list of files
- **404**: The project doesn't exist

Sample session
***************


.. literalinclude:: ../../examples/get_projectsprojectidfiles.txt

