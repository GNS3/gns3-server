/version
------------------------------

.. contents::

GET /version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Retrieve server version number

Response status codes
**************************
- **200**: OK

Output
*******
.. raw:: html

    <table>
    <tr><th>Name</th><th>Mandatory</th><th>Type</th><th>Description</th></tr>
    <tr><td>version</td><td>&#10004;</td><td>string</td><td>Version number human readable</td></tr>
    </table>

Sample session
***************


.. literalinclude:: examples/get_version.txt

