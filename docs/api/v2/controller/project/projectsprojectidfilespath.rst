/v2/projects/{project_id}/files/{path:.+}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/projects/**{project_id}**/files/**{path:.+}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a file from a project. Beware you have warranty to be able to access only to file global to the project (for example README.txt)

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **200**: File returned
- **403**: Permission denied
- **404**: The file doesn't exist


POST /v2/projects/**{project_id}**/files/**{path:.+}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Write a file to a project

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **200**: File returned
- **403**: Permission denied
- **404**: The path doesn't exist

