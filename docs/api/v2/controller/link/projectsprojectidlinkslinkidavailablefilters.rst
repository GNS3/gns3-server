/v2/projects/{project_id}/links/{link_id}/available_filters
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/projects/**{project_id}**/links/**{link_id}**/available_filters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Return the list of filters available for this link

Parameters
**********
- **project_id**: Project UUID
- **link_id**: Link UUID

Response status codes
**********************
- **200**: List of filters
- **400**: Invalid request

Sample session
***************


.. literalinclude:: ../../../examples/controller_get_projectsprojectidlinkslinkidavailablefilters.txt

