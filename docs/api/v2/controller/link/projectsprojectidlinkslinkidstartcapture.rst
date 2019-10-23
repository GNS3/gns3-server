/v2/projects/{project_id}/links/{link_id}/start_capture
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/projects/**{project_id}**/links/**{link_id}**/start_capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Start capture on a link instance. By default we consider it as an Ethernet link

Parameters
**********
- **project_id**: Project UUID
- **link_id**: Link UUID

Response status codes
**********************
- **201**: Capture started
- **400**: Invalid request

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>capture_file_name</td>                    <td> </td>                     <td>string</td>                     <td>Read only property. The name of the capture file if capture is running</td>                     </tr>
    <tr><td>data_link_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: DLT_ATM_RFC1483, DLT_EN10MB, DLT_FRELAY, DLT_C_HDLC, DLT_PPP_SERIAL</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>capture_compute_id</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Read only property. The compute identifier where a capture is running</td>                     </tr>
    <tr><td>capture_file_name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Read only property. The name of the capture file if a capture is running</td>                     </tr>
    <tr><td>capture_file_path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Read only property. The full path of the capture file if a capture is running</td>                     </tr>
    <tr><td>capturing</td>                    <td> </td>                     <td>boolean</td>                     <td>Read only property. True if a capture running on the link</td>                     </tr>
    <tr><td>filters</td>                    <td> </td>                     <td>object</td>                     <td>Packet filter. This allow to simulate latency and errors</td>                     </tr>
    <tr><td>link_id</td>                    <td> </td>                     <td>string</td>                     <td>Link UUID</td>                     </tr>
    <tr><td>link_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: ethernet, serial</td>                     </tr>
    <tr><td>nodes</td>                    <td> </td>                     <td>array</td>                     <td>List of the VMS</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>suspend</td>                    <td> </td>                     <td>boolean</td>                     <td>Suspend the link</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/controller_post_projectsprojectidlinkslinkidstartcapture.txt

