/v2/compute/projects/{project_id}/traceng/nodes/{node_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/projects/**{project_id}**/traceng/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a TraceNG instance

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
    <tr><td>command_line</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Last command line used by GNS3 to start TraceNG</td>                     </tr>
    <tr><td>console</td>                    <td>&#10004;</td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: none</td>                     </tr>
    <tr><td>default_destination</td>                    <td>&#10004;</td>                     <td>['string']</td>                     <td>Default destination IP address or hostname for tracing</td>                     </tr>
    <tr><td>ip_address</td>                    <td>&#10004;</td>                     <td>['string']</td>                     <td>Source IP address for tracing</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>TraceNG VM name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>string</td>                     <td>Path to the VM working directory</td>                     </tr>
    <tr><td>node_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>status</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_get_projectsprojectidtracengnodesnodeid.txt


PUT /v2/compute/projects/**{project_id}**/traceng/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a TraceNG instance

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
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: none</td>                     </tr>
    <tr><td>default_destination</td>                    <td> </td>                     <td>['string']</td>                     <td>Default destination IP address or hostname for tracing</td>                     </tr>
    <tr><td>ip_address</td>                    <td> </td>                     <td>['string']</td>                     <td>Source IP address for tracing</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>TraceNG VM name</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>command_line</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Last command line used by GNS3 to start TraceNG</td>                     </tr>
    <tr><td>console</td>                    <td>&#10004;</td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: none</td>                     </tr>
    <tr><td>default_destination</td>                    <td>&#10004;</td>                     <td>['string']</td>                     <td>Default destination IP address or hostname for tracing</td>                     </tr>
    <tr><td>ip_address</td>                    <td>&#10004;</td>                     <td>['string']</td>                     <td>Source IP address for tracing</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>TraceNG VM name</td>                     </tr>
    <tr><td>node_directory</td>                    <td> </td>                     <td>string</td>                     <td>Path to the VM working directory</td>                     </tr>
    <tr><td>node_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>status</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_put_projectsprojectidtracengnodesnodeid.txt


DELETE /v2/compute/projects/**{project_id}**/traceng/nodes/**{node_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a TraceNG instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **204**: Instance deleted
- **400**: Invalid request
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/compute_delete_projectsprojectidtracengnodesnodeid.txt

