/v2/hypervisor/projects/{project_id}/docker/vms
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/hypervisor/projects/**{project_id}**/docker/vms
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new Docker container

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
    <tr><td>adapters</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>number of adapters</td>                     </tr>
    <tr><td>aux</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>auxilary TCP port</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, vnc</td>                     </tr>
    <tr><td>environment</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Docker environment</td>                     </tr>
    <tr><td>image</td>                    <td> </td>                     <td>string</td>                     <td>Docker image name</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Docker container name</td>                     </tr>
    <tr><td>start_command</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Docker CMD entry</td>                     </tr>
    <tr><td>vm_id</td>                    <td> </td>                     <td>string</td>                     <td>Docker VM instance identifier</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>adapters</td>                    <td>&#10004;</td>                     <td>['integer', 'null']</td>                     <td>number of adapters</td>                     </tr>
    <tr><td>aux</td>                    <td>&#10004;</td>                     <td>['integer', 'null']</td>                     <td>auxilary TCP port</td>                     </tr>
    <tr><td>console</td>                    <td>&#10004;</td>                     <td>['integer', 'null']</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: telnet, vnc</td>                     </tr>
    <tr><td>container_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Docker container ID</td>                     </tr>
    <tr><td>environment</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>Docker environment</td>                     </tr>
    <tr><td>image</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Docker image name</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Docker container name</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>start_command</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>Docker CMD entry</td>                     </tr>
    <tr><td>vm_directory</td>                    <td>&#10004;</td>                     <td>string</td>                     <td></td>                     </tr>
    <tr><td>vm_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Docker container instance UUID</td>                     </tr>
    </table>

