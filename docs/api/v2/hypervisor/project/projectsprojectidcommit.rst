/v2/hypervisor/projects/{project_id}/commit
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/hypervisor/projects/**{project_id}**/commit
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Write changes on disk

Parameters
**********
- **project_id**: The UUID of the project

Response status codes
**********************
- **404**: The project doesn't exist
- **204**: Changes have been written on disk

Sample session
***************


.. literalinclude:: ../../../examples/hypervisor_post_projectsprojectidcommit.txt

