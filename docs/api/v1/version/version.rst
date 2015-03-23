/v1/version
----------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v1/version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Retrieve the server version number

Response status codes
**********************
- **200**: OK

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>version</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Version number human readable</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../examples/get_version.txt


POST /v1/version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Check if version is the same as the server

Response status codes
**********************
- **200**: Same version
- **409**: Invalid version

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>version</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Version number human readable</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>version</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Version number human readable</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../examples/post_version.txt

