/v1/projects/{project_id}/files/{path:.+}
----------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v1/projects/**{project_id}**/files/**{path:.+}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a file of a project

Parameters
**********
- **project_id**: The UUID of the project

Response status codes
**********************
- **200**: Return the file
- **403**: Permission denied
- **404**: The file doesn't exist

