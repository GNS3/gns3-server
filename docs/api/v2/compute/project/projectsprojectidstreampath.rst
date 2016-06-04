/v2/compute/projects/{project_id}/stream/{path:.+}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/projects/**{project_id}**/stream/**{path:.+}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stream a file from a project

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **200**: File returned
- **403**: Permission denied
- **404**: The file doesn't exist

