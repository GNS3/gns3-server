/vpcs/{uuid}/ports/{port_number:\d+}/nio
---------------------------------------------

.. contents::

POST /vpcs/**{uuid}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a VPCS instance

Parameters
**********
- **uuid**: Instance UUID
- **port_number**: Port where the nio should be added

Response status codes
**********************
- **400**: Invalid instance UUID
- **201**: NIO created
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: examples/post_vpcsuuidportsportnumberdnio.txt


DELETE /vpcs/**{uuid}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a VPCS instance

Parameters
**********
- **uuid**: Instance UUID
- **port_number**: Port from where the nio should be removed

Response status codes
**********************
- **400**: Invalid instance UUID
- **404**: Instance doesn't exist
- **204**: NIO deleted

Sample session
***************


.. literalinclude:: examples/delete_vpcsuuidportsportnumberdnio.txt

