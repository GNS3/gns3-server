/v1/qemu/binaries
----------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v1/qemu/binaries
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a list of available Qemu binaries

Response status codes
**********************
- **200**: Success
- **400**: Invalid request
- **404**: Instance doesn't exist

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>archs</td>                    <td> </td>                     <td>array</td>                     <td>Architectures to filter binaries by</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/get_qemubinaries.txt

