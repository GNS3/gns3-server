/v1/projects/{project_id}/dynamips/vms
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/dynamips/vms
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new Dynamips VM instance

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
    <tr><td>aux</td>                    <td> </td>                     <td>integer</td>                     <td>auxiliary console TCP port</td>                     </tr>
    <tr><td>chassis</td>                    <td> </td>                     <td>string</td>                     <td>router chassis model</td>                     </tr>
    <tr><td>clock_divisor</td>                    <td> </td>                     <td>integer</td>                     <td>clock divisor</td>                     </tr>
    <tr><td>confreg</td>                    <td> </td>                     <td>string</td>                     <td>configuration register</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>disk0</td>                    <td> </td>                     <td>integer</td>                     <td>disk0 size in MB</td>                     </tr>
    <tr><td>disk1</td>                    <td> </td>                     <td>integer</td>                     <td>disk1 size in MB</td>                     </tr>
    <tr><td>dynamips_id</td>                    <td> </td>                     <td>integer</td>                     <td>ID to use with Dynamips</td>                     </tr>
    <tr><td>exec_area</td>                    <td> </td>                     <td>integer</td>                     <td>exec area value</td>                     </tr>
    <tr><td>idlemax</td>                    <td> </td>                     <td>integer</td>                     <td>idlemax value</td>                     </tr>
    <tr><td>idlepc</td>                    <td> </td>                     <td>string</td>                     <td>Idle-PC value</td>                     </tr>
    <tr><td>idlesleep</td>                    <td> </td>                     <td>integer</td>                     <td>idlesleep value</td>                     </tr>
    <tr><td>image</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>path to the IOS image</td>                     </tr>
    <tr><td>iomem</td>                    <td> </td>                     <td>integer</td>                     <td>I/O memory percentage</td>                     </tr>
    <tr><td>mac_addr</td>                    <td> </td>                     <td>string</td>                     <td>base MAC address</td>                     </tr>
    <tr><td>midplane</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: std, vxr</td>                     </tr>
    <tr><td>mmap</td>                    <td> </td>                     <td>boolean</td>                     <td>MMAP feature</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Dynamips VM instance name</td>                     </tr>
    <tr><td>npe</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: npe-100, npe-150, npe-175, npe-200, npe-225, npe-300, npe-400, npe-g2</td>                     </tr>
    <tr><td>nvram</td>                    <td> </td>                     <td>integer</td>                     <td>amount of NVRAM in KB</td>                     </tr>
    <tr><td>platform</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>platform</td>                     </tr>
    <tr><td>power_supplies</td>                    <td> </td>                     <td>array</td>                     <td>Power supplies status</td>                     </tr>
    <tr><td>private_config</td>                    <td> </td>                     <td>string</td>                     <td>path to the IOS private configuration file</td>                     </tr>
    <tr><td>private_config_base64</td>                    <td> </td>                     <td>string</td>                     <td>private configuration base64 encoded</td>                     </tr>
    <tr><td>private_config_content</td>                    <td> </td>                     <td>string</td>                     <td>Content of IOS private configuration file</td>                     </tr>
    <tr><td>ram</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>amount of RAM in MB</td>                     </tr>
    <tr><td>sensors</td>                    <td> </td>                     <td>array</td>                     <td>Temperature sensors</td>                     </tr>
    <tr><td>slot0</td>                    <td> </td>                     <td></td>                     <td>Network module slot 0</td>                     </tr>
    <tr><td>slot1</td>                    <td> </td>                     <td></td>                     <td>Network module slot 1</td>                     </tr>
    <tr><td>slot2</td>                    <td> </td>                     <td></td>                     <td>Network module slot 2</td>                     </tr>
    <tr><td>slot3</td>                    <td> </td>                     <td></td>                     <td>Network module slot 3</td>                     </tr>
    <tr><td>slot4</td>                    <td> </td>                     <td></td>                     <td>Network module slot 4</td>                     </tr>
    <tr><td>slot5</td>                    <td> </td>                     <td></td>                     <td>Network module slot 5</td>                     </tr>
    <tr><td>slot6</td>                    <td> </td>                     <td></td>                     <td>Network module slot 6</td>                     </tr>
    <tr><td>sparsemem</td>                    <td> </td>                     <td>boolean</td>                     <td>sparse memory feature</td>                     </tr>
    <tr><td>startup_config</td>                    <td> </td>                     <td>string</td>                     <td>path to the IOS startup configuration file</td>                     </tr>
    <tr><td>startup_config_base64</td>                    <td> </td>                     <td>string</td>                     <td>startup configuration base64 encoded</td>                     </tr>
    <tr><td>startup_config_content</td>                    <td> </td>                     <td>string</td>                     <td>Content of IOS startup configuration file</td>                     </tr>
    <tr><td>system_id</td>                    <td> </td>                     <td>string</td>                     <td>system ID</td>                     </tr>
    <tr><td>vm_id</td>                    <td> </td>                     <td></td>                     <td>Dynamips VM instance identifier</td>                     </tr>
    <tr><td>wic0</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    <tr><td>wic1</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    <tr><td>wic2</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>aux</td>                    <td> </td>                     <td>integer</td>                     <td>auxiliary console TCP port</td>                     </tr>
    <tr><td>chassis</td>                    <td> </td>                     <td>string</td>                     <td>router chassis model</td>                     </tr>
    <tr><td>clock_divisor</td>                    <td> </td>                     <td>integer</td>                     <td>clock divisor</td>                     </tr>
    <tr><td>confreg</td>                    <td> </td>                     <td>string</td>                     <td>configuration register</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>disk0</td>                    <td> </td>                     <td>integer</td>                     <td>disk0 size in MB</td>                     </tr>
    <tr><td>disk1</td>                    <td> </td>                     <td>integer</td>                     <td>disk1 size in MB</td>                     </tr>
    <tr><td>dynamips_id</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>ID to use with Dynamips</td>                     </tr>
    <tr><td>exec_area</td>                    <td> </td>                     <td>integer</td>                     <td>exec area value</td>                     </tr>
    <tr><td>idlemax</td>                    <td> </td>                     <td>integer</td>                     <td>idlemax value</td>                     </tr>
    <tr><td>idlepc</td>                    <td> </td>                     <td>string</td>                     <td>Idle-PC value</td>                     </tr>
    <tr><td>idlesleep</td>                    <td> </td>                     <td>integer</td>                     <td>idlesleep value</td>                     </tr>
    <tr><td>image</td>                    <td> </td>                     <td>string</td>                     <td>path to the IOS image</td>                     </tr>
    <tr><td>iomem</td>                    <td> </td>                     <td>integer</td>                     <td>I/O memory percentage</td>                     </tr>
    <tr><td>mac_addr</td>                    <td> </td>                     <td>string</td>                     <td>base MAC address</td>                     </tr>
    <tr><td>midplane</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: std, vxr</td>                     </tr>
    <tr><td>mmap</td>                    <td> </td>                     <td>boolean</td>                     <td>MMAP feature</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Dynamips VM instance name</td>                     </tr>
    <tr><td>npe</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: npe-100, npe-150, npe-175, npe-200, npe-225, npe-300, npe-400, npe-g2</td>                     </tr>
    <tr><td>nvram</td>                    <td> </td>                     <td>integer</td>                     <td>amount of NVRAM in KB</td>                     </tr>
    <tr><td>platform</td>                    <td> </td>                     <td>string</td>                     <td>platform</td>                     </tr>
    <tr><td>power_supplies</td>                    <td> </td>                     <td>array</td>                     <td>Power supplies status</td>                     </tr>
    <tr><td>private_config</td>                    <td> </td>                     <td>string</td>                     <td>path to the IOS private configuration file</td>                     </tr>
    <tr><td>private_config_base64</td>                    <td> </td>                     <td>string</td>                     <td>private configuration base64 encoded</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>ram</td>                    <td> </td>                     <td>integer</td>                     <td>amount of RAM in MB</td>                     </tr>
    <tr><td>sensors</td>                    <td> </td>                     <td>array</td>                     <td>Temperature sensors</td>                     </tr>
    <tr><td>slot0</td>                    <td> </td>                     <td></td>                     <td>Network module slot 0</td>                     </tr>
    <tr><td>slot1</td>                    <td> </td>                     <td></td>                     <td>Network module slot 1</td>                     </tr>
    <tr><td>slot2</td>                    <td> </td>                     <td></td>                     <td>Network module slot 2</td>                     </tr>
    <tr><td>slot3</td>                    <td> </td>                     <td></td>                     <td>Network module slot 3</td>                     </tr>
    <tr><td>slot4</td>                    <td> </td>                     <td></td>                     <td>Network module slot 4</td>                     </tr>
    <tr><td>slot5</td>                    <td> </td>                     <td></td>                     <td>Network module slot 5</td>                     </tr>
    <tr><td>slot6</td>                    <td> </td>                     <td></td>                     <td>Network module slot 6</td>                     </tr>
    <tr><td>sparsemem</td>                    <td> </td>                     <td>boolean</td>                     <td>sparse memory feature</td>                     </tr>
    <tr><td>startup_config</td>                    <td> </td>                     <td>string</td>                     <td>path to the IOS startup configuration file</td>                     </tr>
    <tr><td>startup_config_base64</td>                    <td> </td>                     <td>string</td>                     <td>startup configuration base64 encoded</td>                     </tr>
    <tr><td>system_id</td>                    <td> </td>                     <td>string</td>                     <td>system ID</td>                     </tr>
    <tr><td>vm_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Dynamips router instance UUID</td>                     </tr>
    <tr><td>wic0</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    <tr><td>wic1</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    <tr><td>wic2</td>                    <td> </td>                     <td></td>                     <td>Network module WIC slot 0</td>                     </tr>
    </table>

