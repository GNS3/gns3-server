/v2/compute/projects/{project_id}/iou/nodes/{node_id}/start
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/iou/nodes/**{node_id}**/start
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Start an IOU instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **200**: Instance started
- **400**: Invalid request
- **404**: Instance doesn't exist

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>iourc_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the iourc file. Ignored if Null</td>                     </tr>
    <tr><td>license_check</td>                    <td> </td>                     <td>boolean</td>                     <td>Whether the license should be checked</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>application_id</td>                    <td> </td>                     <td>integer</td>                     <td>Application ID for running IOU image</td>                     </tr>
    <tr><td>command_line</td>                    <td> </td>                     <td>string</td>                     <td>Last command line used by GNS3 to start IOU</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, none</td>                     </tr>
    <tr><td>ethernet_adapters</td>                    <td> </td>                     <td>integer</td>                     <td>How many ethernet adapters are connected to the IOU</td>                     </tr>
    <tr><td>l1_keepalives</td>                    <td> </td>                     <td>boolean</td>                     <td>Always up ethernet interface</td>                     </tr>
    <tr><td>md5sum</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Checksum of iou binary</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>IOU VM name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>string</td>                     <td>Path to the node working directory</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>IOU VM UUID</td>                     </tr>
    <tr><td>nvram</td>                    <td> </td>                     <td>integer</td>                     <td>Allocated NVRAM KB</td>                     </tr>
    <tr><td>path</td>                    <td> </td>                     <td>string</td>                     <td>Path of iou binary</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>ram</td>                    <td> </td>                     <td>integer</td>                     <td>Allocated RAM MB</td>                     </tr>
    <tr><td>serial_adapters</td>                    <td> </td>                     <td>integer</td>                     <td>How many serial adapters are connected to the IOU</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    <tr><td>usage</td>                    <td> </td>                     <td>string</td>                     <td>How to use the IOU VM</td>                     </tr>
    <tr><td>use_default_iou_values</td>                    <td> </td>                     <td>['boolean', 'null']</td>                     <td>Use default IOU values</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_post_projectsprojectidiounodesnodeidstart.txt

