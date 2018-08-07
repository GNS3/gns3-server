/v2/compute/projects/{project_id}/virtualbox/nodes/{node_id}/adapters/{adapter_number:\d+}/ports/{port_number:\d+}/nio
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/virtualbox/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Add a NIO to a VirtualBox VM instance

Parameters
**********
- **adapter_number**: Adapter where the nio should be added
- **node_id**: Node UUID
- **project_id**: Project UUID
- **port_number**: Port on the adapter (always 0)

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO created
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/compute_post_projectsprojectidvirtualboxnodesnodeidadaptersadapternumberdportsportnumberdnio.txt


PUT /v2/compute/projects/**{project_id}**/virtualbox/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a NIO from a Virtualbox instance

Parameters
**********
- **adapter_number**: Network adapter where the nio is located
- **node_id**: Node UUID
- **project_id**: Project UUID
- **port_number**: Port from where the nio should be updated

Response status codes
**********************
- **400**: Invalid request
- **201**: NIO updated
- **404**: Instance doesn't exist

Sample session
***************


.. literalinclude:: ../../../examples/compute_put_projectsprojectidvirtualboxnodesnodeidadaptersadapternumberdportsportnumberdnio.txt


DELETE /v2/compute/projects/**{project_id}**/virtualbox/nodes/**{node_id}**/adapters/**{adapter_number:\d+}**/ports/**{port_number:\d+}**/nio
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Remove a NIO from a VirtualBox VM instance

Parameters
**********
- **adapter_number**: Adapter from where the nio should be removed
- **node_id**: Node UUID
- **project_id**: Project UUID
- **port_number**: Port on the adapter (always 0)

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: NIO deleted

Sample session
***************


.. literalinclude:: ../../../examples/compute_delete_projectsprojectidvirtualboxnodesnodeidadaptersadapternumberdportsportnumberdnio.txt

