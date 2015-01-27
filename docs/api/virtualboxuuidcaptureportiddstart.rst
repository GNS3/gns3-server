/virtualbox/{uuid}/capture/{port_id:\d+}/start
---------------------------------------------

.. contents::

POST /virtualbox/**{uuid}**/capture/**{port_id:\d+}**/start
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Start a packet capture on a VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID
- **port_id**: ID of the port to start a packet capture

Response status codes
**********************
- **200**: Capture started
- **400**: Invalid instance UUID
- **404**: Instance doesn't exist

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>capture_filename</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Capture file name</td>                     </tr>
    </table>

