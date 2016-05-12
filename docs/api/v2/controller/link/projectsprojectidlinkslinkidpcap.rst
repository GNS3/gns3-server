/v2/projects/{project_id}/links/{link_id}/pcap
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/projects/**{project_id}**/links/**{link_id}**/pcap
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get the pcap from the capture

Parameters
**********
- **link_id**: UUID of the link
- **project_id**: UUID for the project

Response status codes
**********************
- **200**: Return the file
- **403**: Permission denied
- **404**: The file doesn't exist

