/v2/templates/{template_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/templates/**{template_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Get an template

Response status codes
**********************
- **200**: Template found
- **400**: Invalid request
- **404**: Template doesn't exist

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>builtin</td>                    <td>&#10004;</td>                     <td>boolean</td>                     <td>Template is builtin</td>                     </tr>
    <tr><td>category</td>                    <td>&#10004;</td>                     <td></td>                     <td>Template category</td>                     </tr>
    <tr><td>compute_id</td>                    <td>&#10004;</td>                     <td>['null', 'string']</td>                     <td>Compute identifier</td>                     </tr>
    <tr><td>default_name_format</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Default name format</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Template name</td>                     </tr>
    <tr><td>symbol</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Symbol of the template</td>                     </tr>
    <tr><td>template_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Template UUID</td>                     </tr>
    <tr><td>template_type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: cloud, ethernet_hub, ethernet_switch, docker, dynamips, vpcs, traceng, virtualbox, vmware, iou, qemu</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/controller_get_templatestemplateid.txt


PUT /v2/templates/**{template_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update an template

Response status codes
**********************
- **200**: Template updated
- **400**: Invalid request
- **404**: Template doesn't exist

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>builtin</td>                    <td> </td>                     <td>boolean</td>                     <td>Template is builtin</td>                     </tr>
    <tr><td>category</td>                    <td> </td>                     <td></td>                     <td>Template category</td>                     </tr>
    <tr><td>compute_id</td>                    <td> </td>                     <td>['null', 'string']</td>                     <td>Compute identifier</td>                     </tr>
    <tr><td>default_name_format</td>                    <td> </td>                     <td>string</td>                     <td>Default name format</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>string</td>                     <td>Template name</td>                     </tr>
    <tr><td>symbol</td>                    <td> </td>                     <td>string</td>                     <td>Symbol of the template</td>                     </tr>
    <tr><td>template_id</td>                    <td> </td>                     <td>string</td>                     <td>Template UUID</td>                     </tr>
    <tr><td>template_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: cloud, ethernet_hub, ethernet_switch, docker, dynamips, vpcs, traceng, virtualbox, vmware, iou, qemu</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>builtin</td>                    <td>&#10004;</td>                     <td>boolean</td>                     <td>Template is builtin</td>                     </tr>
    <tr><td>category</td>                    <td>&#10004;</td>                     <td></td>                     <td>Template category</td>                     </tr>
    <tr><td>compute_id</td>                    <td>&#10004;</td>                     <td>['null', 'string']</td>                     <td>Compute identifier</td>                     </tr>
    <tr><td>default_name_format</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Default name format</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Template name</td>                     </tr>
    <tr><td>symbol</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Symbol of the template</td>                     </tr>
    <tr><td>template_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Template UUID</td>                     </tr>
    <tr><td>template_type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: cloud, ethernet_hub, ethernet_switch, docker, dynamips, vpcs, traceng, virtualbox, vmware, iou, qemu</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/controller_put_templatestemplateid.txt


DELETE /v2/templates/**{template_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete an template

Parameters
**********
- **template_id**: template UUID

Response status codes
**********************
- **204**: Template deleted
- **400**: Invalid request
- **404**: Template doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/controller_delete_templatestemplateid.txt

