/project
---------------------------------------------

.. contents::

POST /project
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a project on the server

Response status codes
**********************
- **200**: OK

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>location</td>                    <td> </td>                     <td>string</td>                     <td>Base directory where the project should be created on remote server</td>                     </tr>
    <tr><td>uuid</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>location</td>                    <td> </td>                     <td>string</td>                     <td>Base directory where the project should be created on remote server</td>                     </tr>
    <tr><td>uuid</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: examples/post_project.txt

