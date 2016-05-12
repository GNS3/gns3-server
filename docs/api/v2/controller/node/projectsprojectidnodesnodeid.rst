/v2/projects/{project_id}/nodes/{node_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

PUT /v2/projects/**{project_id}**/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a node instance

Response status codes
**********************
- **400**: Invalid request
- **201**: Instance created

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>compute_id</td>                    <td> </td>                     <td>string</td>                     <td>Compute identifier</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: serial, vnc, telnet</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Node name</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>Node identifier</td>                     </tr>
    <tr><td>node_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: docker, dynamips, vpcs, virtualbox, vmware, iou, qemu</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project identifier</td>                     </tr>
    <tr><td>properties</td>                    <td> </td>                     <td>object</td>                     <td>Properties specific to an emulator</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>compute_id</td>                    <td> </td>                     <td>string</td>                     <td>Compute identifier</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: serial, vnc, telnet</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Node name</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>Node identifier</td>                     </tr>
    <tr><td>node_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: docker, dynamips, vpcs, virtualbox, vmware, iou, qemu</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project identifier</td>                     </tr>
    <tr><td>properties</td>                    <td> </td>                     <td>object</td>                     <td>Properties specific to an emulator</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/controller_put_projectsprojectidnodesnodeid.txt


DELETE /v2/projects/**{project_id}**/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a node instance

Parameters
**********
- **node_id**: UUID for the node
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **201**: Instance deleted

Sample session
***************


.. literalinclude:: ../../../examples/controller_delete_projectsprojectidnodesnodeid.txt

