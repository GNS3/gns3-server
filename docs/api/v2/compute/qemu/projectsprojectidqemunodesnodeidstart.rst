/v2/compute/projects/{project_id}/qemu/nodes/{node_id}/start
------------------------------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v2/compute/projects/**{project_id}**/qemu/nodes/**{node_id}**/start
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Start a Qemu VM instance

Parameters
**********
- **project_id**: Project UUID
- **node_id**: Node UUID

Response status codes
**********************
- **200**: Instance started
- **400**: Invalid request
- **404**: Instance doesn't exist

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>adapter_type</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Number of adapters</td>                     </tr>
    <tr><td>bios_image</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU bios image path</td>                     </tr>
    <tr><td>bios_image_md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>QEMU bios image checksum</td>                     </tr>
    <tr><td>boot_priority</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: c, d, n, cn, cd, dn, dc, nc, nd</td>                     </tr>
    <tr><td>cdrom_image</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU cdrom image path</td>                     </tr>
    <tr><td>cdrom_image_md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>QEMU cdrom image checksum</td>                     </tr>
    <tr><td>command_line</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Last command line used by GNS3 to start QEMU</td>                     </tr>
    <tr><td>console</td>                    <td>&#10004;</td>                     <td>['integer', 'null']</td>                     <td>Console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: telnet, vnc, spice, spice+agent, none</td>                     </tr>
    <tr><td>cpu_throttling</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Percentage of CPU allowed for QEMU</td>                     </tr>
    <tr><td>cpus</td>                    <td>&#10004;</td>                     <td>['integer', 'null']</td>                     <td>Number of vCPUs</td>                     </tr>
    <tr><td>hda_disk_image</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU hda disk image path</td>                     </tr>
    <tr><td>hda_disk_image_md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>QEMU hda disk image checksum</td>                     </tr>
    <tr><td>hda_disk_interface</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU hda interface</td>                     </tr>
    <tr><td>hdb_disk_image</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU hdb disk image path</td>                     </tr>
    <tr><td>hdb_disk_image_md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>QEMU hdb disk image checksum</td>                     </tr>
    <tr><td>hdb_disk_interface</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU hdb interface</td>                     </tr>
    <tr><td>hdc_disk_image</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU hdc disk image path</td>                     </tr>
    <tr><td>hdc_disk_image_md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>QEMU hdc disk image checksum</td>                     </tr>
    <tr><td>hdc_disk_interface</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU hdc interface</td>                     </tr>
    <tr><td>hdd_disk_image</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU hdd disk image path</td>                     </tr>
    <tr><td>hdd_disk_image_md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>QEMU hdd disk image checksum</td>                     </tr>
    <tr><td>hdd_disk_interface</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU hdd interface</td>                     </tr>
    <tr><td>initrd</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU initrd path</td>                     </tr>
    <tr><td>initrd_md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>QEMU initrd path</td>                     </tr>
    <tr><td>kernel_command_line</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU kernel command line</td>                     </tr>
    <tr><td>kernel_image</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU kernel image path</td>                     </tr>
    <tr><td>kernel_image_md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>QEMU kernel image checksum</td>                     </tr>
    <tr><td>legacy_networking</td>                    <td>&#10004;</td>                     <td>boolean</td>                     <td>Use QEMU legagy networking commands (-net syntax)</td>                     </tr>
    <tr><td>mac_address</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU MAC address</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU VM instance name</td>                     </tr>
    <tr><td>node_directory</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Path to the VM working directory</td>                     </tr>
    <tr><td>node_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Node UUID</td>                     </tr>
    <tr><td>on_close</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: power_off, shutdown_signal, save_vm_state</td>                     </tr>
    <tr><td>options</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Additional QEMU options</td>                     </tr>
    <tr><td>platform</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: aarch64, alpha, arm, cris, i386, lm32, m68k, microblaze, microblazeel, mips, mips64, mips64el, mipsel, moxie, or32, ppc, ppc64, ppcemb, s390x, sh4, sh4eb, sparc, sparc64, tricore, unicore32, x86_64, xtensa, xtensaeb, null</td>                     </tr>
    <tr><td>process_priority</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: realtime, very high, high, normal, low, very low</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project UUID</td>                     </tr>
    <tr><td>qemu_path</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Path to QEMU</td>                     </tr>
    <tr><td>ram</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Amount of RAM in MB</td>                     </tr>
    <tr><td>save_vm_state</td>                    <td> </td>                     <td>['boolean', 'null']</td>                     <td>Save VM state support</td>                     </tr>
    <tr><td>status</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: started, stopped, suspended</td>                     </tr>
    <tr><td>usage</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>How to use the QEMU VM</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../../examples/compute_post_projectsprojectidqemunodesnodeidstart.txt

