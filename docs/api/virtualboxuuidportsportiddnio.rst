/virtualbox/{uuid}/ports/{port_id:\d+}/nio
---------------------------------------------

.. contents::

POST /virtualbox/**{uuid}**/ports/**{port_id:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID
- **port_id**: ID of the port where the nio should be added

Response status codes
**********************
- **400**: Invalid instance UUID
- **201**: NIO created
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: examples/post_virtualboxuuidportsportiddnio.txt


DELETE /virtualbox/**{uuid}**/ports/**{port_id:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a VirtualBox VM instance

Parameters
**********
- **uuid**: Instance UUID
- **port_id**: ID of the port from where the nio should be removed

Response status codes
**********************
- **400**: Invalid instance UUID
- **404**: Instance doesn't exist
- **204**: NIO deleted

Sample session
***************


.. literalinclude:: examples/delete_virtualboxuuidportsportiddnio.txt

