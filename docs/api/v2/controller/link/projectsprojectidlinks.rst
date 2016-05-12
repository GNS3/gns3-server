/v2/projects/{project_id}/links
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/projects/**{project_id}**/links
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new link instance

Parameters
**********
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **201**: Link created

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>capture_file_name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Read only propertie. The name of the capture file if capture is running</td>                     </tr>
    <tr><td>capture_file_path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Read only propertie. The full path of the capture file if capture is running</td>                     </tr>
    <tr><td>capturing</td>                    <td> </td>                     <td>boolean</td>                     <td>Read only propertie. True if a capture running on the link</td>                     </tr>
    <tr><td>link_id</td>                    <td> </td>                     <td>string</td>                     <td>Link identifier</td>                     </tr>
    <tr><td>nodes</td>                    <td>&#10004;</td>                     <td>array</td>                     <td>List of the VMS</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>capture_file_name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Read only propertie. The name of the capture file if capture is running</td>                     </tr>
    <tr><td>capture_file_path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Read only propertie. The full path of the capture file if capture is running</td>                     </tr>
    <tr><td>capturing</td>                    <td> </td>                     <td>boolean</td>                     <td>Read only propertie. True if a capture running on the link</td>                     </tr>
    <tr><td>link_id</td>                    <td> </td>                     <td>string</td>                     <td>Link identifier</td>                     </tr>
    <tr><td>nodes</td>                    <td>&#10004;</td>                     <td>array</td>                     <td>List of the VMS</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/controller_post_projectsprojectidlinks.txt

