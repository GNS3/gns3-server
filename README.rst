GNS3-server-zstdsnap
===========

This is a branch off of the GNS3 2.1.21 release to support much faster snapshotting
of large projects by replacing zipstream with the facebook zstandard streaming 
compressor: https://github.com/facebook/zstd

The python-zstandard library is used for this purpose: 
https://github.com/indygreg/python-zstandard

The zstandard library provides multi-threaded compression and much more tunable 
compression settings which provide much improved speed and compression ratios.

The zstandard compression will ONLY be applied to newly created *snapshots*. This branch
has full interoperability with standard GNS3 snapshots and will just use the existing
zipstream code to import those. Standard project import/export will also use the
standard zip format; this is to maintain portability.

Performance
--------

Using a 154GB source project-files directory, we can see a dramatic difference in
compression time and ratio between zipstream and zstandard. The machine doing the
compression has the following specs:

Intel(R) Xeon(R) CPU E5-2620 v4 @ 2.10GHz with 32 (hyper-threaded) cores
128GB RAM
NFS backing storage (limits write throughput to ~1Gbit)

The limiting factor with the above machine is the storage speed. As such, I have
tweaked the compression parameters to use long range matching and a higher
compression level to produce a smaller result rather than focusing purely on
speed. On an appliance with direct SSD storage the compression, the compression
strategy can be modified to prioritize speed.

.. image:: https://user-images.githubusercontent.com/39999922/69082867-fbe30300-0a0e-11ea-9967-68ee21c2e92e.png
.. image:: https://user-images.githubusercontent.com/39999922/69083023-511f1480-0a0f-11ea-901a-f62268228bb5.png

zipstream compressed the project in just over 2 hours with a compression ratio of ~2.2 whereas
zstandard compressed the project in 30 minutes with a compression ratio of ~4

Default Settings
--------

The default compression settings are designed for an appliance with ample memory and CPU power, where the primary concern is to produce a file with better compression ratio while still beating zipstream on speed.

The compression level can be changed in the snapshot.py file by modifying the compression params:

/usr/share/gns3/gns3-server/lib/python3.5/site-packages/gns3server/controller/snapshot.py

.. code-block:: python
    
    def _create_snapshot_zs(self, filelist):
        """
        Creates new zstandard format snapshot file (to be run in its own thread)
        """
        #create zstandard compressor to use as many threads as logical cpus
        params = zstd.ZstdCompressionParameters.from_level(11,threads=-1,enable_ldm=True,window_log=31)
        cctx = zstd.ZstdCompressor(compression_params=params)

A list of parameters is available here: https://github.com/indygreg/python-zstandard 

With more detailed parameters described here: https://github.com/facebook/zstd/blob/dev/lib/zstd.h

For example, to maintain multi-threading and lower the memory usage/CPU usage requirements one can reset to the default level:

.. code-block:: python

        params = zstd.ZstdCompressionParameters.from_level(3,threads=-1)
        
