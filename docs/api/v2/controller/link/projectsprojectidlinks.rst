/v2/projects/{project_id}/links
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/projects/**{project_id}**/links
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
List links of a project

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **200**: List of links returned

Sample session
***************


.. literalinclude:: ../../../examples/controller_get_projectsprojectidlinks.txt


POST /v2/projects/**{project_id}**/links
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new link instance

Parameters
**********
- **project_id**: Project UUID

Response status codes
**********************
- **201**: Link created
- **400**: Invalid request

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>capture_file_name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Read only property. The name of the capture file if capture is running</td>                     </tr>
    <tr><td>capture_file_path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Read only property. The full path of the capture file if capture is running</td>                     </tr>
    <tr><td>capturing</td>                    <td> </td>                     <td>boolean</td>                     <td>Read only property. True if a capture running on the link</td>                     </tr>
    <tr><td>link_id</td>                    <td> </td>                     <td>string</td>                     <td>Link UUID</td>                     </tr>
    <tr><td>link_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: ethernet, serial</td>                     </tr>
    <tr><td>nodes</td>                    <td>&#10004;</td>                     <td>array</td>                     <td>List of the VMS</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>capture_file_name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Read only property. The name of the capture file if capture is running</td>                     </tr>
    <tr><td>capture_file_path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Read only property. The full path of the capture file if capture is running</td>                     </tr>
    <tr><td>capturing</td>                    <td> </td>                     <td>boolean</td>                     <td>Read only property. True if a capture running on the link</td>                     </tr>
    <tr><td>link_id</td>                    <td> </td>                     <td>string</td>                     <td>Link UUID</td>                     </tr>
    <tr><td>link_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: ethernet, serial</td>                     </tr>
    <tr><td>nodes</td>                    <td>&#10004;</td>                     <td>array</td>                     <td>List of the VMS</td>                     </tr>
    <tr><td>project_id</td>                    <td> </td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/controller_post_projectsprojectidlinks.txt

