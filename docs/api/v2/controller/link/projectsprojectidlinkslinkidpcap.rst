/v2/projects/{project_id}/links/{link_id}/pcap
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/projects/**{project_id}**/links/**{link_id}**/pcap
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Steam the pcap capture file

Parameters
**********
- **link_id**: Link UUID
- **project_id**: Project UUID

Response status codes
**********************
- **200**: File returned
- **403**: Permission denied
- **404**: The file doesn't exist

