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
    <tr><td>local</td>                    <td> </td>                     <td>boolean</td>                     <td>Whether this is a local server or not</td>                     </tr>
    <tr><td>version</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Version number</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_get_version.txt

