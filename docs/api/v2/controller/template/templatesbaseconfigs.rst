GET /v2/templates/base-configs
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/templates/base-configs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

List all available base configuration files

Response status codes
**********************
- **200**: List of base configuration files returned

Output
*******

.. raw:: html

    <table>
    <tr>
        <th>Name</th>
        <th>Type</th>
        <th>Description</th>
    </tr>

    <tr>
        <td>filename</td>
        <td>string</td>
        <td>Name of the base configuration file</td>
    </tr>

    </table>

Sample session
***************

.. literalinclude:: ../../../examples/controller_get_templatesbaseconfigs.txt