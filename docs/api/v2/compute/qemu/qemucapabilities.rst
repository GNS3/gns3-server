/v2/compute/qemu/capabilities
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/compute/qemu/capabilities
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get a list of Qemu capabilities on this server

Response status codes
**********************
- **200**: Success

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>kvm</td>                    <td> </td>                     <td>array</td>                     <td>Architectures that KVM is enabled for</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_get_qemucapabilities.txt

