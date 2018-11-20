/v2/compute/projects/{project_id}/cloud/nodes
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/cloud/nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new cloud instance

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
Types
+++++++++
HostInterfaces
^^^^^^^^^^^^^^^^^^^^^^
Interfaces on this host

.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Interface name</td>                     </tr>
    <tr><td>special</td>                    <td>&#10004;</td>                     <td>boolean</td>                     <td>If true the interface is non standard (firewire for example)</td>                     </tr>
    <tr><td>type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: ethernet, tap</td>                     </tr>
    </table>

Body
+++++++++
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>interfaces</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Cloud name</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td></td>                     <td>Node UUID</td>                     </tr>
    <tr><td>ports_mapping</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>remote_console_host</td>                    <td> </td>                     <td>['string']</td>                     <td>Remote console host or IP</td>                     </tr>
    <tr><td>remote_console_http_path</td>                    <td> </td>                     <td>string</td>                     <td>Path of the remote web interface</td>                     </tr>
    <tr><td>remote_console_port</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>remote_console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, vnc, spice, http, https, none</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>interfaces</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Cloud name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>string</td>                     <td>Path to the VM working directory</td>                     </tr>
    <tr><td>node_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>ports_mapping</td>                    <td>&#10004;</td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>remote_console_host</td>                    <td> </td>                     <td>['string']</td>                     <td>Remote console host or IP</td>                     </tr>
    <tr><td>remote_console_http_path</td>                    <td> </td>                     <td>string</td>                     <td>Path of the remote web interface</td>                     </tr>
    <tr><td>remote_console_port</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>remote_console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, vnc, spice, http, https, none</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_post_projectsprojectidcloudnodes.txt

