/v1/projects/{project_id}/dynamips/devices/{device_id}/ports/{port_number:\d+}/start_capture
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/dynamips/devices/**{device_id}**/ports/**{port_number:\d+}**/start_capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Start a packet capture on a Dynamips device instance

Parameters
**********
- **project_id**: UUID for the project
- **device_id**: UUID for the instance
- **port_number**: Port on the device

Response status codes
**********************
- **200**: Capture started
- **400**: Invalid request
- **404**: Instance doesn't exist

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>capture_file_name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Capture file name</td>                     </tr>
    <tr><td>data_link_type</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>PCAP data link type</td>                     </tr>
    </table>

