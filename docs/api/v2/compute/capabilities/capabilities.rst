/v2/compute/capabilities
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/capabilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Retrieve the capabilities of the server

Response status codes
**********************
- **200**: OK

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>node_types</td>                    <td>&#10004;</td>                     <td>array</td>                     <td>Node type supported by the compute</td>                     </tr>
    <tr><td>platform</td>                    <td> </td>                     <td>string</td>                     <td>Platform where the compute is running</td>                     </tr>
    <tr><td>version</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>Version number</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_get_capabilities.txt

