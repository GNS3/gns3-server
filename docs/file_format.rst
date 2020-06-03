The GNS3 files
===============

.gns3 files
############

GNS3 project files in JSON file format with all
the information necessary to save a project.

A minimal version:

.. code:: json

    {
        "name": "untitled",
        "project_id": null,
        "revision": 5,
        "topology": {},
        "type": "topology",
        "version": "2.0.0"
    }


The revision is the version of file format:

* 9: GNS3 2.2
* 8: GNS3 2.1
* 7: GNS3 2.0
* 6: GNS3 2.0 < beta 3
* 5: GNS3 2.0 < alpha 4
* 4: GNS3 1.5
* 3: GNS3 1.4
* 2: GNS3 1.3
* 1: GNS3 1.0, 1.1, 1.2 (Not mentioned in the file)

The full JSON schema can be found there:

.. literalinclude:: gns3_file.json


.net files
###########

Topology files made for GNS3 <= version 1.0. Not supported.


.gns3p or .gns3project files
#############################

This this a zipped version of a.gns3 file and includes all the required files to easily share a project.
The binary images can optionally be included.

The zip can be a ZIP64 if the project is too big for standard zip file.

.gns3a or .gns3appliance files
##############################

These files contain everything needed to create a new appliance template in GNS3.

A JSON schema is available there:
https://github.com/GNS3/gns3-registry/blob/master/schemas/appliance_v6.json

And samples there:
https://github.com/GNS3/gns3-registry/tree/master/appliances
