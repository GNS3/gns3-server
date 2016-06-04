/v2/computes
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/computes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Register a compute server

Response status codes
**********************
- **201**: Compute server added

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>compute_id</td>                    <td> </td>                     <td>string</td>                     <td>Server identifier</td>                     </tr>
    <tr><td>host</td>                    <td> </td>                     <td>string</td>                     <td>Server host</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Server name</td>                     </tr>
    <tr><td>password</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Password for authentication</td>                     </tr>
    <tr><td>port</td>                    <td> </td>                     <td>integer</td>                     <td>Server port</td>                     </tr>
    <tr><td>protocol</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: http, https</td>                     </tr>
    <tr><td>user</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>User for authentication</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>compute_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Server identifier</td>                     </tr>
    <tr><td>connected</td>                    <td>&#10004;</td>                     <td>boolean</td>                     <td>Whether the controller is connected to the compute server or not</td>                     </tr>
    <tr><td>host</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Server host</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Server name</td>                     </tr>
    <tr><td>port</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Server port</td>                     </tr>
    <tr><td>protocol</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: http, https</td>                     </tr>
    <tr><td>user</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>User for authentication</td>                     </tr>
    <tr><td>version</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Version of the GNS3 remote compute server</td>                     </tr>
    </table>


GET /v2/computes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
List of compute servers

Response status codes
**********************
- **200**: Compute servers list returned

