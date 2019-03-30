/v2/compute/projects/{project_id}/dynamips/nodes/{node_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/projects/**{project_id}**/dynamips/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a Dynamips VM instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

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
    <tr><td>auto_delete_disks</td>                    <td> </td>                     <td>boolean</td>                     <td>Automatically delete nvram and disk files</td>                     </tr>
    <tr><td>aux</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Auxiliary console TCP port</td>                     </tr>
    <tr><td>chassis</td>                    <td> </td>                     <td>string</td>                     <td>Cisco router chassis model</td>                     </tr>
    <tr><td>clock_divisor</td>                    <td> </td>                     <td>integer</td>                     <td>Clock divisor</td>                     </tr>
    <tr><td>console</td>                    <td>&#10004;</td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: telnet, none</td>                     </tr>
    <tr><td>disk0</td>                    <td> </td>                     <td>integer</td>                     <td>Disk0 size in MB</td>                     </tr>
    <tr><td>disk1</td>                    <td> </td>                     <td>integer</td>                     <td>Disk1 size in MB</td>                     </tr>
    <tr><td>dynamips_id</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>ID to use with Dynamips</td>                     </tr>
    <tr><td>exec_area</td>                    <td> </td>                     <td>integer</td>                     <td>Exec area value</td>                     </tr>
    <tr><td>idlemax</td>                    <td> </td>                     <td>integer</td>                     <td>Idlemax value</td>                     </tr>
    <tr><td>idlepc</td>                    <td> </td>                     <td>string</td>                     <td>Idle-PC value</td>                     </tr>
    <tr><td>idlesleep</td>                    <td> </td>                     <td>integer</td>                     <td>Idlesleep value</td>                     </tr>
    <tr><td>image</td>                    <td> </td>                     <td>string</td>                     <td>Path to the IOS image</td>                     </tr>
    <tr><td>image_md5sum</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Checksum of the IOS image</td>                     </tr>
    <tr><td>iomem</td>                    <td> </td>                     <td>integer</td>                     <td>I/O memory percentage</td>                     </tr>
    <tr><td>mac_addr</td>                    <td> </td>                     <td>['null', 'string']</td>                     <td>Base MAC address</td>                     </tr>
    <tr><td>midplane</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: std, vxr</td>                     </tr>
    <tr><td>mmap</td>                    <td> </td>                     <td>boolean</td>                     <td>MMAP feature</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Dynamips VM instance name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>string</td>                     <td>Path to the vm working directory</td>                     </tr>
    <tr><td>node_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>npe</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: npe-100, npe-150, npe-175, npe-200, npe-225, npe-300, npe-400, npe-g2</td>                     </tr>
    <tr><td>nvram</td>                    <td> </td>                     <td>integer</td>                     <td>Amount of NVRAM in KB</td>                     </tr>
    <tr><td>platform</td>                    <td> </td>                     <td>string</td>                     <td>Cisco router platform</td>                     </tr>
    <tr><td>power_supplies</td>                    <td> </td>                     <td>array</td>                     <td>Power supplies status</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>ram</td>                    <td> </td>                     <td>integer</td>                     <td>Amount of RAM in MB</td>                     </tr>
    <tr><td>sensors</td>                    <td> </td>                     <td>array</td>                     <td>Temperature sensors</td>                     </tr>
    <tr><td>slot0</td>                    <td> </td>                     <td></td>                     <td>Network module slot 0</td>                     </tr>
    <tr><td>slot1</td>                    <td> </td>                     <td></td>                     <td>Network module slot 1</td>                     </tr>
    <tr><td>slot2</td>                    <td> </td>                     <td></td>                     <td>Network module slot 2</td>                     </tr>
    <tr><td>slot3</td>                    <td> </td>                     <td></td>                     <td>Network module slot 3</td>                     </tr>
    <tr><td>slot4</td>                    <td> </td>                     <td></td>                     <td>Network module slot 4</td>                     </tr>
    <tr><td>slot5</td>                    <td> </td>                     <td></td>                     <td>Network module slot 5</td>                     </tr>
    <tr><td>slot6</td>                    <td> </td>                     <td></td>                     <td>Network module slot 6</td>                     </tr>
    <tr><td>sparsemem</td>                    <td> </td>                     <td>boolean</td>                     <td>Sparse memory feature</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    <tr><td>system_id</td>                    <td> </td>                     <td>string</td>                     <td>System ID</td>                     </tr>
    <tr><td>usage</td>                    <td> </td>                     <td>string</td>                     <td>How to use the Dynamips VM</td>                     </tr>
    <tr><td>wic0</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    <tr><td>wic1</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    <tr><td>wic2</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    </table>


PUT /v2/compute/projects/**{project_id}**/dynamips/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a Dynamips VM instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

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
    <tr><td>auto_delete_disks</td>                    <td> </td>                     <td>boolean</td>                     <td>Automatically delete nvram and disk files</td>                     </tr>
    <tr><td>aux</td>                    <td> </td>                     <td>integer</td>                     <td>Auxiliary console TCP port</td>                     </tr>
    <tr><td>chassis</td>                    <td> </td>                     <td>string</td>                     <td>Cisco router chassis model</td>                     </tr>
    <tr><td>clock_divisor</td>                    <td> </td>                     <td>integer</td>                     <td>Clock divisor</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, none</td>                     </tr>
    <tr><td>disk0</td>                    <td> </td>                     <td>integer</td>                     <td>Disk0 size in MB</td>                     </tr>
    <tr><td>disk1</td>                    <td> </td>                     <td>integer</td>                     <td>Disk1 size in MB</td>                     </tr>
    <tr><td>dynamips_id</td>                    <td> </td>                     <td>integer</td>                     <td>Dynamips ID</td>                     </tr>
    <tr><td>exec_area</td>                    <td> </td>                     <td>integer</td>                     <td>Exec area value</td>                     </tr>
    <tr><td>idlemax</td>                    <td> </td>                     <td>integer</td>                     <td>Idlemax value</td>                     </tr>
    <tr><td>idlepc</td>                    <td> </td>                     <td>string</td>                     <td>Idle-PC value</td>                     </tr>
    <tr><td>idlesleep</td>                    <td> </td>                     <td>integer</td>                     <td>Idlesleep value</td>                     </tr>
    <tr><td>image</td>                    <td> </td>                     <td>string</td>                     <td>Path to the IOS image</td>                     </tr>
    <tr><td>image_md5sum</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Checksum of the IOS image</td>                     </tr>
    <tr><td>iomem</td>                    <td> </td>                     <td>integer</td>                     <td>I/O memory percentage</td>                     </tr>
    <tr><td>mac_addr</td>                    <td> </td>                     <td>['null', 'string']</td>                     <td>Base MAC address</td>                     </tr>
    <tr><td>midplane</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: std, vxr</td>                     </tr>
    <tr><td>mmap</td>                    <td> </td>                     <td>boolean</td>                     <td>MMAP feature</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Dynamips VM instance name</td>                     </tr>
    <tr><td>npe</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: npe-100, npe-150, npe-175, npe-200, npe-225, npe-300, npe-400, npe-g2</td>                     </tr>
    <tr><td>nvram</td>                    <td> </td>                     <td>integer</td>                     <td>Amount of NVRAM in KB</td>                     </tr>
    <tr><td>platform</td>                    <td> </td>                     <td>string</td>                     <td>Cisco router platform</td>                     </tr>
    <tr><td>power_supplies</td>                    <td> </td>                     <td>array</td>                     <td>Power supplies status</td>                     </tr>
    <tr><td>ram</td>                    <td> </td>                     <td>integer</td>                     <td>Amount of RAM in MB</td>                     </tr>
    <tr><td>sensors</td>                    <td> </td>                     <td>array</td>                     <td>Temperature sensors</td>                     </tr>
    <tr><td>slot0</td>                    <td> </td>                     <td></td>                     <td>Network module slot 0</td>                     </tr>
    <tr><td>slot1</td>                    <td> </td>                     <td></td>                     <td>Network module slot 1</td>                     </tr>
    <tr><td>slot2</td>                    <td> </td>                     <td></td>                     <td>Network module slot 2</td>                     </tr>
    <tr><td>slot3</td>                    <td> </td>                     <td></td>                     <td>Network module slot 3</td>                     </tr>
    <tr><td>slot4</td>                    <td> </td>                     <td></td>                     <td>Network module slot 4</td>                     </tr>
    <tr><td>slot5</td>                    <td> </td>                     <td></td>                     <td>Network module slot 5</td>                     </tr>
    <tr><td>slot6</td>                    <td> </td>                     <td></td>                     <td>Network module slot 6</td>                     </tr>
    <tr><td>sparsemem</td>                    <td> </td>                     <td>boolean</td>                     <td>Sparse memory feature</td>                     </tr>
    <tr><td>system_id</td>                    <td> </td>                     <td>string</td>                     <td>System ID</td>                     </tr>
    <tr><td>usage</td>                    <td> </td>                     <td>string</td>                     <td>How to use the Dynamips VM</td>                     </tr>
    <tr><td>wic0</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    <tr><td>wic1</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    <tr><td>wic2</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>auto_delete_disks</td>                    <td> </td>                     <td>boolean</td>                     <td>Automatically delete nvram and disk files</td>                     </tr>
    <tr><td>aux</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Auxiliary console TCP port</td>                     </tr>
    <tr><td>chassis</td>                    <td> </td>                     <td>string</td>                     <td>Cisco router chassis model</td>                     </tr>
    <tr><td>clock_divisor</td>                    <td> </td>                     <td>integer</td>                     <td>Clock divisor</td>                     </tr>
    <tr><td>console</td>                    <td>&#10004;</td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: telnet, none</td>                     </tr>
    <tr><td>disk0</td>                    <td> </td>                     <td>integer</td>                     <td>Disk0 size in MB</td>                     </tr>
    <tr><td>disk1</td>                    <td> </td>                     <td>integer</td>                     <td>Disk1 size in MB</td>                     </tr>
    <tr><td>dynamips_id</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>ID to use with Dynamips</td>                     </tr>
    <tr><td>exec_area</td>                    <td> </td>                     <td>integer</td>                     <td>Exec area value</td>                     </tr>
    <tr><td>idlemax</td>                    <td> </td>                     <td>integer</td>                     <td>Idlemax value</td>                     </tr>
    <tr><td>idlepc</td>                    <td> </td>                     <td>string</td>                     <td>Idle-PC value</td>                     </tr>
    <tr><td>idlesleep</td>                    <td> </td>                     <td>integer</td>                     <td>Idlesleep value</td>                     </tr>
    <tr><td>image</td>                    <td> </td>                     <td>string</td>                     <td>Path to the IOS image</td>                     </tr>
    <tr><td>image_md5sum</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Checksum of the IOS image</td>                     </tr>
    <tr><td>iomem</td>                    <td> </td>                     <td>integer</td>                     <td>I/O memory percentage</td>                     </tr>
    <tr><td>mac_addr</td>                    <td> </td>                     <td>['null', 'string']</td>                     <td>Base MAC address</td>                     </tr>
    <tr><td>midplane</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: std, vxr</td>                     </tr>
    <tr><td>mmap</td>                    <td> </td>                     <td>boolean</td>                     <td>MMAP feature</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Dynamips VM instance name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>string</td>                     <td>Path to the vm working directory</td>                     </tr>
    <tr><td>node_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>npe</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: npe-100, npe-150, npe-175, npe-200, npe-225, npe-300, npe-400, npe-g2</td>                     </tr>
    <tr><td>nvram</td>                    <td> </td>                     <td>integer</td>                     <td>Amount of NVRAM in KB</td>                     </tr>
    <tr><td>platform</td>                    <td> </td>                     <td>string</td>                     <td>Cisco router platform</td>                     </tr>
    <tr><td>power_supplies</td>                    <td> </td>                     <td>array</td>                     <td>Power supplies status</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>ram</td>                    <td> </td>                     <td>integer</td>                     <td>Amount of RAM in MB</td>                     </tr>
    <tr><td>sensors</td>                    <td> </td>                     <td>array</td>                     <td>Temperature sensors</td>                     </tr>
    <tr><td>slot0</td>                    <td> </td>                     <td></td>                     <td>Network module slot 0</td>                     </tr>
    <tr><td>slot1</td>                    <td> </td>                     <td></td>                     <td>Network module slot 1</td>                     </tr>
    <tr><td>slot2</td>                    <td> </td>                     <td></td>                     <td>Network module slot 2</td>                     </tr>
    <tr><td>slot3</td>                    <td> </td>                     <td></td>                     <td>Network module slot 3</td>                     </tr>
    <tr><td>slot4</td>                    <td> </td>                     <td></td>                     <td>Network module slot 4</td>                     </tr>
    <tr><td>slot5</td>                    <td> </td>                     <td></td>                     <td>Network module slot 5</td>                     </tr>
    <tr><td>slot6</td>                    <td> </td>                     <td></td>                     <td>Network module slot 6</td>                     </tr>
    <tr><td>sparsemem</td>                    <td> </td>                     <td>boolean</td>                     <td>Sparse memory feature</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    <tr><td>system_id</td>                    <td> </td>                     <td>string</td>                     <td>System ID</td>                     </tr>
    <tr><td>usage</td>                    <td> </td>                     <td>string</td>                     <td>How to use the Dynamips VM</td>                     </tr>
    <tr><td>wic0</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    <tr><td>wic1</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    <tr><td>wic2</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    </table>


DELETE /v2/compute/projects/**{project_id}**/dynamips/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a Dynamips VM instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **204**: Instance deleted
- **400**: Invalid request
- **404**: Instance doesn't exist

