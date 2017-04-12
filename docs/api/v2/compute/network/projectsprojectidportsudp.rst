/v2/compute/projects/{project_id}/ports/udp
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/ports/udp
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allocate an UDP port on the server

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **201**: UDP port allocated
- **404**: The project doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/compute_post_projectsprojectidportsudp.txt

