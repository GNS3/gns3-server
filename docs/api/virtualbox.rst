/virtualbox
---------------------------------------------

.. contents::

POST /virtualbox
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new VirtualBox VM instance

Response status codes
**********************
- **400**: Invalid project UUID
- **201**: Instance created
- **409**: Conflict

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>adapter_start_index</td>                    <td> </td>                     <td>integer</td>                     <td>adapter index from which to start using adapters</td>                     </tr>
    <tr><td>adapter_type</td>                    <td> </td>                     <td>string</td>                     <td>VirtualBox adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td> </td>                     <td>integer</td>                     <td>number of adapters</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>enable_remote_console</td>                    <td> </td>                     <td>boolean</td>                     <td>enable the remote console</td>                     </tr>
    <tr><td>headless</td>                    <td> </td>                     <td>boolean</td>                     <td>headless mode</td>                     </tr>
    <tr><td>linked_clone</td>                    <td>&#10004;</td>                     <td>boolean</td>                     <td>either the VM is a linked clone or not</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VirtualBox VM instance name</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>uuid</td>                    <td> </td>                     <td>string</td>                     <td>VirtualBox VM instance UUID</td>                     </tr>
    <tr><td>vbox_id</td>                    <td> </td>                     <td>integer</td>                     <td>VirtualBox VM instance ID (for project created before GNS3 1.3)</td>                     </tr>
    <tr><td>vmname</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VirtualBox VM name (in VirtualBox itself)</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>adapter_start_index</td>                    <td> </td>                     <td>integer</td>                     <td>adapter index from which to start using adapters</td>                     </tr>
    <tr><td>adapter_type</td>                    <td> </td>                     <td>string</td>                     <td>VirtualBox adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td> </td>                     <td>integer</td>                     <td>number of adapters</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>enable_remote_console</td>                    <td> </td>                     <td>boolean</td>                     <td>enable the remote console</td>                     </tr>
    <tr><td>headless</td>                    <td> </td>                     <td>boolean</td>                     <td>headless mode</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VirtualBox VM instance name</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>uuid</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VirtualBox VM instance UUID</td>                     </tr>
    <tr><td>vmname</td>                    <td> </td>                     <td>string</td>                     <td>VirtualBox VM name (in VirtualBox itself)</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: examples/post_virtualbox.txt

