/v2/projects/{project_id}/links/{link_id}/stop_capture
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/projects/**{project_id}**/links/**{link_id}**/stop_capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop capture on a link instance

Parameters
**********
- **project_id**: Project UUID
- **link_id**: Link UUID

Response status codes
**********************
- **400**: Invalid request
- **201**: Capture stopped

Sample session
***************


.. literalinclude:: ../../../examples/controller_post_projectsprojectidlinkslinkidstopcapture.txt

