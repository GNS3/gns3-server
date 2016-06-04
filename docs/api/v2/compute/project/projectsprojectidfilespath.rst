/v2/compute/projects/{project_id}/files/{path:.+}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/projects/**{project_id}**/files/**{path:.+}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a file from a project

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **200**: File returned
- **403**: Permission denied
- **404**: The file doesn't exist


POST /v2/compute/projects/**{project_id}**/files/**{path:.+}**
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

