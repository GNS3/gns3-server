This directories contain topologies made for previous version of GNS3

Each directory is a GNS3 project. You have two directory inside:
* before 
* after

Before is the state of the project before conversion and after
is the reference for checking if conversion is a success.

To check if file are the same we check the file size except
for .gns3

.gns3 check
###########

The .gns3 json is loaded and compare to the reference project.

You have some special value in the after project:
* "ANYSTR" allow for any string to match
* "ANYUUID" allow for any uuid to match


Run the tests
###############

You can run the tests with:

.. code:: bash

    py.test -vv -x tests/test_topologies.py
