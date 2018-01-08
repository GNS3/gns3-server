/v2/computes/endpoint/{compute_id}/{emulator}/{action:.+}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/computes/endpoint/**{compute_id}**/**{emulator}**/**{action:.+}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Returns the endpoint for particular `compute` to specific action. WARNING: This is experimental feature and may change anytime. Please don't rely on this endpoint.

Parameters
**********
- **compute_id**: Compute UUID

Response status codes
**********************
- **200**: OK
- **404**: Instance doesn't exist

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>endpoint</td>                    <td> </td>                     <td>string</td>                     <td>URL to endpoint on specific compute and to particular action</td>                     </tr>
    </table>

