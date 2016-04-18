/v2/compute/version
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Retrieve the server version number

Response status codes
**********************
- **200**: OK

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>local</td>                    <td> </td>                     <td>boolean</td>                     <td>Either this is a local server</td>                     </tr>
    <tr><td>version</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Version number human readable</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_get_version.txt


POST /v2/compute/version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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
    <tr><td>local</td>                    <td> </td>                     <td>boolean</td>                     <td>Either this is a local server</td>                     </tr>
    <tr><td>version</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Version number human readable</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>local</td>                    <td> </td>                     <td>boolean</td>                     <td>Either this is a local server</td>                     </tr>
    <tr><td>version</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Version number human readable</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_post_version.txt

