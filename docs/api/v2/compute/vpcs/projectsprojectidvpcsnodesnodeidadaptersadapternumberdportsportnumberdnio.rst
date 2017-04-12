/v2/compute/projects/{project_id}/vpcs/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/vpcs/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a VPCS instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID
- **adapter_number**: Network adapter where the nio is located
- **port_number**: Port where the nio should be added

Response status codes
**********************
- **201**: NIO created
- **400**: Invalid request
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/compute_post_projectsprojectidvpcsnodesnodeidadaptersadapternumberdportsportnumberdnio.txt


DELETE /v2/compute/projects/**{project_id}**/vpcs/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a VPCS instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID
- **adapter_number**: Network adapter where the nio is located
- **port_number**: Port from where the nio should be removed

Response status codes
**********************
- **204**: NIO deleted
- **400**: Invalid request
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/compute_delete_projectsprojectidvpcsnodesnodeidadaptersadapternumberdportsportnumberdnio.txt

