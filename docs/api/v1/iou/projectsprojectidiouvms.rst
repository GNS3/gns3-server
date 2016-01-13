/v1/projects/{project_id}/iou/vms
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/iou/vms
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new IOU instance

Parameters
**********
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **201**: Instance created
- **409**: Conflict

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>ethernet_adapters</td>                    <td> </td>                     <td>integer</td>                     <td>How many ethernet adapters are connected to the IOU</td>                     </tr>
    <tr><td>iourc_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the iourc file. Ignored if Null</td>                     </tr>
    <tr><td>l1_keepalives</td>                    <td> </td>                     <td>['boolean', 'null']</td>                     <td>Always up ethernet interface</td>                     </tr>
    <tr><td>md5sum</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Checksum of iou binary</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>IOU VM name</td>                     </tr>
    <tr><td>nvram</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Allocated NVRAM KB</td>                     </tr>
    <tr><td>path</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Path of iou binary</td>                     </tr>
    <tr><td>private_config</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path to the private-config of IOU</td>                     </tr>
    <tr><td>private_config_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Private-config of IOU</td>                     </tr>
    <tr><td>ram</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Allocated RAM MB</td>                     </tr>
    <tr><td>serial_adapters</td>                    <td> </td>                     <td>integer</td>                     <td>How many serial adapters are connected to the IOU</td>                     </tr>
    <tr><td>startup_config</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path to the startup-config of IOU</td>                     </tr>
    <tr><td>startup_config_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Startup-config of IOU</td>                     </tr>
    <tr><td>use_default_iou_values</td>                    <td> </td>                     <td>['boolean', 'null']</td>                     <td>Use default IOU values</td>                     </tr>
    <tr><td>vm_id</td>                    <td> </td>                     <td></td>                     <td>IOU VM identifier</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>console</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>ethernet_adapters</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>How many ethernet adapters are connected to the IOU</td>                     </tr>
    <tr><td>iourc_path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path of the iourc file used by remote servers</td>                     </tr>
    <tr><td>l1_keepalives</td>                    <td>&#10004;</td>                     <td>boolean</td>                     <td>Always up ethernet interface</td>                     </tr>
    <tr><td>md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>Checksum of iou binary</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>IOU VM name</td>                     </tr>
    <tr><td>nvram</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Allocated NVRAM KB</td>                     </tr>
    <tr><td>path</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Path of iou binary</td>                     </tr>
    <tr><td>private_config</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>Path of the private-config content relative to project directory</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>ram</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Allocated RAM MB</td>                     </tr>
    <tr><td>serial_adapters</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>How many serial adapters are connected to the IOU</td>                     </tr>
    <tr><td>startup_config</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>Path of the startup-config content relative to project directory</td>                     </tr>
    <tr><td>use_default_iou_values</td>                    <td>&#10004;</td>                     <td>['boolean', 'null']</td>                     <td>Use default IOU values</td>                     </tr>
    <tr><td>vm_directory</td>                    <td> </td>                     <td>string</td>                     <td></td>                     </tr>
    <tr><td>vm_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>IOU VM UUID</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../examples/post_projectsprojectidiouvms.txt

