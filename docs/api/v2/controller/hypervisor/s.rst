/v2/controller/hypervisors
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/controller/hypervisors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Register a hypervisor

Response status codes
**********************
- **201**: Hypervisor added

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>host</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Server host</td>                     </tr>
    <tr><td>hypervisor_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Server identifier</td>                     </tr>
    <tr><td>password</td>                    <td> </td>                     <td>string</td>                     <td>Password for auth</td>                     </tr>
    <tr><td>port</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Server port</td>                     </tr>
    <tr><td>protocol</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: http, https</td>                     </tr>
    <tr><td>user</td>                    <td> </td>                     <td>string</td>                     <td>User for auth</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>connected</td>                    <td> </td>                     <td>boolean</td>                     <td>True if controller is connected to the hypervisor</td>                     </tr>
    <tr><td>host</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Server host</td>                     </tr>
    <tr><td>hypervisor_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Server identifier</td>                     </tr>
    <tr><td>port</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Server port</td>                     </tr>
    <tr><td>protocol</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: http, https</td>                     </tr>
    <tr><td>user</td>                    <td> </td>                     <td>string</td>                     <td>User for auth</td>                     </tr>
    <tr><td>version</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Version of the GNS3 remote hypervisor</td>                     </tr>
    </table>

