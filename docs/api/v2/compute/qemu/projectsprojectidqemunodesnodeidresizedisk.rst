/v2/compute/projects/{project_id}/qemu/nodes/{node_id}/resize_disk
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/qemu/nodes/**{node_id}**/resize_disk
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Resize a Qemu VM disk image

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **201**: Instance updated
- **404**: Instance doesn't exist

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>drive_name</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: hda, hdb, hdc, hdd</td>                     </tr>
    <tr><td>extend</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Number of Megabytes to extend the image</td>                     </tr>
    </table>

