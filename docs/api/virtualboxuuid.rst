/virtualbox/{uuid}
---------------------------------------------

.. contents::

GET /virtualbox/**{uuid}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID

Response status codes
**********************
- **200**: Success
- **404**: Instance doesn't exist

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


.. literalinclude:: examples/get_virtualboxuuid.txt


PUT /virtualbox/**{uuid}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID

Response status codes
**********************
- **200**: Instance updated
- **409**: Conflict
- **404**: Instance doesn't exist

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
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>VirtualBox VM instance name</td>                     </tr>
    <tr><td>vmname</td>                    <td> </td>                     <td>string</td>                     <td>VirtualBox VM name (in VirtualBox itself)</td>                     </tr>
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


DELETE /virtualbox/**{uuid}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID

Response status codes
**********************
- **404**: Instance doesn't exist
- **204**: Instance deleted

