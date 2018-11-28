/v2/computes
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/computes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Register a compute

Response status codes
**********************
- **201**: Compute added

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>compute_id</td>                    <td> </td>                     <td>string</td>                     <td>Server identifier</td>                     </tr>
    <tr><td>host</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Server host</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Server name</td>                     </tr>
    <tr><td>password</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Password for authentication</td>                     </tr>
    <tr><td>port</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Server port</td>                     </tr>
    <tr><td>protocol</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: http, https</td>                     </tr>
    <tr><td>user</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>User for authentication</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>capabilities</td>                    <td> </td>                     <td>object</td>                     <td>Get what a server support</td>                     </tr>
    <tr><td>compute_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Server identifier</td>                     </tr>
    <tr><td>connected</td>                    <td> </td>                     <td>boolean</td>                     <td>Whether the controller is connected to the compute or not</td>                     </tr>
    <tr><td>cpu_usage_percent</td>                    <td> </td>                     <td>['number', 'null']</td>                     <td>CPU usage of the compute. Read only</td>                     </tr>
    <tr><td>host</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Server host</td>                     </tr>
    <tr><td>last_error</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Last error on the compute</td>                     </tr>
    <tr><td>memory_usage_percent</td>                    <td> </td>                     <td>['number', 'null']</td>                     <td>RAM usage of the compute. Read only</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Server name</td>                     </tr>
    <tr><td>port</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Server port</td>                     </tr>
    <tr><td>protocol</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: http, https</td>                     </tr>
    <tr><td>user</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>User for authentication</td>                     </tr>
    </table>


GET /v2/computes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
List of computes

Response status codes
**********************
- **200**: Computes list returned

