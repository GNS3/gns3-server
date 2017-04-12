/v2/projects/{project_id}/nodes
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/projects/**{project_id}**/nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new node instance

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **201**: Instance created
- **400**: Invalid request

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>command_line</td>                    <td> </td>                     <td>['null', 'string']</td>                     <td>Command line use to start the node</td>                     </tr>
    <tr><td>compute_id</td>                    <td> </td>                     <td>string</td>                     <td>Compute identifier</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_host</td>                    <td> </td>                     <td>string</td>                     <td>Console host. Warning if the host is 0.0.0.0 or :: (listen on all interfaces) you need to use the same address you use to connect to the controller.</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: vnc, telnet, http, null</td>                     </tr>
    <tr><td>first_port_name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Name of the first port</td>                     </tr>
    <tr><td>height</td>                    <td> </td>                     <td>integer</td>                     <td>Height of the node (Read only)</td>                     </tr>
    <tr><td>label</td>                    <td> </td>                     <td>object</td>                     <td></td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Node name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>['null', 'string']</td>                     <td>Working directory of the node. Read only</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>node_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: cloud, nat, ethernet_hub, ethernet_switch, frame_relay_switch, atm_switch, docker, dynamips, vpcs, virtualbox, vmware, iou, qemu</td>                     </tr>
    <tr><td>port_name_format</td>                    <td> </td>                     <td>string</td>                     <td>Formating for port name {0} will be replace by port number</td>                     </tr>
    <tr><td>port_segment_size</td>                    <td> </td>                     <td>integer</td>                     <td>Size of the port segment</td>                     </tr>
    <tr><td>ports</td>                    <td> </td>                     <td>array</td>                     <td>List of node ports READ only</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>properties</td>                    <td> </td>                     <td>object</td>                     <td>Properties specific to an emulator</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: stopped, started, suspended</td>                     </tr>
    <tr><td>symbol</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Symbol of the node</td>                     </tr>
    <tr><td>width</td>                    <td> </td>                     <td>integer</td>                     <td>Width of the node (Read only)</td>                     </tr>
    <tr><td>x</td>                    <td> </td>                     <td>integer</td>                     <td>X position of the node</td>                     </tr>
    <tr><td>y</td>                    <td> </td>                     <td>integer</td>                     <td>Y position of the node</td>                     </tr>
    <tr><td>z</td>                    <td> </td>                     <td>integer</td>                     <td>Z position of the node</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>command_line</td>                    <td> </td>                     <td>['null', 'string']</td>                     <td>Command line use to start the node</td>                     </tr>
    <tr><td>compute_id</td>                    <td> </td>                     <td>string</td>                     <td>Compute identifier</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_host</td>                    <td> </td>                     <td>string</td>                     <td>Console host. Warning if the host is 0.0.0.0 or :: (listen on all interfaces) you need to use the same address you use to connect to the controller.</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: vnc, telnet, http, null</td>                     </tr>
    <tr><td>first_port_name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Name of the first port</td>                     </tr>
    <tr><td>height</td>                    <td> </td>                     <td>integer</td>                     <td>Height of the node (Read only)</td>                     </tr>
    <tr><td>label</td>                    <td> </td>                     <td>object</td>                     <td></td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Node name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>['null', 'string']</td>                     <td>Working directory of the node. Read only</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>node_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: cloud, nat, ethernet_hub, ethernet_switch, frame_relay_switch, atm_switch, docker, dynamips, vpcs, virtualbox, vmware, iou, qemu</td>                     </tr>
    <tr><td>port_name_format</td>                    <td> </td>                     <td>string</td>                     <td>Formating for port name {0} will be replace by port number</td>                     </tr>
    <tr><td>port_segment_size</td>                    <td> </td>                     <td>integer</td>                     <td>Size of the port segment</td>                     </tr>
    <tr><td>ports</td>                    <td> </td>                     <td>array</td>                     <td>List of node ports READ only</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>properties</td>                    <td> </td>                     <td>object</td>                     <td>Properties specific to an emulator</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: stopped, started, suspended</td>                     </tr>
    <tr><td>symbol</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Symbol of the node</td>                     </tr>
    <tr><td>width</td>                    <td> </td>                     <td>integer</td>                     <td>Width of the node (Read only)</td>                     </tr>
    <tr><td>x</td>                    <td> </td>                     <td>integer</td>                     <td>X position of the node</td>                     </tr>
    <tr><td>y</td>                    <td> </td>                     <td>integer</td>                     <td>Y position of the node</td>                     </tr>
    <tr><td>z</td>                    <td> </td>                     <td>integer</td>                     <td>Z position of the node</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/controller_post_projectsprojectidnodes.txt


GET /v2/projects/**{project_id}**/nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
List nodes of a project

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **200**: List of nodes returned

Sample session
***************


.. literalinclude:: ../../../examples/controller_get_projectsprojectidnodes.txt

