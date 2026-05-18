/v2/templates/{template_id}/base-config/{filename}
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

GET /v2/templates/**{template_id}**/base-configs/**{filename}**
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

.. literalinclude:: ../../../examples/controller_get_templateidbaseconfig.txt


PUT /v2/templates/**{template_id}**/base-config/**{filename}**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Update base configuration file content

Response status codes
**********************
- **200**: File updated
- **404**: File not found

Input
*******

.. raw:: html

    <table>
    <tr>
        <th>Name</th>
        <th>Mandatory</th>
        <th>Type</th>
        <th>Description</th>
    </tr>

    <tr><td>content</td><td>&#10004;</td><td>string</td><td>New file content</td></tr>

    </table>

Output
*******

.. raw:: html

    <table>
    <tr>
        <th>Name</th>
        <th>Mandatory</th>
        <th>Type</th>
        <th>Description</th>
    </tr>

    <tr><td>template_id</td><td>&#10004;</td><td>string</td><td>Template UUID</td></tr>
    <tr><td>filename</td><td>&#10004;</td><td>string</td><td>Base configuration filename</td></tr>
    <tr><td>content</td><td>&#10004;</td><td>string</td><td>Updated file content</td></tr>

    </table>

Sample session
***************

.. literalinclude:: ../../../examples/controller_put_templateidbaseconfig.txt