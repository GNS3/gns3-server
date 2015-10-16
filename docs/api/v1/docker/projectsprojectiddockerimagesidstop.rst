/v1/projects/{project_id}/docker/images/{id}/stop
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/docker/images/**{id}**/stop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a Docker container

Parameters
**********
- **id**: ID of the container
- **project_id**: UUID of the project

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Instance stopped

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>adapter_type</td>                    <td> </td>                     <td>string</td>                     <td>Docker adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td> </td>                     <td>integer</td>                     <td>number of adapters</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>string</td>                     <td>console name</td>                     </tr>
    <tr><td>imagename</td>                    <td> </td>                     <td>string</td>                     <td>Docker image name</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Docker container name</td>                     </tr>
    <tr><td>startcmd</td>                    <td> </td>                     <td>string</td>                     <td>Docker CMD entry</td>                     </tr>
    <tr><td>vm_id</td>                    <td> </td>                     <td></td>                     <td>Docker VM instance identifier</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>adapter_type</td>                    <td> </td>                     <td>string</td>                     <td>Docker adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td> </td>                     <td>integer</td>                     <td>number of adapters</td>                     </tr>
    <tr><td>cid</td>                    <td> </td>                     <td>string</td>                     <td>Docker container ID</td>                     </tr>
    <tr><td>image</td>                    <td> </td>                     <td>string</td>                     <td>Docker image name</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Docker container name</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>vm_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Docker container instance UUID</td>                     </tr>
    </table>

