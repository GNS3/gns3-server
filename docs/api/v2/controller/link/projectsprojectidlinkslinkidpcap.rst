/v2/projects/{project_id}/links/{link_id}/pcap
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/projects/**{project_id}**/links/**{link_id}**/pcap
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stream the PCAP capture file from compute

Parameters
**********
- **project_id**: Project UUID
- **link_id**: Link UUID

Response status codes
**********************
- **200**: File returned
- **403**: Permission denied
- **404**: The file doesn't exist

