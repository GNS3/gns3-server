/v1/projects/{project_id}/qemu/vms
----------------------------------------------------------------------------------------------------------------------

.. contents::

POST /v1/projects/**{project_id}**/qemu/vms
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a new Qemu VM instance

Parameters
**********
- **project_id**: UUID for the project

Response status codes
**********************
- **400**: Invalid request
- **201**: Instance created
- **409**: Conflict

Input
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>acpi_shutdown</td>                    <td> </td>                     <td>['boolean', 'null']</td>                     <td>ACPI shutdown support</td>                     </tr>
    <tr><td>adapter_type</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>QEMU adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>number of adapters</td>                     </tr>
    <tr><td>console</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: telnet, vnc</td>                     </tr>
    <tr><td>cpu_throttling</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>Percentage of CPU allowed for QEMU</td>                     </tr>
    <tr><td>hda_disk_image</td>                    <td> </td>                     <td>string</td>                     <td>QEMU hda disk image path</td>                     </tr>
    <tr><td>hda_disk_image_md5sum</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>QEMU hda disk image checksum</td>                     </tr>
    <tr><td>hdb_disk_image</td>                    <td> </td>                     <td>string</td>                     <td>QEMU hdb disk image path</td>                     </tr>
    <tr><td>hdb_disk_image_md5sum</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>QEMU hdb disk image checksum</td>                     </tr>
    <tr><td>hdc_disk_image</td>                    <td> </td>                     <td>string</td>                     <td>QEMU hdc disk image path</td>                     </tr>
    <tr><td>hdc_disk_image_md5sum</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>QEMU hdc disk image checksum</td>                     </tr>
    <tr><td>hdd_disk_image</td>                    <td> </td>                     <td>string</td>                     <td>QEMU hdd disk image path</td>                     </tr>
    <tr><td>hdd_disk_image_md5sum</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>QEMU hdd disk image checksum</td>                     </tr>
    <tr><td>initrd</td>                    <td> </td>                     <td>string</td>                     <td>QEMU initrd path</td>                     </tr>
    <tr><td>initrd_md5sum</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>QEMU initrd path</td>                     </tr>
    <tr><td>kernel_command_line</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>QEMU kernel command line</td>                     </tr>
    <tr><td>kernel_image</td>                    <td> </td>                     <td>string</td>                     <td>QEMU kernel image path</td>                     </tr>
    <tr><td>kernel_image_md5sum</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>QEMU kernel image checksum</td>                     </tr>
    <tr><td>legacy_networking</td>                    <td> </td>                     <td>['boolean', 'null']</td>                     <td>Use QEMU legagy networking commands (-net syntax)</td>                     </tr>
    <tr><td>mac_address</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>QEMU MAC address</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU VM instance name</td>                     </tr>
    <tr><td>options</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Additional QEMU options</td>                     </tr>
    <tr><td>platform</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: aarch64, alpha, arm, cris, i386, lm32, m68k, microblaze, microblazeel, mips, mips64, mips64el, mipsel, moxie, or32, ppc, ppc64, ppcemb, s390x, sh4, sh4eb, sparc, sparc64, tricore, unicore32, x86_64, xtensa, xtensaeb, null</td>                     </tr>
    <tr><td>process_priority</td>                    <td> </td>                     <td>enum</td>                     <td>Possible values: realtime, very high, high, normal, low, very low, null</td>                     </tr>
    <tr><td>qemu_path</td>                    <td> </td>                     <td>['string', 'null']</td>                     <td>Path to QEMU</td>                     </tr>
    <tr><td>ram</td>                    <td> </td>                     <td>['integer', 'null']</td>                     <td>amount of RAM in MB</td>                     </tr>
    <tr><td>vm_id</td>                    <td> </td>                     <td></td>                     <td>QEMU VM identifier</td>                     </tr>
    </table>

Output
*******
.. raw:: html

    <table>
    <tr>                 <th>Name</th>                 <th>Mandatory</th>                 <th>Type</th>                 <th>Description</th>                 </tr>
    <tr><td>acpi_shutdown</td>                    <td>&#10004;</td>                     <td>boolean</td>                     <td>ACPI shutdown support</td>                     </tr>
    <tr><td>adapter_type</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU adapter type</td>                     </tr>
    <tr><td>adapters</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>number of adapters</td>                     </tr>
    <tr><td>console</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>console TCP port</td>                     </tr>
    <tr><td>console_type</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: telnet, vnc</td>                     </tr>
    <tr><td>cpu_throttling</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>Percentage of CPU allowed for QEMU</td>                     </tr>
    <tr><td>hda_disk_image</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU hda disk image path</td>                     </tr>
    <tr><td>hda_disk_image_md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>QEMU hda disk image checksum</td>                     </tr>
    <tr><td>hdb_disk_image</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU hdb disk image path</td>                     </tr>
    <tr><td>hdb_disk_image_md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>QEMU hdb disk image checksum</td>                     </tr>
    <tr><td>hdc_disk_image</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU hdc disk image path</td>                     </tr>
    <tr><td>hdc_disk_image_md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>QEMU hdc disk image checksum</td>                     </tr>
    <tr><td>hdd_disk_image</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU hdd disk image path</td>                     </tr>
    <tr><td>hdd_disk_image_md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>QEMU hdd disk image checksum</td>                     </tr>
    <tr><td>initrd</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU initrd path</td>                     </tr>
    <tr><td>initrd_md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>QEMU initrd path</td>                     </tr>
    <tr><td>kernel_command_line</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU kernel command line</td>                     </tr>
    <tr><td>kernel_image</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU kernel image path</td>                     </tr>
    <tr><td>kernel_image_md5sum</td>                    <td>&#10004;</td>                     <td>['string', 'null']</td>                     <td>QEMU kernel image checksum</td>                     </tr>
    <tr><td>legacy_networking</td>                    <td>&#10004;</td>                     <td>boolean</td>                     <td>Use QEMU legagy networking commands (-net syntax)</td>                     </tr>
    <tr><td>mac_address</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU MAC address</td>                     </tr>
    <tr><td>name</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU VM instance name</td>                     </tr>
    <tr><td>options</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Additional QEMU options</td>                     </tr>
    <tr><td>platform</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: aarch64, alpha, arm, cris, i386, lm32, m68k, microblaze, microblazeel, mips, mips64, mips64el, mipsel, moxie, or32, ppc, ppc64, ppcemb, s390x, sh4, sh4eb, sparc, sparc64, tricore, unicore32, x86_64, xtensa, xtensaeb</td>                     </tr>
    <tr><td>process_priority</td>                    <td>&#10004;</td>                     <td>enum</td>                     <td>Possible values: realtime, very high, high, normal, low, very low</td>                     </tr>
    <tr><td>project_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>Project uuid</td>                     </tr>
    <tr><td>qemu_path</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>path to QEMU</td>                     </tr>
    <tr><td>ram</td>                    <td>&#10004;</td>                     <td>integer</td>                     <td>amount of RAM in MB</td>                     </tr>
    <tr><td>vm_directory</td>                    <td>&#10004;</td>                     <td>string</td>                     <td></td>                     </tr>
    <tr><td>vm_id</td>                    <td>&#10004;</td>                     <td>string</td>                     <td>QEMU VM uuid</td>                     </tr>
    </table>

Sample session
***************


.. literalinclude:: ../../examples/post_projectsprojectidqemuvms.txt

