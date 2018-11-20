/v2/appliances
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/appliances
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new appliance

Response status codes
**********************
- **201**: Appliance created
- **400**: Invalid request

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>appliance_id</td>                    <td> </td>                     <td>string</td>                     <td>Appliance UUID from which the node has been created. Read only</td>                     </tr>
    <tr><td>appliance_type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: cloud, ethernet_hub, ethernet_switch, docker, dynamips, vpcs, traceng, virtualbox, vmware, iou, qemu</td>                     </tr>
    <tr><td>builtin</td>                    <td> </td>                     <td>boolean</td>                     <td>Appliance is builtin</td>                     </tr>
    <tr><td>category</td>                    <td> </td>                     <td></td>                     <td>Appliance category</td>                     </tr>
    <tr><td>compute_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Compute identifier</td>                     </tr>
    <tr><td>default_name_format</td>                    <td> </td>                     <td>string</td>                     <td>Default name format</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Appliance name</td>                     </tr>
    <tr><td>symbol</td>                    <td> </td>                     <td>string</td>                     <td>Symbol of the appliance</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>appliance_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Appliance UUID from which the node has been created. Read only</td>                     </tr>
    <tr><td>appliance_type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: cloud, ethernet_hub, ethernet_switch, docker, dynamips, vpcs, traceng, virtualbox, vmware, iou, qemu</td>                     </tr>
    <tr><td>builtin</td>                    <td>&#10004;</td>                     <td>boolean</td>                     <td>Appliance is builtin</td>                     </tr>
    <tr><td>category</td>                    <td>&#10004;</td>                     <td></td>                     <td>Appliance category</td>                     </tr>
    <tr><td>compute_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Compute identifier</td>                     </tr>
    <tr><td>default_name_format</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Default name format</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Appliance name</td>                     </tr>
    <tr><td>symbol</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Symbol of the appliance</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/controller_post_appliances.txt


GET /v2/appliances
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
List of appliance

Response status codes
**********************
- **200**: Appliance list returned

Sample session
***************


.. literalinclude:: ../../../examples/controller_get_appliances.txt

