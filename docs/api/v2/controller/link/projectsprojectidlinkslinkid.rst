/v2/projects/{project_id}/links/{link_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

DELETE /v2/projects/**{project_id}**/links/**{link_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a link instance

Parameters
**********
- **link_id**: UUID of the link
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **204**: Link deleted

Sample session
***************


.. literalinclude:: ../../../examples/controller_delete_projectsprojectidlinkslinkid.txt

