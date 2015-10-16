/v1/projects/{project_id}/docker/images/{id}
----------------------------------------------------------------------------------------------------------------------

.. contents::

DELETE /v1/projects/**{project_id}**/docker/images/**{id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a Docker container

Parameters
**********
- **id**: ID for the container
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Instance deleted

