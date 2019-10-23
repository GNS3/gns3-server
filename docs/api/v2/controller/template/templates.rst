/v2/templates
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/templates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new template

Response status codes
**********************
- **201**: Template created
- **400**: Invalid request

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>builtin</td>                    <td> </td>                     <td>boolean</td>                     <td>Template is builtin</td>                     </tr>
    <tr><td>category</td>                    <td> </td>                     <td></td>                     <td>Template category</td>                     </tr>
    <tr><td>compute_id</td>                    <td>&#10004;</td>                     <td>['null', 'string']</td>                     <td>Compute identifier</td>                     </tr>
    <tr><td>default_name_format</td>                    <td> </td>                     <td>string</td>                     <td>Default name format</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Template name</td>                     </tr>
    <tr><td>symbol</td>                    <td> </td>                     <td>string</td>                     <td>Symbol of the template</td>                     </tr>
    <tr><td>template_id</td>                    <td> </td>                     <td>string</td>                     <td>Template UUID</td>                     </tr>
    <tr><td>template_type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: cloud, ethernet_hub, ethernet_switch, docker, dynamips, vpcs, traceng, virtualbox, vmware, iou, qemu</td>                     </tr>
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


.. literalinclude:: ../../../examples/controller_post_templates.txt


GET /v2/templates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
List of template

Response status codes
**********************
- **200**: Template list returned

Sample session
***************


.. literalinclude:: ../../../examples/controller_get_templates.txt

