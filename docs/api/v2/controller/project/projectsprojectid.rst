/v2/projects/{project_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/projects/**{project_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get the project

Parameters
**********
- **project_id**: The UUID of the project

Response status codes
**********************
- **200**: The project exist
- **404**: The project doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/controller_get_projectsprojectid.txt


DELETE /v2/projects/**{project_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a project from disk

Parameters
**********
- **project_id**: The UUID of the project

Response status codes
**********************
- **404**: The project doesn't exist
- **204**: Changes have been written on disk

Sample session
***************


.. literalinclude:: ../../../examples/controller_delete_projectsprojectid.txt

