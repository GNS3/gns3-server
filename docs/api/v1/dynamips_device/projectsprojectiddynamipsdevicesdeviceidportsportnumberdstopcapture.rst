/v1/projects/{project_id}/dynamips/devices/{device_id}/ports/{port_number:\d+}/stop_capture
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/dynamips/devices/**{device_id}**/ports/**{port_number:\d+}**/stop_capture
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Stop a packet capture on a Dynamips device instance

Parameters
**********
- **project_id**: UUID for the project
- **device_id**: UUID for the instance
- **port_number**: Port on the device

Response status codes
**********************
- **400**: Invalid request
- **404**: Instance doesn't exist
- **204**: Capture stopped

