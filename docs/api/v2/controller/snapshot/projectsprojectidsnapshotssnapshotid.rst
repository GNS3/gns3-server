/v2/projects/{project_id}/snapshots/{snapshot_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

DELETE /v2/projects/**{project_id}**/snapshots/**{snapshot_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a snapshot from disk

Parameters
**********
- **project_id**: Project UUID
- **snapshot_id**: Snapshot UUID

Response status codes
**********************
- **204**: Changes have been written on disk
- **404**: The project or snapshot doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/controller_delete_projectsprojectidsnapshotssnapshotid.txt

