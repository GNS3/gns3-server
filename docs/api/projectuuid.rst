/project/{uuid}
---------------------------------------------

.. contents::

GET /project/**{uuid}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get project information

Parameters
**********
- **uuid**: Project instance UUID

Response status codes
**********************
- **200**: OK
- **404**: Project instance doesn't exist

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>location</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Base directory where the project should be created on remote server</td>                     </tr>
    <tr><td>temporary</td>                    <td>&#10004;</td>                     <td>boolean</td>                     <td>If project is a temporary project</td>                     </tr>
    <tr><td>uuid</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: examples/get_projectuuid.txt


PUT /project/**{uuid}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a project

Parameters
**********
- **uuid**: Project instance UUID

Response status codes
**********************
- **200**: Project updated
- **404**: Project instance doesn't exist

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>temporary</td>                    <td> </td>                     <td>boolean</td>                     <td>If project is a temporary project</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>location</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Base directory where the project should be created on remote server</td>                     </tr>
    <tr><td>temporary</td>                    <td>&#10004;</td>                     <td>boolean</td>                     <td>If project is a temporary project</td>                     </tr>
    <tr><td>uuid</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: examples/put_projectuuid.txt


DELETE /project/**{uuid}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a project from disk

Parameters
**********
- **uuid**: Project instance UUID

Response status codes
**********************
- **404**: Project instance doesn't exist
- **204**: Changes write on disk

Sample session
***************


.. literalinclude:: examples/delete_projectuuid.txt

