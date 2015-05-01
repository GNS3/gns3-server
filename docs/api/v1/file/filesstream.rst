/v1/files/stream
----------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v1/files/stream
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stream a file from the server

Response status codes
**********************
- **200**: File retrieved
- **409**: Can't access to file
- **404**: File doesn't exist

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>location</td>                    <td>&#10004;</td>                     <td>['string']</td>                     <td>File path</td>                     </tr>
    </table>

