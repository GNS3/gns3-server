/project/{uuid}/commit
---------------------------------------------

.. contents::

POST /project/**{uuid}**/commit
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Write changes on disk

Parameters
**********
- **uuid**: Project instance UUID

Response status codes
**********************
- **404**: Project instance doesn't exist
- **204**: Changes write on disk

Sample session
***************


.. literalinclude:: examples/post_projectuuidcommit.txt

