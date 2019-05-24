/v2/computes/{compute_id}/ports
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/computes/**{compute_id}**/ports
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get ports used by a compute

Parameters
**********
- **compute_id**: Compute UUID

Response status codes
**********************
- **200**: Ports information returned

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>console_port_range</td>                    <td> </td>                     <td>array</td>                     <td>Console port range</td>                     </tr>
    <tr><td>console_ports</td>                    <td> </td>                     <td>array</td>                     <td>Console ports used by the compute</td>                     </tr>
    <tr><td>udp_port_range</td>                    <td> </td>                     <td>array</td>                     <td>UDP port range</td>                     </tr>
    <tr><td>udp_ports</td>                    <td> </td>                     <td>array</td>                     <td>UDP ports used by the compute</td>                     </tr>
    </table>

