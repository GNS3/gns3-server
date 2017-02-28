GNS3 file formats
=================

The .gns3
##########

It's the topology file of GNS3 this file is a JSON with all
the informations about what is inside the topology.

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

* 8: GNS3 2.1
* 7: GNS3 2.0
* 6: GNS3 2.0 < beta 3
* 5: GNS3 2.0 < alpha 4
* 4: GNS3 1.5
* 3: GNS3 1.4
* 2: GNS3 1.3
* 1: GNS3 1.0, 1.1, 1.2 (Not mentionned in the topology file)

And the full JSON schema:

.. literalinclude:: gns3_file.json


The .net
#########
It's topologies made for GNS3 0.8


The .gns3p or .gns3project
###########################

It's a zipped version of the .gns3 and all files require for
a topology. The images could be included inside but are optionnals.

The zip could be a ZIP64 if the project is too big for standard
zip file.

The .gns3a or .gns3appliance
#############################

This file contains details on how to import an appliance in GNS3.

A JSON schema is available here:
https://github.com/GNS3/gns3-registry/blob/master/schemas/appliance.json

And samples here:
https://github.com/GNS3/gns3-registry/tree/master/appliances
