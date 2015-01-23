/project/{uuid}/close
---------------------------------------------

.. contents::

POST /project/**{uuid}**/close
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Close project

Parameters
**********
- **uuid**: Project instance UUID

Response status codes
**********************
- **404**: Project instance doesn't exist
- **204**: Project closed

Sample session
***************


.. literalinclude:: examples/post_projectuuidclose.txt

