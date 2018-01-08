/v2/projects/{project_id}/snapshots/{snapshot_id}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

DELETE /v2/projects/**{project_id}**/snapshots/**{snapshot_id}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Delete a snapshot from disk

Parameters
**********
- **snapshot_id**: Snasphot UUID
- **project_id**: Project UUID

Response status codes
**********************
- **404**: The project or snapshot doesn't exist
- **204**: Changes have been written on disk

