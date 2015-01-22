/vpcs/{uuid}/ports/{port_id}/nio
---------------------------------------------

.. contents::

POST /vpcs/**{uuid}**/ports/**{port_id}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a VPCS

Parameters
**********
- **port_id**: Id of the port where the nio should be add
- **uuid**: VPCS instance UUID

Response status codes
**********************
- **400**: Invalid VPCS instance UUID
- **201**: NIO created
- **404**: VPCS instance doesn't exist

Sample session
***************


.. literalinclude:: examples/post_vpcsuuidportsportidnio.txt


DELETE /vpcs/**{uuid}**/ports/**{port_id}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a VPCS

Parameters
**********
- **port_id**: ID of the port where the nio should be removed
- **uuid**: VPCS instance UUID

Response status codes
**********************
- **400**: Invalid VPCS instance UUID
- **404**: VPCS instance doesn't exist
- **204**: NIO deleted

Sample session
***************


.. literalinclude:: examples/delete_vpcsuuidportsportidnio.txt

