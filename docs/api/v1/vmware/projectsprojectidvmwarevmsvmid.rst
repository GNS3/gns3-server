/v1/projects/{project_id}/vmware/vms/{vm_id}
----------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v1/projects/**{project_id}**/vmware/vms/**{vm_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a VMware VM instance

Parameters
**********
- **project_id**: UUID for the project
- **vm_id**: UUID for the instance

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
    <tr><td>acpi_shutdown</td>                    <td> </td>                     <td>boolean</td>                     <td>ACPI shutdown</td>                     </tr>
    <tr><td>adapter_type</td>                    <td> </td>                     <td>string</td>                     <td>VMware adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td> </td>                     <td>integer</td>                     <td>number of adapters</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>enable_remote_console</td>                    <td> </td>                     <td>boolean</td>                     <td>enable the remote console</td>                     </tr>
    <tr><td>headless</td>                    <td> </td>                     <td>boolean</td>                     <td>headless mode</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VMware VM instance name</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>use_any_adapter</td>                    <td> </td>                     <td>boolean</td>                     <td>allow GNS3 to use any VMware adapter</td>                     </tr>
    <tr><td>vm_directory</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td></td>                     </tr>
    <tr><td>vm_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VMware VM instance UUID</td>                     </tr>
    <tr><td>vmx_path</td>                    <td> </td>                     <td>string</td>                     <td>path to the vmx file</td>                     </tr>
    </table>


PUT /v1/projects/**{project_id}**/vmware/vms/**{vm_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a VMware VM instance

Parameters
**********
- **project_id**: UUID for the project
- **vm_id**: UUID for the instance

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
    <tr><td>acpi_shutdown</td>                    <td> </td>                     <td>boolean</td>                     <td>ACPI shutdown</td>                     </tr>
    <tr><td>adapter_type</td>                    <td> </td>                     <td>string</td>                     <td>VMware adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td> </td>                     <td>integer</td>                     <td>number of adapters</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>enable_remote_console</td>                    <td> </td>                     <td>boolean</td>                     <td>enable the remote console</td>                     </tr>
    <tr><td>headless</td>                    <td> </td>                     <td>boolean</td>                     <td>headless mode</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>VMware VM instance name</td>                     </tr>
    <tr><td>use_any_adapter</td>                    <td> </td>                     <td>boolean</td>                     <td>allow GNS3 to use any VMware adapter</td>                     </tr>
    <tr><td>vmx_path</td>                    <td> </td>                     <td>string</td>                     <td>path to the vmx file</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>acpi_shutdown</td>                    <td> </td>                     <td>boolean</td>                     <td>ACPI shutdown</td>                     </tr>
    <tr><td>adapter_type</td>                    <td> </td>                     <td>string</td>                     <td>VMware adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td> </td>                     <td>integer</td>                     <td>number of adapters</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>enable_remote_console</td>                    <td> </td>                     <td>boolean</td>                     <td>enable the remote console</td>                     </tr>
    <tr><td>headless</td>                    <td> </td>                     <td>boolean</td>                     <td>headless mode</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VMware VM instance name</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>use_any_adapter</td>                    <td> </td>                     <td>boolean</td>                     <td>allow GNS3 to use any VMware adapter</td>                     </tr>
    <tr><td>vm_directory</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td></td>                     </tr>
    <tr><td>vm_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VMware VM instance UUID</td>                     </tr>
    <tr><td>vmx_path</td>                    <td> </td>                     <td>string</td>                     <td>path to the vmx file</td>                     </tr>
    </table>


DELETE /v1/projects/**{project_id}**/vmware/vms/**{vm_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a VMware VM instance

Parameters
**********
- **project_id**: UUID for the project
- **vm_id**: UUID for the instance

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Instance deleted

