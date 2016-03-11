/v2/projects/{project_id}/links
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/projects/**{project_id}**/links
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new link instance

Parameters
**********
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **201**: Link created

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>link_id</td>                    <td> </td>                     <td>string</td>                     <td>Link identifier</td>                     </tr>
    <tr><td>vms</td>                    <td>&#10004;</td>                     <td>array</td>                     <td>List of the VMS</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>link_id</td>                    <td> </td>                     <td>string</td>                     <td>Link identifier</td>                     </tr>
    <tr><td>vms</td>                    <td>&#10004;</td>                     <td>array</td>                     <td>List of the VMS</td>                     </tr>
    </table>

