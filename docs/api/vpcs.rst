/vpcs
---------------------------------------------

.. contents::

POST /vpcs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new VPCS instance

Response status codes
**********************
- **201**: VPCS instance created
- **409**: Conflict

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>console</td>                    <td> </td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VPCS device name</td>                     </tr>
    <tr><td>project_uuid</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>uuid</td>                    <td> </td>                     <td>string</td>                     <td>VPCS device UUID</td>                     </tr>
    <tr><td>vpcs_id</td>                    <td> </td>                     <td>integer</td>                     <td>VPCS device instance ID (for project created before GNS3 1.3)</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>console</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VPCS device name</td>                     </tr>
    <tr><td>project_uuid</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>uuid</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>VPCS device UUID</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: examples/post_vpcs.txt

