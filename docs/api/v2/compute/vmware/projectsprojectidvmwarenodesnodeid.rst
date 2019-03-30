/v2/compute/projects/{project_id}/vmware/nodes/{node_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/projects/**{project_id}**/vmware/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a VMware VM instance

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
    <tr><td>adapter_type</td>                    <td> </td>                     <td>string</td>                     <td>VMware adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td> </td>                     <td>integer</td>                     <td>Number of adapters</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, none</td>                     </tr>
    <tr><td>custom_adapters</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>headless</td>                    <td> </td>                     <td>boolean</td>                     <td>Headless mode</td>                     </tr>
    <tr><td>linked_clone</td>                    <td> </td>                     <td>boolean</td>                     <td>Whether the VM is a linked clone or not</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>VMware VM instance name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path to the node working directory</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>on_close</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: power_off, shutdown_signal, save_vm_state</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    <tr><td>usage</td>                    <td> </td>                     <td>string</td>                     <td>How to use the VMware VM</td>                     </tr>
    <tr><td>use_any_adapter</td>                    <td> </td>                     <td>boolean</td>                     <td>Allow GNS3 to use any VMware adapter</td>                     </tr>
    <tr><td>vmx_path</td>                    <td> </td>                     <td>string</td>                     <td>Path to the vmx file</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_get_projectsprojectidvmwarenodesnodeid.txt


PUT /v2/compute/projects/**{project_id}**/vmware/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a VMware VM instance

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
    <tr><td>adapter_type</td>                    <td> </td>                     <td>string</td>                     <td>VMware adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td> </td>                     <td>integer</td>                     <td>Number of adapters</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, none</td>                     </tr>
    <tr><td>custom_adapters</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>headless</td>                    <td> </td>                     <td>boolean</td>                     <td>Headless mode</td>                     </tr>
    <tr><td>linked_clone</td>                    <td> </td>                     <td>boolean</td>                     <td>Whether the VM is a linked clone or not</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>VMware VM instance name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path to the node working directory</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>on_close</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: power_off, shutdown_signal, save_vm_state</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    <tr><td>usage</td>                    <td> </td>                     <td>string</td>                     <td>How to use the VMware VM</td>                     </tr>
    <tr><td>use_any_adapter</td>                    <td> </td>                     <td>boolean</td>                     <td>Allow GNS3 to use any VMware adapter</td>                     </tr>
    <tr><td>vmx_path</td>                    <td> </td>                     <td>string</td>                     <td>Path to the vmx file</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>adapter_type</td>                    <td> </td>                     <td>string</td>                     <td>VMware adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td> </td>                     <td>integer</td>                     <td>Number of adapters</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, none</td>                     </tr>
    <tr><td>custom_adapters</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>headless</td>                    <td> </td>                     <td>boolean</td>                     <td>Headless mode</td>                     </tr>
    <tr><td>linked_clone</td>                    <td> </td>                     <td>boolean</td>                     <td>Whether the VM is a linked clone or not</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>VMware VM instance name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path to the node working directory</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>on_close</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: power_off, shutdown_signal, save_vm_state</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    <tr><td>usage</td>                    <td> </td>                     <td>string</td>                     <td>How to use the VMware VM</td>                     </tr>
    <tr><td>use_any_adapter</td>                    <td> </td>                     <td>boolean</td>                     <td>Allow GNS3 to use any VMware adapter</td>                     </tr>
    <tr><td>vmx_path</td>                    <td> </td>                     <td>string</td>                     <td>Path to the vmx file</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_put_projectsprojectidvmwarenodesnodeid.txt


DELETE /v2/compute/projects/**{project_id}**/vmware/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a VMware VM instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **204**: Instance deleted
- **400**: Invalid request
- **404**: Instance doesn't exist

