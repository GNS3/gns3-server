/v1/projects/{project_id}/ports/udp
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/ports/udp
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allocate an UDP port on the server

Parameters
**********
- **project_id**: The UUID of the project

Response status codes
**********************
- **201**: UDP port allocated
- **404**: The project doesn't exist

Sample session
***************


.. literalinclude:: ../../examples/post_projectsprojectidportsudp.txt

