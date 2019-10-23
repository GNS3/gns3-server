/v2/compute/projects/{project_id}/docker/nodes/{node_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

DELETE /v2/compute/projects/**{project_id}**/docker/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a Docker container

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **204**: Instance deleted
- **400**: Invalid request
- **404**: Instance doesn't exist


PUT /v2/compute/projects/**{project_id}**/docker/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a Docker instance

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
    <tr><td>adapters</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>number of adapters</td>                     </tr>
    <tr><td>aux</td>                    <td> </td>                     <td>integer</td>                     <td>Auxiliary TCP port</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_http_path</td>                    <td> </td>                     <td>string</td>                     <td>Path of the web interface</td>                     </tr>
    <tr><td>console_http_port</td>                    <td> </td>                     <td>integer</td>                     <td>Internal port in the container for the HTTP server</td>                     </tr>
    <tr><td>console_resolution</td>                    <td> </td>                     <td>string</td>                     <td>Console resolution for VNC</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, vnc, http, https, none</td>                     </tr>
    <tr><td>container_id</td>                    <td> </td>                     <td>string</td>                     <td>Docker container ID Read only</td>                     </tr>
    <tr><td>custom_adapters</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>environment</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Docker environment</td>                     </tr>
    <tr><td>extra_hosts</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Docker extra hosts (added to /etc/hosts)</td>                     </tr>
    <tr><td>extra_volumes</td>                    <td> </td>                     <td>array</td>                     <td>Additional directories to make persistent</td>                     </tr>
    <tr><td>image</td>                    <td> </td>                     <td>string</td>                     <td>Docker image name  Read only</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Docker container name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>string</td>                     <td>Path to the node working directory  Read only</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID Read only</td>                     </tr>
    <tr><td>start_command</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Docker CMD entry</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    <tr><td>usage</td>                    <td> </td>                     <td>string</td>                     <td>How to use the Docker container</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>adapters</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>number of adapters</td>                     </tr>
    <tr><td>aux</td>                    <td> </td>                     <td>integer</td>                     <td>Auxiliary TCP port</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_http_path</td>                    <td> </td>                     <td>string</td>                     <td>Path of the web interface</td>                     </tr>
    <tr><td>console_http_port</td>                    <td> </td>                     <td>integer</td>                     <td>Internal port in the container for the HTTP server</td>                     </tr>
    <tr><td>console_resolution</td>                    <td> </td>                     <td>string</td>                     <td>Console resolution for VNC</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, vnc, http, https, none</td>                     </tr>
    <tr><td>container_id</td>                    <td> </td>                     <td>string</td>                     <td>Docker container ID Read only</td>                     </tr>
    <tr><td>custom_adapters</td>                    <td> </td>                     <td>array</td>                     <td></td>                     </tr>
    <tr><td>environment</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Docker environment</td>                     </tr>
    <tr><td>extra_hosts</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Docker extra hosts (added to /etc/hosts)</td>                     </tr>
    <tr><td>extra_volumes</td>                    <td> </td>                     <td>array</td>                     <td>Additional directories to make persistent</td>                     </tr>
    <tr><td>image</td>                    <td> </td>                     <td>string</td>                     <td>Docker image name  Read only</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Docker container name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>string</td>                     <td>Path to the node working directory  Read only</td>                     </tr>
    <tr><td>node_id</td>                    <td> </td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID Read only</td>                     </tr>
    <tr><td>start_command</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Docker CMD entry</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    <tr><td>usage</td>                    <td> </td>                     <td>string</td>                     <td>How to use the Docker container</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_put_projectsprojectiddockernodesnodeid.txt

