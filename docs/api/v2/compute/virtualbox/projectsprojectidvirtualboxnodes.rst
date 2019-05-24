/v2/compute/projects/{project_id}/virtualbox/nodes
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/virtualbox/nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new VirtualBox VM instance

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **201**: Instance created
- **400**: Invalid request
- **409**: Conflict

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>adapter_type</td>                    <td> </td>                     <td>string</td>                     <td>VirtualBox adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td> </td>                     <td>integer</td>                     <td>Number of adapters</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, none</td>                     </tr>
    <tr><td>custom_adapters</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>headless</td>                    <td> </td>                     <td>boolean</td>                     <td>Headless mode</td>                     </tr>
    <tr><td>linked_clone</td>                    <td> </td>                     <td>boolean</td>                     <td>Whether the VM is a linked clone or not</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VirtualBox VM instance name</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td></td>                     <td>Node UUID</td>                     </tr>
    <tr><td>on_close</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: power_off, shutdown_signal, save_vm_state</td>                     </tr>
    <tr><td>ram</td>                    <td> </td>                     <td>integer</td>                     <td>Amount of RAM</td>                     </tr>
    <tr><td>usage</td>                    <td> </td>                     <td>string</td>                     <td>How to use the VirtualBox VM</td>                     </tr>
    <tr><td>use_any_adapter</td>                    <td> </td>                     <td>boolean</td>                     <td>Allow GNS3 to use any VirtualBox adapter</td>                     </tr>
    <tr><td>vmname</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VirtualBox VM name (in VirtualBox itself)</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>adapter_type</td>                    <td> </td>                     <td>string</td>                     <td>VirtualBox adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td> </td>                     <td>integer</td>                     <td>Number of adapters</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, none</td>                     </tr>
    <tr><td>custom_adapters</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>headless</td>                    <td> </td>                     <td>boolean</td>                     <td>Headless mode</td>                     </tr>
    <tr><td>linked_clone</td>                    <td> </td>                     <td>boolean</td>                     <td>Whether the VM is a linked clone or not</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>VirtualBox VM instance name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path to the VM working directory</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>on_close</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: power_off, shutdown_signal, save_vm_state</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>ram</td>                    <td> </td>                     <td>integer</td>                     <td>Amount of RAM</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    <tr><td>usage</td>                    <td> </td>                     <td>string</td>                     <td>How to use the VirtualBox VM</td>                     </tr>
    <tr><td>use_any_adapter</td>                    <td> </td>                     <td>boolean</td>                     <td>Allow GNS3 to use any VirtualBox adapter</td>                     </tr>
    <tr><td>vmname</td>                    <td> </td>                     <td>string</td>                     <td>VirtualBox VM name (in VirtualBox itself)</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_post_projectsprojectidvirtualboxnodes.txt

