/v2/projects/{project_id}/snapshots/{snapshot_id}/restore
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/projects/**{project_id}**/snapshots/**{snapshot_id}**/restore
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Restore a snapshot from disk

Parameters
**********
- **snapshot_id**: Snasphot UUID
- **project_id**: Project UUID

Response status codes
**********************
- **201**: The snapshot has been restored
- **404**: The project or snapshot doesn't exist

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>auto_close</td>                    <td> </td>                     <td>boolean</td>                     <td>Project auto close when client cut off the notifications feed</td>                     </tr>
    <tr><td>auto_open</td>                    <td> </td>                     <td>boolean</td>                     <td>Project open when GNS3 start</td>                     </tr>
    <tr><td>auto_start</td>                    <td> </td>                     <td>boolean</td>                     <td>Project start when opened</td>                     </tr>
    <tr><td>filename</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project filename</td>                     </tr>
    <tr><td>name</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project name</td>                     </tr>
    <tr><td>path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Project directory</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>status</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: opened, closed</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/controller_post_projectsprojectidsnapshotssnapshotidrestore.txt

