/v2/compute/qemu/img
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/qemu/img
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a Qemu image

Response status codes
**********************
- **201**: Image created

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>adapter_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: ide, lsilogic, buslogic, legacyESX</td>                     </tr>
    <tr><td>cluster_size</td>                    <td> </td>                     <td>integer</td>                     <td></td>                     </tr>
    <tr><td>format</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: qcow2, qcow, vpc, vdi, vmdk, raw</td>                     </tr>
    <tr><td>lazy_refcounts</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: on, off</td>                     </tr>
    <tr><td>path</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Absolute or relative path of the image</td>                     </tr>
    <tr><td>preallocation</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: off, metadata, falloc, full</td>                     </tr>
    <tr><td>qemu_img</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Path to the qemu-img binary</td>                     </tr>
    <tr><td>refcount_bits</td>                    <td> </td>                     <td>integer</td>                     <td></td>                     </tr>
    <tr><td>size</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Image size in Megabytes</td>                     </tr>
    <tr><td>static</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: on, off</td>                     </tr>
    <tr><td>subformat</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: dynamic, fixed, streamOptimized, twoGbMaxExtentSparse, twoGbMaxExtentFlat, monolithicSparse, monolithicFlat</td>                     </tr>
    <tr><td>zeroed_grain</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: on, off</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_post_qemuimg.txt


PUT /v2/compute/qemu/img
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Update a Qemu image

Response status codes
**********************
- **201**: Image Updated

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>extend</td>                    <td> </td>                     <td>integer</td>                     <td>Number of Megabytes to extend the image</td>                     </tr>
    <tr><td>path</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Absolute or relative path of the image</td>                     </tr>
    <tr><td>qemu_img</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Path to the qemu-img binary</td>                     </tr>
    </table>

