/vpcs/{vpcs_id}
------------------------------

.. contents::

GET /vpcs/{vpcs_id}
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get informations about a VPCS

Parameters
**********
- **vpcs_id**: Id of VPCS instance

Response status codes
**************************
- **200**: OK

Output
*******
.. raw:: html

    <table>
    <tr><th>Name</th><th>Mandatory</th><th>Type</th><th>Description</th></tr>
    <tr><td>console</td><td>&#10004;</td><td>integer</td><td>console TCP port</td></tr>
    <tr><td>name</td><td>&#10004;</td><td>string</td><td>VPCS device name</td></tr>
    <tr><td>vpcs_id</td><td>&#10004;</td><td>integer</td><td>VPCS device instance ID</td></tr>
    </table>


PUT /vpcs/{vpcs_id}
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update VPCS informations

Parameters
**********
- **vpcs_id**: Id of VPCS instance

Response status codes
**************************
- **200**: OK

Input
*******
.. raw:: html

    <table>
    <tr><th>Name</th><th>Mandatory</th><th>Type</th><th>Description</th></tr>
    <tr><td>console</td><td>&#10004;</td><td>integer</td><td>console TCP port</td></tr>
    <tr><td>name</td><td>&#10004;</td><td>string</td><td>VPCS device name</td></tr>
    <tr><td>vpcs_id</td><td>&#10004;</td><td>integer</td><td>VPCS device instance ID</td></tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr><th>Name</th><th>Mandatory</th><th>Type</th><th>Description</th></tr>
    <tr><td>console</td><td>&#10004;</td><td>integer</td><td>console TCP port</td></tr>
    <tr><td>name</td><td>&#10004;</td><td>string</td><td>VPCS device name</td></tr>
    <tr><td>vpcs_id</td><td>&#10004;</td><td>integer</td><td>VPCS device instance ID</td></tr>
    </table>

