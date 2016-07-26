/v2/compute/projects/{project_id}/iou/nodes/{node_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/projects/**{project_id}**/iou/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get an IOU instance

Parameters
**********
- **node_id**: Node UUID
- **project_id**: Project UUID

Response status codes
**********************
- **200**: Success
- **400**: Invalid request
- **404**: Instance doesn't exist

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>command_line</td>                    <td> </td>                     <td>string</td>                     <td>Last command line used by GNS3 to start QEMU</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>integer</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet</td>                     </tr>
    <tr><td>ethernet_adapters</td>                    <td> </td>                     <td>integer</td>                     <td>How many ethernet adapters are connected to the IOU</td>                     </tr>
    <tr><td>iourc_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the iourc file. Ignored if Null</td>                     </tr>
    <tr><td>iourc_path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path of the iourc file used by remote servers</td>                     </tr>
    <tr><td>l1_keepalives</td>                    <td> </td>                     <td>boolean</td>                     <td>Always up ethernet interface</td>                     </tr>
    <tr><td>md5sum</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Checksum of iou binary</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>IOU VM name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>string</td>                     <td>Path to the node working directory</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>IOU VM UUID</td>                     </tr>
    <tr><td>nvram</td>                    <td> </td>                     <td>integer</td>                     <td>Allocated NVRAM KB</td>                     </tr>
    <tr><td>path</td>                    <td> </td>                     <td>string</td>                     <td>Path of iou binary</td>                     </tr>
    <tr><td>private_config</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path of the private-config content relative to project directory</td>                     </tr>
    <tr><td>private_config_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Private-config of IOU</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>ram</td>                    <td> </td>                     <td>integer</td>                     <td>Allocated RAM MB</td>                     </tr>
    <tr><td>serial_adapters</td>                    <td> </td>                     <td>integer</td>                     <td>How many serial adapters are connected to the IOU</td>                     </tr>
    <tr><td>startup_config</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path of the startup-config content relative to project directory</td>                     </tr>
    <tr><td>startup_config_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Startup-config of IOU</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    <tr><td>use_default_iou_values</td>                    <td> </td>                     <td>['boolean', 'null']</td>                     <td>Use default IOU values</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_get_projectsprojectidiounodesnodeid.txt


PUT /v2/compute/projects/**{project_id}**/iou/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update an IOU instance

Parameters
**********
- **node_id**: Node UUID
- **project_id**: Project UUID

Response status codes
**********************
- **200**: Instance updated
- **400**: Invalid request
- **404**: Instance doesn't exist
- **409**: Conflict

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>command_line</td>                    <td> </td>                     <td>string</td>                     <td>Last command line used by GNS3 to start QEMU</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>integer</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet</td>                     </tr>
    <tr><td>ethernet_adapters</td>                    <td> </td>                     <td>integer</td>                     <td>How many ethernet adapters are connected to the IOU</td>                     </tr>
    <tr><td>iourc_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the iourc file. Ignored if Null</td>                     </tr>
    <tr><td>iourc_path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path of the iourc file used by remote servers</td>                     </tr>
    <tr><td>l1_keepalives</td>                    <td> </td>                     <td>boolean</td>                     <td>Always up ethernet interface</td>                     </tr>
    <tr><td>md5sum</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Checksum of iou binary</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>IOU VM name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>string</td>                     <td>Path to the node working directory</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>IOU VM UUID</td>                     </tr>
    <tr><td>nvram</td>                    <td> </td>                     <td>integer</td>                     <td>Allocated NVRAM KB</td>                     </tr>
    <tr><td>path</td>                    <td> </td>                     <td>string</td>                     <td>Path of iou binary</td>                     </tr>
    <tr><td>private_config</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path of the private-config content relative to project directory</td>                     </tr>
    <tr><td>private_config_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Private-config of IOU</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>ram</td>                    <td> </td>                     <td>integer</td>                     <td>Allocated RAM MB</td>                     </tr>
    <tr><td>serial_adapters</td>                    <td> </td>                     <td>integer</td>                     <td>How many serial adapters are connected to the IOU</td>                     </tr>
    <tr><td>startup_config</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path of the startup-config content relative to project directory</td>                     </tr>
    <tr><td>startup_config_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Startup-config of IOU</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    <tr><td>use_default_iou_values</td>                    <td> </td>                     <td>['boolean', 'null']</td>                     <td>Use default IOU values</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>command_line</td>                    <td> </td>                     <td>string</td>                     <td>Last command line used by GNS3 to start QEMU</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>integer</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet</td>                     </tr>
    <tr><td>ethernet_adapters</td>                    <td> </td>                     <td>integer</td>                     <td>How many ethernet adapters are connected to the IOU</td>                     </tr>
    <tr><td>iourc_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Content of the iourc file. Ignored if Null</td>                     </tr>
    <tr><td>iourc_path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path of the iourc file used by remote servers</td>                     </tr>
    <tr><td>l1_keepalives</td>                    <td> </td>                     <td>boolean</td>                     <td>Always up ethernet interface</td>                     </tr>
    <tr><td>md5sum</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Checksum of iou binary</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>IOU VM name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>string</td>                     <td>Path to the node working directory</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>IOU VM UUID</td>                     </tr>
    <tr><td>nvram</td>                    <td> </td>                     <td>integer</td>                     <td>Allocated NVRAM KB</td>                     </tr>
    <tr><td>path</td>                    <td> </td>                     <td>string</td>                     <td>Path of iou binary</td>                     </tr>
    <tr><td>private_config</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path of the private-config content relative to project directory</td>                     </tr>
    <tr><td>private_config_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Private-config of IOU</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>ram</td>                    <td> </td>                     <td>integer</td>                     <td>Allocated RAM MB</td>                     </tr>
    <tr><td>serial_adapters</td>                    <td> </td>                     <td>integer</td>                     <td>How many serial adapters are connected to the IOU</td>                     </tr>
    <tr><td>startup_config</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path of the startup-config content relative to project directory</td>                     </tr>
    <tr><td>startup_config_content</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Startup-config of IOU</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    <tr><td>use_default_iou_values</td>                    <td> </td>                     <td>['boolean', 'null']</td>                     <td>Use default IOU values</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_put_projectsprojectidiounodesnodeid.txt


DELETE /v2/compute/projects/**{project_id}**/iou/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete an IOU instance

Parameters
**********
- **node_id**: Node UUID
- **project_id**: Project UUID

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Instance deleted

Sample session
***************


.. literalinclude:: ../../../examples/compute_delete_projectsprojectidiounodesnodeid.txt

