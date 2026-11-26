# Startup configurations

Startup configurations let a GNS3 project keep reusable device configurations
(**configuration sets**), capture them from running or stopped nodes, deliver
them when a node starts, and **wipe** a node back to its base image. Saving a
configuration in GNS3 never changes a running device by itself.

## Architecture overview

| Layer | Role |
| --- | --- |
| Controller (`controller/configurations.py`, `controller/configuration_rpc.py`) | Project-level state: sets, per-node selections, capture/apply jobs, wipe. Talks to computes through the shared helper in `configuration_rpc.py`. |
| Compute (`compute/configurations.py`, `api/routes/compute/configurations.py`) | `ConfigurationService`: export, import, apply, wipe on the node that owns the emulator. |
| Services (`services/configurations/`) | The console session (`console/session.py`: the telnet logic, and the entry point of the isolated subprocess that runs it), `session_runner.py` (leases a node's console and starts that subprocess), console recipes (`console/recipes/config_<device>.py`), boot media profiles (`boot_media/`), `sets/` (the persisted configuration sets in `store.py`, the per-node assignments in `selections.py` and the ZIP set archives in `archive.py`). The node and device types that may start from an entry are decided in `schemas/configurations.py` (`STARTUP_ENGINES`, `compatible_device_type`). |
| Boot media (`services/configurations/boot_media/`) | Profile catalog, ISO and FAT image builders, disk preparation, staging, and QEMU attachment. See [Native boot media](#native-boot-media). |
| Shared code (`services/configurations/shared/`) | `errors.py`: the single registry of public error codes, user messages, validation fields and HTTP statuses. `failure_context.py`: the masked context of a failed console step. `safe_io.py`: bounded, atomic, link-safe file I/O. `node_lease.py`: the per-node lifecycle lock (start, stop, reload, wipe and console apply never overlap). `startup_journal.py`: the per-node runtime journal (`.startup-runtime.json`) that decides whether a start applies the saved startup. |

Set capture and live apply are in-memory jobs (`state(project)["jobs"]`). They are
lost when the controller restarts, and closing a project cancels its running apply
tasks; saved sets and assignments are stored in the project and are not affected.

### How a node starts

- **Native engines** (Dynamips, IOU/IOL, VPCS, the generic Docker network
  file, and Docker FRR): the controller places the configuration where the guest expects it
  before launch. After a runtime has booted, ordinary Stop/Start keeps its saved
  state; a new set or an OFF switch takes effect only after **Wipe**. Nodes
  without a runtime journal are treated as having saved state.
- **Native boot media** (QEMU nodes with `startup_media_profile`): the compute stages the
  configuration as a CD-ROM, a FAT disk, or files on the node's own disk, depending on
  the profile. See [Native boot media](#native-boot-media) for supported appliances and requirements.
- **Console restore** (every other QEMU appliance): after the first start following a Wipe, a worker replays the config
  through the Telnet/SSH console, holding an exclusive console lease. Ordinary
  restarts do not replay. Replay usually merges into the existing configuration.

Without a boot media profile a QEMU node has no pre-boot delivery: no media is built
and no guest disk is edited. It can have startup enabled when the console
rule holds:

1. its **Netmiko device type** names a console recipe (see the table below),
2. the saved entry's device type matches that recipe, and
3. its console type is Telnet or SSH.

Otherwise Start and Wipe refuse with `device_type_required`,
`device_type_unsupported`, `configuration_profile_mismatch` or
`configuration_restore_console_required` instead of silently booting a factory
configuration. Wipe resets the node's linked-clone overlays (and UEFI variables).

## Concepts

| Term | Meaning |
| --- | --- |
| Configuration set | Named collection of node configurations stored in the project (max 32; `Default` is protected; names are unique ignoring case). Each entry has its own startup ON/OFF flag. |
| Startup set | The set assigned to a node (assignment `none` or `set`). Different nodes can use different sets. |
| Console device type | Netmiko-style driver used for console capture and replay, taken from the node's Netmiko device type. |

Netmiko names are mapped to the existing recipes, so appliances need no recipe of
their own: `cisco_asa`, `cisco_asa_ssh` and `cisco_asa_telnet` (ASAv) use the ASA
recipe; `cisco_ios`, `cisco_xe`, `cisco_xe_ssh` and `cisco_xe_telnet` (IOSv,
Catalyst 8000v in autonomous mode, CSR 1000v) use the IOS recipe; the `_telnet`
variants of the other recipes (NX-OS, IOS XR, RouterOS, Viptela, PAN-OS, EOS and Junos (capture only)) are
aliases of their base recipe (`normalize_device_type`). Only the platforms that were
verified have a recipe: pfSense, SR OS and AOS-CX were removed and
come back one at a time, each tested on a real image. Replay merges into the running
configuration. Appliance workflows that require native bootstrap or an unsupported
first-login interaction, such as a forced password change, need the appropriate
boot-media profile or manual guest setup.

## API summary

All routes are under `/v3/projects/{project_id}`. Rows marked UI are used by the
web interface.

| Method and path | Purpose | UI |
| --- | --- | --- |
| `GET /v3/startup-media-profiles` (not project scoped) | Catalog of boot media profiles `[{id, title, device_type, description}]` | yes |
| `GET /startup-configurations` | Current sets document | yes |
| `PUT /startup-configurations` | Replace the sets document (revision checked) | yes |
| `POST /startup-configurations/sets` | Create an empty set | yes |
| `PUT /startup-configurations/selections` | Assign a set or clear startup for a list of nodes (assignment revision checked) | yes |
| `GET /startup-configurations/sets/{id}/export?revision=N` | Portable ZIP archive of a set at the requested revision | yes |
| `POST /startup-configurations/import` | Import a ZIP archive as a new set | yes |
| `POST /startup-configurations/capture` | Capture nodes into a set (202, job) | yes |
| `GET /startup-configurations/status` | Capture/apply job and per-node status | yes |
| `POST /nodes/{id}/configuration-apply` | Apply a saved entry to a running node (202) | yes |
| `POST /nodes/{id}/configuration-export?save_to_set=false` | Download a node configuration. Setting `save_to_set=true` also saves a usable entry into the project default set. | yes |
| `POST /startup-configurations/wipe` | Wipe nodes (see below) | yes |

All rows are used by the web interface.

The following routes are internal controller-to-compute calls under
`/v3/compute/projects/{project_id}/{node_type}/nodes/{node_id}`. A compute without
these routes returns 404.

| Method and path | Purpose |
| --- | --- |
| `POST /configuration-export` | Read configuration bytes from the selected source |
| `POST /configuration-apply` | Prepare native files for startup or replay configuration through the console |
| `GET /configuration-startup-state` | Check the node's runtime journal |
| `POST /configuration-withdraw` | Withdraw an unused native file preparation |
| `POST /configuration-media/preflight` | Check the profile, its required tools, and its attachment slot before a wipe |
| `POST /configuration-media` | Stage startup media or withdraw it when the content is null |
| `POST /configuration-wipe/preflight` | Check whether the node's runtime state can be reset |
| `POST /configuration-wipe` | Reset the stopped node's runtime state |

## Native boot media

Some appliances read their configuration from a CD-ROM on their first boot. IOSv
and IOSvL2 read a small FAT disk, and vEOS reads the prepared flash partition of its
own disk. A QEMU node or template with `startup_media_profile` set uses the
profile's delivery method. QEMU nodes without a profile use console restore for
supported entries. The saved entry's `device_type` matches the profile
(`cisco_ios_telnet` for the C8000v and IOSv, `cisco_viptela` for Viptela, `paloalto_panos` for PAN-OS, `arista_eos` for vEOS, `juniper_junos` for vSRX NG, `cisco_asa` for ASAv, `cisco_nxos` for Nexus 9000v, `cisco_xr` for IOS XRv 9000), so console
capture/export keeps working; its content is the text the profile turns into media.

### How it works

1. **Start** (stopped node, entry enabled): the controller calls the compute route
   `POST /v3/compute/projects/{project}/qemu/nodes/{node}/configuration-media`
   with `{"profile": "<id>", "content": "<entry text>"}`. A node that has no entry
   (or a disabled one) sends `content: null`, which withdraws previously staged media.
2. The compute stages the profile's files as `startup-media.iso` with `iso_builder.py`,
   as `startup-media.img` with `disk_builder.py`, or in a prepared overlay for a disk-only
   profile. An ISO needs `xorrisofs`, `genisoimage`, or `mkisofs`. A FAT image needs
   `mformat` and `mcopy` from mtools. The runtime journal changes to `prepared` when
   staging succeeds. The reply is `{"staged": true|false}`.
3. **Launch**: for an ISO, QEMU uses the first free IDE CD-ROM slot (index 2 or 3).
   For a FAT image, QEMU attaches an extra virtio disk after the node's own disks.
   A disk-only profile starts with its prepared overlay. QEMU keeps the existing boot order.
   Once the guest runs, the compute records `initialized`. Later Stop/Start keeps
   the guest's saved state and starts without the staged CD-ROM or FAT disk.
4. **Edits** to the entry or set before that first boot are staged again on every Start. After
   the guest booted they take effect only after **Wipe**, which removes the media and the
   linked-clone overlays and marks the journal `clean`, so the next Start stages again.
   A node that already ran before this feature (overlay disks, no journal) is not staged
   silently: it needs one Wipe first. A node that never ran is staged straight away. When nothing is staged because the guest
   already ran, the node status shows `saved_state_kept` (an informational notification, not an error): Wipe, then Start.
   It is sent when an entry changed since it was last delivered or reported, not on every restart of an unchanged node
   (the controller remembers a digest per node; it forgets it on Wipe and on a controller restart, which can repeat the
   notice once).

A launch that fails before QEMU runs leaves the journal `prepared`, so the next attempt
can use the media again. Once QEMU is running, the preparation is consumed even if a
later startup step fails.

A media failure stops the Start before the guest launches. Start returns an error that
names the cause, the node status (`GET .../startup-configurations/status`, `nodes[<id>]`)
shows `{"status": "<code>", "set_id": "..."}` with one of the registered codes below, and
the project notification carries the same text. A successful stage shows `prepared`.
After launch the controller reports `media_delivered`. This confirms delivery to the
guest. Check the guest console or running configuration for the result of its import.

Nodes with a profile need no Telnet/SSH console and no Netmiko type for startup; they still
need them for export and live apply.

### Profiles (`GET /v3/startup-media-profiles`)

| Profile id | Entry device type | Media | Verified on |
| --- | --- | --- | --- |
| `juniper-vsrx` | `juniper_junos` | `juniper.conf` (the entry text, unchanged), label `CONFIG` | vSRX 3.0 23.2R1.13: hostname and the rest of the captured configuration committed at the first boot; also a minimal text without `root-authentication` |
| `arista-veos` | `arista_eos` | `startup-config` (the entry text, LF line endings) written into the flash partition of the node's own disk; no media is attached | vEOS-lab 4.37.0F (stock, single disk): hostname, user and interface description applied at the first boot with ZeroTouch off; the file is on the flash, so the node's own `write memory` saves persist |
| `cisco-asav` | `cisco_asa` | `day0-config` (the entry text; see the enable password below), label `cidata` | Not verified on a real ASAv image; the previous implementation of the same approach worked |
| `cisco-cat9kv` | `cisco_ios_telnet` | `iosxe_config.txt` (the entry text, unchanged), label `GNS3_BOOT` | Catalyst 9000v 17.12: startup config restored at the first boot after a Wipe (confirmed on a GNS3 node); the first boot is slow |
| `cisco-c8000v-autonomous` | `cisco_ios_telnet` | `iosxe_config.txt` (the entry text, unchanged), label `GNS3_BOOT` | C8000v 17.18.03a autonomous (hostname and interface in `show running-config`, about 2.5 min to the prompt) |
| `cisco-c8000v-controller` | `cisco_ios_telnet` | `ciscosdwan_cloud_init.cfg`, label `CONFIG` | C8000v 17.18.03a controller after a config reset (hostname, `username`, system-ip, site-id, org, vbond visible; see the prerequisite) |
| `cisco-iosv` | `cisco_ios_telnet` | Disk media: `ios_config.txt` (the entry text) and `ios_config_checksum` (its MD5) on a FAT disk, label `IOSCFG` | IOSv-L3 15.9(3)M12 and IOSvL2 15.2 (20200929): `% Applying bootstrap config from flash2:...`; a `show running-config` capture delivered back to a fresh IOSv-L3 gave an identical running configuration |
| `cisco-iosxrv9k` | `cisco_xr` | `iosxr_config.txt` (the entry text, LF line endings; see the admin account below), label `config-1` | XRv 9000 26.1.1: bootstrap applied by CVAC after the first boot; a `show running-config` capture delivered back to a fresh VM (see below) |
| `cisco-nxosv9k` | `cisco_nxos` | `nxos_config.txt` (the entry text, LF line endings; see the admin account below), label `CONFIG` | Nexus 9000v 10.5(5): bootstrap applied at the first boot (about 4 min to the login prompt); a `show running-config` capture delivered back gave an identical running configuration (banner, VLAN, loopback, admin hash) |
| `cisco-viptela` | `cisco_viptela` | NoCloud seed: `user-data` + `meta-data`, label `cidata` | vSmart, vBond and vManage 20.18.5 (host-name, system-ip, organization, vbond in `show running-config`); real 128-line vSmart export with SNMPv3 users, vpn 0/512 and banner applied completely |
| `paloalto-panos` | `paloalto_panos` | Bootstrap package on an ISO (label `PAN_BOOT`): `config/bootstrap.xml` (the entry text, XML), `config/init-cfg.txt` (derived), empty `content/`, `license/`, `software/` | PAN-OS VM-Series 11.2.12: hostname and management address from the XML applied, `show system bootstrap status` all successful, injected admin password logs in without the forced change (about 2.5 min from the host login to the firewall prompt) |

**ASAv.** The guest copies `day0-config` to its startup-config only while that is empty, and the
distributed image already holds startup state in its encrypted store. Staging therefore also prepares the
node's disk: a disposable VM boots the image with the vendor's recovery entry (`with no configuration load`),
runs `write erase` and reloads, and the erased overlay is cached once per base image in
`<config dir>/startup-media-cache/` (shared by every ASAv node of that image) and copied to the node's
`hda_disk.qcow2`. Only the first ASAv node per image pays for the recovery boot (several minutes; the
controller waits up to 420 s); later wipes and other nodes only copy the cached overlay. The guest's boot
script only sees the CD-ROM on the `pc` machine type (not on `q35`, the default), so a node with this profile
is started with `-machine pc` unless its options name a machine. The node needs `/dev/kvm`, at least 2048 MB
of RAM and a virtio disk (`configuration_topology_unsupported`); a failed recovery boot is reported as
`configuration_factory_reset_failed` and its console log is kept in the node folder (`.asav-recovery/`).
The base image is only ever a read-only backing file.

The enable password: a listing pasted from `show running-config` prints it as `enable password ***** pbkdf2`, which the guest cannot load. When the text has no usable `enable password` line, the node's saved default password (the Netmiko credentials of the node, also its enable secret) is written as `enable password <password>` in plain text on the media (the media file is private to the node folder); a password with spaces or control characters is not used. A usable line in the text always wins.

**IOSv and IOSvL2 (disk media).** These images have no CD-ROM driver (`show file systems` lists no CD device).
Their bootstrap reads `ios_config.txt` from a second **virtio disk** holding a FAT filesystem, prints
`% Applying bootstrap config from flash2:...` and applies the file as CLI configuration. The `cisco-iosv` profile therefore
uses the `disk` media kind: the compute builds a 1 MiB raw disk (an MBR with one FAT partition, the layout of the disk the
vendor's own `IOSv_startup_config.img` has) with `mformat` and `mcopy` (mtools), stores it as `startup-media.img`
and attaches it as a virtio disk at the first free index of 1 to 3 (`if=virtio,index=1,media=disk`) for the first boot after
a wipe only. It is placed on the command line after the node's own disks: virtio disks take their PCI slots in command-line
order and the firmware boots the first one, so a media disk listed first leaves the node without a console. `ios_config_checksum` holds the MD5 of `ios_config.txt` (hash plus a newline). The text must be at most
900 KiB for the disk (`boot_media_too_large`). IOS needs no account in the file (the console line has no login by default), so
the node's saved password is not used.

`show running-config` prints a banner delimiter as the two characters `^C`, which a configuration file does not read as one
delimiter (the banner text would gain a `C`). Like the console replay, the profile rewrites every banner with a plain delimiter
that is not part of its text (one of `% ~ | @`); a banner it cannot close, or one that uses all four, is refused with
`configuration_invalid_content`. A node created from the appliance already has the vendor's own startup disk as `hdb` (virtio index 1, a
default configuration); the media then takes index 2 and IOS applies it, not the vendor's (checked on IOSv-L3: two extra
disks showed as `flash1:` and `flash2:`, and the config of the media was the one in effect). A node whose second disk slots
(hdb to hdd, or the config disk) are all virtio and in use cannot take the media and Start reports an error.

Export (Fetch from device) uses the `cisco_ios_telnet` console recipe, which parses a real IOSvL2 and IOSv-L3 `show running-config`
unchanged. IOSvL2 builds that listing slowly (about 4 s for a small configuration, other commands answer at once).

**IOS XRv 9000.** The image's host layer reads `iosxr_config.txt` from the CD-ROM and hands it to the XR VM as
`/etc/sysconfig/iosxr_config.txt`; its CVAC step applies it (the commit shows `by CVAC`). Things that decide whether it works:

- *Admin user.* CVAC only runs while no username is configured, and the file must create one. Without a user the console
  asks `Enter root-system username:` (Administrative User Dialog) and nothing of the file is applied. A capture of
  `show running-config` already holds `username <name> ... secret 10 <hash>` and loads unchanged. When the text has no user
  with a loadable secret (none, or a masked `*****` secret), the node's saved console password becomes
  `username admin` (groups `root-lr` and `cisco-support`) with `secret 0 <password>`, which XR stores as a `$6$` hash, and any
  unusable user block is removed. A password with spaces or control characters is not used; with no saved password the
  guest asks for one on the console.
- *Do not use the console early.* CVAC starts about three minutes after the XR prompt text `Press RETURN to get started.`
  (it waits for the traffic interfaces) and retries a locked configuration for 2.5 minutes only. Pressing Enter on the
  console opens the Administrative User Dialog, which holds the configuration lock: CVAC then gives up and the file is
  not applied. Leave the console alone until the login prompt `Username:` shows (or the dialog, if no user was created).
  A failed attempt cannot be retried by reloading: CVAC stores a checksum of the file it handled and skips an unchanged
  file (`Checksum unchanged since last applied`), so the second boot shows the dialog again although the file is present.
  Recover with Wipe and Start (a fresh disk has no checksum). The node's CVAC log is `disk0:/cvac.log` (`run cat /disk0:/cvac.log`).
- *Data adapters.* CVAC waits for a traffic interface (`GigabitEthernet0/0/0/x`). With 3 adapters none appeared and CVAC
  waited forever; the template's 7 adapters work.
- *Memory.* Give the node at least 20 GB of RAM. With less, the first boot of a fresh disk (after a Wipe too) can stop
  after the host's SELinux relabel (`Relabel done, rebooting the system. Running in chroot, ignoring request.`) with a
  silent console. If that happens, raise the RAM, then Wipe and Start.
- Capture and export use the `cisco_xr` console recipe.

**Nexus 9000v.** The guest finds `nxos_config.txt` on the CD-ROM, waits for its ethernet module and applies the
file as CLI (`The bootstrap configure is applied successfully` on the console). The file has to define the `admin`
account; without one the guest stops at its *System Admin Account Setup* dialog. A capture of `show running-config`
already has `username admin password 5 <hash>` and loads unchanged. When the text has no usable admin line (none, a
masked `*****` secret or the factory `!` hash), the node's saved console password becomes the admin password:
`no password strength-check` and `username admin password <password> role network-admin` are placed first and any
unusable admin line is removed. The strength policy is switched off on purpose: with a plain password that fails it
(for example `cisco123`) the line is rejected silently and nobody can log in. This changes the saved device
configuration (the `no password strength-check` line shows in `show running-config`). A password with spaces or
control characters is not used; with no saved password the guest asks for one on the console. Capture and export use the
`cisco_nxos` console recipe.

**C8000v controller mode.** A text that already contains a `MIME-Version:` header (a bootstrap
generated by SD-WAN Manager) is used byte for byte. Anything else is treated as the device's
SD-WAN CLI configuration and wrapped in a multipart MIME file: a `text/cloud-config` part with
`vinitparam` (`uuid: C8K-<node id>`, `otp` of zeros, `vbond` and `org` taken from the `system`
section, otherwise `0.0.0.0` / `gns3-lab`, `rcc: true`) and a `text/cloud-boothook` part that holds the CLI text unchanged.
This is a lab bootstrap that does not enrol with Manager. **Prerequisite:** the guest only reads the
bootstrap when its SD-WAN database is empty. A controller image that was booted and saved once
reports `LOAD_DAY0_CONFIG=false` and ignores the media; run
`request platform software sdwan config reset` on it once (it reloads) with the media attached, or
use an image that was never initialized. A clean 17.18.05 controller-capable image that had not completed its first boot applied the bootstrap through the media. A controller image that was derived by booting into controller mode and committing the disk into the base image is already initialized and ignores the bootstrap until the reset. The decision is not derived from the guest identity: on the shipped image a different `-uuid`, SMBIOS serial numbers
(system, chassis and board) and an extra `/.boot_day_0` marker on the bootflash filesystem all still log `LOAD_DAY0_CONFIG=false`.
After `config reset` the image differs in a LUKS-encrypted partition and the object store, so there is no offline or
launch-time switch the server can set; the reset needs a login on the initialized image. The bootstrap replaces the
guest account configuration. Include a valid top-level `username` line in the saved CLI text for the account
you will use. The node's saved Netmiko credentials are used to sign in to an existing guest account. If the
assigned CLI text has no `username` line, preflight reports `configuration_login_required` before stopping or
wiping the node. Add a valid account to the assigned text or turn startup off before retrying. A Manager
bootstrap is delivered unchanged.

**vSRX NG.** The vSRX 3.0 image has a first-boot script, `/etc/vsrx.configdrive`, that looks for a config drive: an
attached CD-ROM (`/dev/cd0`), a USB disk or a virtio drive. When a CD-ROM carries no OpenStack metadata
(`openstack/latest/meta_data.json`) the script copies its root `juniper.conf` to `/config` and `mgd` commits it as the
initial configuration (`Found CDROM device.` and `mgd: commit complete` on the console). It does this once and skips every
later boot, which is what the profile relies on: the entry text is stored unchanged as `juniper.conf` on a CD-ROM
that is attached for the first boot after a Wipe only. The text is the hierarchical configuration `show configuration`
prints (braces balanced; `set` commands, an unbalanced text or text without any `{` are refused with
`configuration_invalid_content` when staged, because a file that fails to load is not tried again); its `##` comments (the
`Last commit` header, `## Warning`, `## SECRET-DATA`) are ignored by the loader. Both a
captured configuration and a minimal one with only `host-name` committed on a real vSRX; a text without
`root-authentication` still commits, and `root` then logs in without a password (the factory state). The export is the
capture-only `juniper_junos` console recipe: the login lands in the shell (`root@:~ #`), the recipe sends `cli` once,
runs `set cli screen-length 0` and `set cli screen-width 0`, then `show configuration | no-more`, and checks that the braces
balance. Live apply of a Junos entry is always refused.

**vEOS.** A stock vEOS image (`vEOS-lab-*.qcow2`: Aboot and one ext4 flash partition on a single disk, as the GNS3
appliance uses it) has no startup-config on its flash, so it starts ZeroTouch Provisioning, and it reads no config
drive. The profile writes the entry into the flash instead, offline and before the first boot: Start converts the
base image to raw, copies its one Linux partition into a private file, runs `e2fsck -p -f` on it (a pending journal
is replayed first), writes `/startup-config` with `debugfs` and reads it back, then stores only the blocks that
changed in a small qcow2 overlay of the base image (well under 1 MiB for the stock image; the shared image is never
written) that replaces the node's `hda_disk.qcow2`. No media is attached, no mount and no root are needed. EOS finds the
startup-config, so ZeroTouch stays off, and the node keeps its own saves across restarts (`write memory`). A Wipe
returns the node to the factory image, which starts ZeroTouch again. The node must be a linked clone with the flash on its first disk (no second drive, no Aboot ISO). The flash is the ext4
partition of the MBR that holds `boot-config`: the first one, or the second behind the Aboot partition as in the stock
images, in which case `zerotouch-config` (`DISABLE=True`) is written too, as EVE-NG does. A disk with no such partition is
refused with `configuration_topology_unsupported`. The host needs `debugfs` and `e2fsck`
(e2fsprogs) and `qemu-io` (next to `qemu-img`; without it the whole edited disk is converted, which is slower and
larger). The base image must be a qcow2 (as the stock vEOS-lab images are); another format is refused with `configuration_topology_unsupported`. Each external tool may run for up to 150 s (a build of any other media is limited to 60 s), the overlay is compared with the edited disk before it is used, and a scratch directory (`.prepare-*` in the node folder) that a killed server left behind is removed at the next staging. Withdrawing the entry before the first boot drops the prepared disk. The export is the capture-only
`arista_eos` console recipe: `terminal length 0`, `terminal width 511`, then `show running-config`, saved as printed
(its `! Command` header and trailing `end` included). Live apply of an EOS entry is always refused. Entries need no
admin account of their own: `admin` still logs in without a password when the text defines other users.

**PAN-OS.** A VM-Series firewall in factory state looks for a bootstrap package on an attached CD-ROM at its first
boot. The profile builds it: `config/bootstrap.xml` is the entry text, `config/init-cfg.txt` is derived from it, and
`content/`, `license/` and `software/` are empty directories (the package layout requires them). PAN-OS gives the values of
`init-cfg.txt` precedence over the XML, so they follow the document: `type=dhcp-client`, or `type=static` with the
management `ip-address`, `netmask` and `default-gateway` (and the IPv6 pair) when the XML has a static address (an
incomplete or invalid one is refused); `op-command-modes=jumbo-frame` when an interface MTU is above 1500 (that mode is
local state the XML does not restore, and the first commit is rejected without it); and
`plugin-op-commands=advance-routing:enable` when advanced routing is on. The entry text is
the XML `<config>` document the device prints, either alone, with an XML declaration, or inside the CLI's
`<response><result>` envelope (removed). Anything that is not one well-formed `<config>` document is refused with
`configuration_invalid_content`; DTDs, entities and processing instructions are never accepted.
*Admin account.* The bootstrap configuration replaces the factory one, so it has to define an administrator that
can log in. A text captured from a device already carries `<phash>` for its users and is delivered unchanged. A text
with no usable superuser (a non-`__` user with a `phash`) gets `admin` added, hashed from the node's saved console
password with SHA-256 crypt (`$5$`), when the node saves a usable password; without one the text is delivered as it is.
The export is the capture-only `paloalto_panos` console recipe: `set cli pager off`, `set cli scripting-mode on`, `set cli
op-command-xml-output on`, then `show config running`, saved as `running-config.xml`. A node that still asks for its
forced first-login password change cannot be captured (`console_not_ready`); log in once and set the password.
Live apply of a PAN-OS entry is always refused.

The node boots with a `PA-HDF login:` prompt for about two minutes while the bootstrap runs, then shows the configured
hostname. Logins are refused until then. Verified on a hand-started copy of the image with the node's own layout; a
copy started without `-uuid` (GNS3 always passes one) never left that state, so the UUID is a likely requirement.
A captured configuration whose `admin` still has the factory password hash asks for the first-login password change
again after the bootstrap.

**Viptela.** The images run stock cloud-init and detect the NoCloud seed on the CD-ROM. The
`user-data` is `#cloud-config` carrying the CLI text as a base64 `write_files` entry plus a small loader
that is started in the background (ConfD only starts after cloud-init finishes). The loader waits for
ConfD and runs `confd_load -l -m -F c` (a merge). ConfD's helper scripts are not ready right after
`confd --wait-started`: an early load of a configuration with SNMPv3 users fails as a whole with
`snmp/user{...}/auth-password: Failed to set usmUserAuthKey ... vconfd_script_usmentry.sh ... echo: write error`
(no part of the configuration is applied, even with a valid encrypted password). The loader therefore retries
every 10 s, up to 40 times, for that class of errors (`usmentry`, `Failed to set usm`, lost or refused ConfD
connections, locks); any other error is final. When the text has top-level `vpn <n>` sections it is loaded with
`-p /vpn`, which replaces the factory `vpn 0`/`vpn 512` (`values are not unique: eth0` otherwise) in one transaction.
The outcome is always printed on the serial console: `GNS3: startup configuration applied.` or
`GNS3: startup configuration FAILED: <first ConfD error, hashes replaced by <hash>> (see /var/lib/gns3-startup/import.log)`.
The node status is `media_delivered` once the node starts with the media attached. Check the serial console for the
guest's import result. ConfD applies the main configuration in one transaction and rolls it back if a statement is
rejected. A text without `vpn` sections is merged into the factory VPNs.

*Admin account.* The loader provisions `admin` first, in its own transaction, so the password is in place before the
main configuration is merged. The password is chosen in this order: (1) the text's own
`system / aaa / user admin / password <hash>` (a `$n$...` hash as printed by `show running-config`; a plaintext value is
ignored and removed from the merged text, because ConfD stores it verbatim and the account becomes unusable); (2) otherwise the node's saved console
password (node settings: default username `admin` or empty, default password other than `admin`), which the server
hashes with sha512-crypt (`$6$`) before building the media, so only the hash is on the ISO; the compute route carries the
password in the optional secret field `admin_password` of `configuration-media`, which is never logged, never part of
a response and not sent for other profiles; (3) otherwise the factory `admin/admin` stays and the guest asks for a new
password at its first console login, as the factory image does. Other `aaa user` entries of the text are merged by the main
transaction. Verified on a real vSmart 20.18.5: with the 128-line SNMPv3 export (no admin user) and a saved password,
`admin` plus that password logs in directly (no password-change dialog) and `admin/admin` is rejected; with the
57-line export the text's admin hash is used (the node password is then rejected); with no usable saved password
`admin/admin` still works and the change dialog appears. Other accounts defined with hashes (e.g. a `netadmin` user)
log in directly too.

### Boot media files

| File | Role |
| --- | --- |
| `boot_media/media_profile.py` | The profile contract (`BootMediaProfile`, `MediaContext`) and the text checks (`checked_text`, `cli_text`) |
| `boot_media/profiles/*.py` | One module per device, with everything specific to it: the text to files rendering and, where needed, its own helpers (the ASAv erased disk, the Viptela `$6$` password hashes) |
| `boot_media/profiles/__init__.py` | The known profiles and the catalog served to clients |
| `boot_media/staging.py` | Stages or withdraws a node's media for the next boot, driven by the runtime journal; wipe paths |
| `boot_media/iso_builder.py` | Builds the ISO9660 image (media kind `cdrom`) with the host's mastering tool |
| `boot_media/disk_builder.py` | Builds the small FAT disk (media kind `disk`) with mtools |
| `boot_media/qemu_attachment.py` | The QEMU `-drive` option and IDE slot choice at launch |
| `api/configuration_route.py` | Route class shared by the startup configuration routers (body limits, safe validation errors) |
| `tests/support/configurations/` | Shared builders, transcripts and fixtures of the startup configuration tests |

### Adding a device

1. Add `services/configurations/boot_media/profiles/<name>.py` defining `PROFILE =
   BootMediaProfile(...)`: `id`, `title`, `description`, the entry `device_types`, the
   `volume_label` and `render(text, context)` returning `{filename: bytes}` (raise
   `ConfigurationError("configuration_invalid_content")` for unusable text; `text_profile()` covers
   the common "one file with the text" case). Set `media="disk"` when the guest reads a FAT disk instead of a
   CD-ROM (the label is then at most 11 characters).
2. Add one line to `PROFILES` in `boot_media/profiles/__init__.py`.
3. Add its expectations to `tests/services/configurations/boot_media/test_profiles.py`.

The staging, journal, attachment, wipe, catalog and schema validation are shared.

### Requirements and limitations

- The compute needs `xorriso`/`xorrisofs`, `genisoimage` or `mkisofs` for CD-ROM media, and `mtools` (`mformat`, `mcopy`) for disk media (`boot_media_tool_missing` otherwise).
- Linked-clone nodes (the default): Wipe needs them. A node that is not a linked clone can be staged only before it ever ran;
  that is known from a marker (`.startup-new`) written when the compute creates its folder, so such a node created before
  the marker existed counts as already run.
- What was staged belongs to the profile that staged it. If the node's profile changes or is removed before the first boot,
  the staged media, and a disk the profile prepared itself, are dropped before the next boot.
- CD-ROM media is attached to one IDE CD-ROM slot (the guest must support an IDE CD-ROM); disk media to one virtio disk slot.
- For profile-based delivery, check the guest's console output to confirm import.
- Viptela, PAN-OS (`paloalto_panos`), EOS (`arista_eos`), and Junos (`juniper_junos`)
  use profile-based startup delivery. Their console recipes support capture only.
  Console startup replay and live apply return `configuration_apply_unsupported`.

## Wipe semantics

`POST /startup-configurations/wipe` takes exactly one selection: `{"node_ids":
[...]}` or `{"all": true}`. An empty body or both forms is a 422; nothing is wiped.
The response is `{"nodes": {"<id>": "wiped" | "<error code>"}, "stopped": [...]}`;
each node is reported independently and `stopped` lists nodes that were running
and were stopped first (wipe leaves nodes stopped). Wipe requires `Project.Modify`,
`Node.Modify` and `Node.Console`. A project that is a frozen distributed template refuses the wipe with 403 (the copies' overlay
disks point at the template's files). A node that a running capture or live-apply job works on is reported
as `configuration_operation_in_progress`; the other nodes are wiped as usual. A pending startup replay of the node
(waiting for the boot prompt or for a console client to disconnect) is cancelled
by the wipe, which stops the node anyway. These privileges are checked before the
node ids in the request are validated, so a caller without access learns nothing
about which ids exist. It is destructive and has no undo.

Before a node is stopped, the controller checks its startup entry and asks the compute
whether the node's storage can be reset (`/configuration-wipe/preflight`); a refusal leaves
a running guest running. The compute repeats the check immediately before it erases. The
node is reserved for the whole wipe: a live apply requested meanwhile is refused with
`configuration_operation_in_progress`. A node is listed in `stopped` only once it reports
stopped. A QEMU process that does not exit even after being killed fails the stop, so its
disks are not erased. A Docker IOL reset that was interrupted blocks Start
(`configuration_outcome_unknown`) until another Wipe completes it. A request may name up
to 10000 nodes.

Per-node results other than `wiped`: `node_not_found`, `stop_required` (the node
could not be stopped), `configuration_wipe_unsupported`, `configuration_extra_storage`,
`configuration_image_required`, `configuration_image_changed`,
`configuration_mount_shadowed`, `configuration_outcome_unknown`,
`configuration_operation_failed`, `container_state_unavailable`,
`application_id_unavailable`, `invalid_startup_runtime`,
`configuration_operation_in_progress` (an explicit live-apply job for that node is
running, checked again after the node's lifecycle lease is acquired; a pending
startup replay is cancelled instead),
`configuration_restore_console_required`, the device-type codes
(`device_type_required`, `device_type_unsupported`, `configuration_profile_mismatch`,
`configuration_apply_unsupported`), `unsafe_configuration_path`,
`unsafe_configuration_file` and the generic `configuration_wipe_failed` (compute
unreachable or any other error).

| Engine | What Wipe resets |
| --- | --- |
| Dynamips | Native startup/private files and NVRAM |
| IOU/IOL | Startup/private files, the generated `nvram_NNNNN` and `vlan.dat-NNNNN` files (Docker IOL also its writable layer) |
| VPCS | Saved startup script |
| QEMU linked clone | A factory reset: owned writable overlays (installed software and disk changes included), UEFI variables, vTPM state, the config disk (`config.img`, `config.zip`) and startup media. Non-linked-clone layouts and project-local base disks are refused, and so are writable disks added through the additional options (`-drive` without `readonly=on`, `snapshot=on` or `media=cdrom`, `-hda`, `-blockdev` and the like) with `configuration_extra_storage` |
| Docker (generic Linux network file) | The saved `etc/network/interfaces` |
| Docker FRR | `etc/frr/frr.conf` (with its `.sav` and any staged startup file) and `etc/network/interfaces`; `daemons` and `vtysh.conf` stay. FRR then starts with an empty configuration |
| Docker with declared files (`extra_configs`), without the built-in network setup, or with a Netmiko console type other than Linux | Not supported: `configuration_wipe_unsupported` |

Wipe keeps the saved sets, the per-node assignments and the ON/OFF flags: only
the node's own runtime state is removed, and the next Start delivers the assigned
set again. Shared base images are never touched. OFF entries, Config Reset
or *None* do not remove configuration already inside a guest; turn the entry OFF,
Wipe, then Start to boot from base defaults (a preconfigured base image can still
contain accounts or licences). Conflicting operations, unsupported storage or an
unavailable compute prevent wiping. An enabled QEMU entry with content that
cannot be restored through the console is reported as
`configuration_restore_console_required` for that node and the node is not wiped,
instead of silently booting without the expected configuration.

### Getting a factory-default boot

1. Turn the node's entry OFF in its set, or assign the node *None*.
2. Wipe the node (it is stopped first if it is running).
3. Start it: nothing is delivered and the guest boots from its base image.

Wiping alone is not enough while an enabled entry is assigned, because the next
Start delivers it again.

A wipe that fails after it started deleting (a disk error on the third file) marks the node's runtime journal
`resetting` before the first file goes. The files already deleted stay deleted, and Start refuses the node with
`configuration_outcome_unknown` instead of booting a half-erased disk. Repeating the wipe finishes the job (a file that
is already gone is fine) and marks the node `clean` again. A wipe that is refused before it deletes anything (an
unsafe path, a running node) leaves the journal untouched.

## Checks and results

- Enabling or assigning an entry that the node's next start would apply runs that start's check, and is refused with the
  same code (`device_type_required`, `configuration_profile_mismatch` and so on). Text can still be stored and edited with
  startup OFF. A node that already booted starts normally even if its entry would be refused, because it is not applied.
- A native set (IOU, Dynamips, Docker IOL) stays pending (`prepared`) until the node has launched, and is written again by
  a later Start. A direct node-property import changes the runtime journal only after the files were written.
- Turning startup off, clearing it or changing its kind withdraws a preparation that has not launched yet
  (`/configuration-withdraw`): the files it replaced are put back. A launched runtime, a file changed since and a direct
  import are left alone.
- Boot media staging records which profile owns the artifacts before it replaces them, so an interrupted staging is
  redone or cleaned up. Portable project export leaves out its `.prepare-*` and `.disk-copy-*` work files.
- A capture reads the node as it is configured now; the stored entry's device type does not choose the commands.
  `save_then_capture` needs `Node.Modify`. `save_to_set=true` fails with `configuration_not_savable` when the result
  cannot become a set entry.
- After startup console replay, IOS/IOS-XE, NX-OS, IOS XR, and ASA are read back.
  The server compares the saved commands with the running configuration in their original
  configuration scope. A match reports `applied`. A mismatch reports
  `configuration_apply_unverified`. An unreadable or incomparable read-back reports
  `configuration_verification_unavailable`. These verification failures require checking
  the guest before retrying because the commands may already have changed it.
- Startup replay on other console recipes and explicit live apply report
  `configuration_apply_accepted` when the commands succeed without read-back. Live apply
  merges and saves or commits the configuration on a running node. Its job's `details`
  record where a failure stopped.
- `GET .../sets/{id}/export?revision=N` refuses the export (`startup_configurations_changed`) if the sets changed since
  revision N.
- A Junos entry without `root-authentication` is applied, and `root` then logs in without a password; the web interface
  says so next to the text.

## FRR containers

A Docker node is an FRR node when its image repository is named `frr` (`gns3/frr`, `quay.io/frrouting/frr`) or its
environment sets `FRR_PROFILE`, it declares no Netmiko device type, and it is not a vendor or IOL container
(`is_frr_node`). A declared device type, `linux` included, keeps the previous handling.

- **Persistence.** `/etc/frr` has to be a volume. The GNS3 `gns3/frr` image declares it; for another image add `/etc/frr`
  to the node's additional persistent directories (`configuration_frr_volume_required` otherwise).
- **Startup.** The entry (device type `frr`, the text of `frr.conf`) is staged as `etc/frr/.gns3-startup.conf` at the first
  start after a Wipe. `init.sh` installs it as `frr.conf` after it has seeded the volume from the image, then removes it.
  Later restarts keep what the router saved (`write memory`).
- **Export and capture.** While the node runs: `docker exec <container> vtysh -c "show running-config"`, which changes
  nothing in the guest. While it is stopped: the saved `frr.conf`. Live apply is not offered.
- **Daemons.** The entry does not choose the daemons: they come from the image's `daemons` file or `FRR_PROFILE`. Commands
  of a daemon that is not running are not applied.
- The image has to provide `vtysh.conf` with `service integrated-vtysh-config` (the GNS3 image does).

## Closed, frozen and linked projects

- The set routes need an opened project (`project_closed` otherwise): a closed project has no loaded nodes, so access
  cannot be checked per node. A frozen distributed template refuses every change to sets and choices (403).
- The projects folder, and a project's `project-files`, may be reached through symbolic links. Below `project-files`
  links are refused, since those files can come from an imported project or a guest.
- A live apply cancelled while it waits ends as `cancelled`. Stop, close and delete drop the controller's apply request,
  and the compute then cancels the console work. Startup replays do not take a live-apply slot while they wait.
- "Import config" of an IOU node makes the next start push the file to NVRAM, also after a Wipe.
- Console proxies of Telnet Dynamips routers use internal ports above the console range.

## Stop, delete and Reload around a start

- A Stop or delete cancels a start that is still preparing its startup configuration; the start then ends without
  launching. A launch already sent to the compute is not interrupted.
- Reload of a stopped node with native startup files (not QEMU) that the feature manages, or that holds a preparation, is
  a Stop and Start.

## Capture and credentials

Console capture reads the running configuration and never runs save/commit
(`save_then_capture` is an explicit mutation). It may adjust paging and dismiss
the Cisco setup wizard. It uses the guest console, not its management IP.
Set the correct Netmiko device type and the guest's Default username/password;
the Default password is also used for enable. Close every console client of the
node first: capture and replay need the exclusive lease. VPCS capture reads the
saved script (`save` first). Managed Docker reads the saved network file, and
FRR reads the running configuration or saved file according to node state.
These sources are available to set capture while stopped. A console-based set
capture requires a running node. A direct export from stopped native IOS nodes
reads the saved native state. A failed capture keeps the previous content, and new
entries start OFF.

## Request size and authentication

Configuration routes authenticate before reading the body. A declared
`Content-Length` above the route budget is rejected with 413 without reading, and
bodies without a length are streamed against the same cap. Budgets: 16 KiB for
small option bodies, 512 KiB for bulk capture, wipe, and assignment requests,
34 MiB for set documents and archive imports on the controller (archives 24 MiB
before base64), and 13 MiB for compute apply and media routes.
Text uploads are limited to 2 MiB per file. Validation errors never echo request
values; only whitelisted field names and fixed reason codes are returned.

Sets, archives and exports can contain secrets (they are not encrypted). Reading
them (`GET` sets, set export, node export) needs `Project.Audit` and `Node.Audit`.
Writing a set document, creating a set, capturing, applying, assigning a set, and
wiping require `Project.Modify`, `Node.Modify`, and `Node.Console` for the nodes
the route checks. Clearing assignments and importing archives require
`Project.Modify` and `Node.Modify` for the affected nodes. Console exports also
require `Node.Console`. Saving to a set or saving on the guest before capture
requires modify access as well. The privilege check precedes semantic validation
of node IDs and set contents. Treat project backups and snapshots accordingly.

`PUT /v3/projects/{project_id}/startup-configurations/selections` gives several nodes one choice
(`{"node_ids": [...], "selection": {"kind": "set", "set_id": ...} | {"kind": "none"}, "revision": n}`) in one write under
the assignment revision, with the node privileges checked for the named nodes only (`Node.Console` only for a set). It is
all or nothing (unknown node or set 404, a node type that cannot apply its entry 422, a stale revision 409) and answers
with `without_startup`: the nodes that have no enabled entry in the set. `kind: none` clears their startup.

## Storage in the project

Everything the feature saves for a project lives under `project-files/startup-configs/` and goes through one
per-project lock with a revision check.

| Path | Content |
| --- | --- |
| `configurations.json` | The named sets and, per set, the entry of each node (device type, text, startup ON/OFF); the project default set |
| `nodes/selections.json` | Which set each node starts from (`set` or `none`); a node without an entry uses the project default |
| `nodes/managed/<node-id>.json` | Marks a Dynamips, IOU, VPCS or Docker IOL node whose startup this feature manages (written by Wipe); only its existence matters |

Per-node runtime state is not in this folder: it is the `.startup-runtime.json` journal (`shared/startup_journal.py`) in the node's own folder, and
the staged CD-ROM (`startup-media.iso`) or FAT disk (`startup-media.img`) sits next to it.
A portable project import remaps node IDs in sets, assignments, and managed-node markers.

## Portability

A portable set archive is a ZIP with `manifest.json` (format version 2: set name, node membership and, per node, the
name of its file) and one readable text file per node, `nodes/<node name>-<short id>.<ext>` (`.xml` for PAN-OS, `.rsc`
for RouterOS, `.vpc` for VPCS, `.conf` for FRR, and `.cfg` for other entries).
An entry without text has no file. The files can be compared, reviewed and
edited offline, then zipped again: folder entries, one enclosing folder, `__MACOSX`, `.DS_Store`, `Thumbs.db` and
`desktop.ini` are ignored, a UTF-8 byte order mark is dropped and line endings are kept as edited. Everything else has
to add up: a file no node names, a named file that is missing, text that is not UTF-8 or contains control characters,
and links or encrypted members are refused (`invalid_configuration_archive`). Limits: 2 MiB per file, 24 MiB for the
ZIP, 48 MiB unpacked; export refuses a set over them (`configuration_archive_too_large`). Only manifest version 2 is accepted.

An archive imports as a **new** set; each node is mapped by an explicit mapping of the request, then by
ID, then by name when exactly one node of the project has the archive node's name (an archive from another project
has other IDs). The response lists `mapped`, `matched_by_name` and `skipped` (`node_not_found`, `node_name_ambiguous`,
`node_mapped_elsewhere` for a node whose ID match an explicit mapping gave to another source,
`configuration_apply_unsupported`). Import never starts or wipes nodes.
Private configuration (Dynamips/IOU `private-config`) is not part of a set: it
stays on the node and is preserved when a set text is applied. The direct file download in
the Web UI can retrieve the private file separately. Full project exports include the
saved sets and assignments. Portable project imports remap node IDs, while a snapshot
restored into the same project keeps its node IDs and restores the saved sets and
assignments from the snapshot.

## Troubleshooting

| Symptom or code | Next step |
| --- | --- |
| Old configuration remains after changing the set | Native runtimes keep saved state: check the set and ON/OFF flag, then Wipe and Start. |
| `configuration_not_saved` (409) | Nothing is saved on the node yet (for example VPCS writes `startup.vpc` about 2 s after `save`, or a native device never saved). Save on the device, wait a moment and retry. |
| Startup configuration is never applied after Start; status stays `waiting_for_console` | An open console blocks the replay: it needs the exclusive console lease and retries every second until every client (browser console tab, desktop terminal) is closed, logging `waiting (console_busy)` about every 30 attempts. Close the console and the replay proceeds by itself. Wipe or Stop cancels it. |
| Replay is slow | The console automation adds no fixed delay per command: cost is the device latency per round trip (roughly 30 s for 270 round trips at 100 ms). It first waits for the boot prompt (up to 600 s per attempt), then types about 2-3 console round trips per configuration line plus the save, so large configurations take minutes. The whole replay, retries included, is bounded to 900 s (`configuration_apply_timeout`), inside the 1200 s compute limit and the 2400 s controller request limit. |
| `configuration_apply_timeout` | Three code paths: (1) the boot-prompt wait (600 s per attempt) never saw a usable prompt: `phase=ready` and the last two console lines say what the console showed; (2) the whole replay, including `console_busy`/`console_unavailable` retries, exceeded 900 s: `phase=console-wait` names the last retry reason when there was one; (3) the compute (1200 s) or controller limits expired. `configuration_capture_timeout` is the equivalent for captures/exports. |
| `console_busy` | Close every client (browser tabs, desktop terminals) of that node's console. |
| `console_unsafe_mode` | Return to an operational prompt (`end` on IOS) and retry. |
| `console_authentication_failed` / enable secret | Check the saved login and enable credentials against the guest. |
| `console_not_ready`, `configuration_capture_timeout` | Let the guest finish booting, check device type and prompt, close console clients. |
| `console_recovery_required` | Reset the console from the UI or stop/start the node. |
| `configuration_apply_failed` / `configuration_apply_unverified` | The guest rejected or did not confirm the replay. Read the failure context below to see where, then inspect the guest before retrying. |
| `configuration_verification_unavailable` | The commands were sent, but the running configuration could not be read or compared. Check the guest before retrying. |
| `configuration_compute_unavailable` (502) | The compute could not be reached or timed out. Other compute failures are reported as `configuration_export_failed` (502) or the operation's own code; the underlying error is in the controller log. |
| `configuration_export_timeout` (408), `capture_capacity_exhausted` (429) | The export took too long, or too many captures are running: retry later. |
| `startup_configurations_changed` / revision conflict | Another editor changed the document; reload and reconcile. |
| `configuration_outcome_unknown` | A reset was interrupted; inspect node/compute state, nothing is repeated automatically. |
| `device_type_required`, `device_type_unsupported`, `configuration_profile_mismatch` | Set the node's Netmiko device type to one with a console recipe that matches the saved entry. |
| `configuration_restore_console_required` | Set the QEMU node's console type to Telnet or SSH. |
| QEMU says `'virtio-gpu-pci' is not a valid device model name` | GNS3 requests this graphics device when using VNC. Check the selected QEMU binary's `-device help` output and install its matching graphics module on the compute host if you need VNC. For an IOSv CLI, select the appliance's default Telnet console. This failure occurs before the guest boots. |
| `configuration_apply_unsupported` for a Viptela entry | Viptela startup is never replayed through the console. Select the `cisco-viptela` boot media profile on the node (or disable the entry). |
| `boot_media_tool_missing`, `boot_media_build_failed`, `boot_media_too_large` | Install the tools required by the selected profile and check the compute log. CD-ROM profiles use `xorrisofs`, `genisoimage`, or `mkisofs`. FAT profiles use mtools and have a separate size limit. Disk preparation profiles can need additional tools listed in their profile notes. |
| `startup_media_profile_unknown` | The profile id is not in `GET /v3/startup-media-profiles`. |
| `saved_state_kept` (status) | The node already booted, so an edited startup entry was not delivered. Wipe the node, then Start it. |
| Wipe returns 404 | An older controller/compute lacks the feature; update and restart them. |

### Reading a failure context

A failed console replay reports where it stopped, in `GET /v3/projects/{id}/startup-configurations/status`
(per node, next to `status` and `set_id`), in the project notification
(`Startup configuration for <node>: ... (phase=replay command=12/101 sent='...' device='...')`)
and in the compute log (`log.warning`, `Startup configuration apply on <node> failed: <code> phase=...`).

```json
{
  "status": "configuration_apply_failed",
  "set_id": "...",
  "phase": "replay",
  "command_index": 6,
  "command_total": 101,
  "command": "password <masked>",
  "device_error": "syntax error: password <masked>"
}
```

All fields except `phase` are optional and only present when known.

| Field | Meaning |
| --- | --- |
| `phase` | `ready` (the boot-prompt wait timed out; `device_error` holds the last two console lines), `console-wait` (the 900 s apply budget ran out while retrying `console_busy`/`console_unavailable`; `device_error` is `last retry: <code>`), `login`, `prepare` (terminal setup), `enter` (entering configuration mode), `replay` (one configuration line), `save` |
| `command_index` / `command_total` | 1-based position of the configuration line being replayed, and the number of lines. |
| `command` | The command that was being run, as a keyword path, at most 160 characters. Quoted strings, `$n$` hashes, long opaque tokens and everything after `password`/`secret`/`key`/`community`/`hash`/`token`... are replaced by `<masked>`. |
| `device_error` | The first device line that was rejected (or, for validate/commit/pending checks, the first output line), masked the same way and truncated to 250 characters. |

Configuration content, credentials and full device output are never reported or logged. Typical reading: `phase=replay` names the first line the device refused; `phase=ready` means the guest never showed a usable prompt.

## Adding a device

Console recipes live in `services/configurations/console/recipes/config_<device>.py`
(one `PLATFORM` each, registered in `recipes/__init__.py`). A recipe opts into behaviour with `ConsolePlatform` fields, never by name in shared code:
`verifiable` (a startup replay is read back and compared, `console/verification.py`; `comparable` converts non-CLI text),
`password_setup` (a first-login password setup is answered), `tolerated_errors` (device errors that only say an item
exists are skipped) and `input_prompt` (a prompt for a missing value is cancelled and reported). A new Netmiko name that
runs an existing CLI only needs an alias in `normalize_device_type`. New public
error codes must be added to the registry in `services/configurations/shared/errors.py`;
`tests/services/configurations/shared/test_errors.py` fails if a raised code is
unregistered or lacks an HTTP status.

### Verified on real images

The formats above were checked by booting the real images with the staged media: the C8000v
autonomous image logs `PnP Discovery stopped (Startup Config Present)`; the controller image logs
`LOAD_DAY0_CONFIG=true` then `Loading day-0 cloud-init bootstrap config` and applies the text; the Viptela
images print the loader's `GNS3: startup configuration applied.` about 15 s after cloud-init and
before `System Ready` plus about one minute. A controller image that was initialized once
logs `LOAD_DAY0_CONFIG=false` and ignores the media until `request platform software sdwan config reset`.

### MikroTik RouterOS (CHR)

A RouterOS node uses the Netmiko device type `mikrotik_routeros` and the console path: the saved text is replayed
through the serial console (Telnet or SSH) after a wipe, as for the other console platforms. There is no boot media.

- **Login**: `admin` with an empty password is accepted. The recipe skips the licence question and the optional
  password-change screen without changing the account, and widens the terminal (the `+ct511w4098h` login suffix)
  so no line is wrapped.
- **Export** (`/export terse`): RouterOS 7 hides secrets unless `show-sensitive` is added, RouterOS 6 prints them
  and rejects both flags, so the backup export uses `/export terse show-sensitive` from version 7 and plain
  `/export terse` below. RouterOS saves its configuration by itself, so no save command is sent.
- **Not exported**: user accounts and their passwords are never part of a RouterOS export. Keep the
  `/user add name=... password=...` lines in the startup text; a capture does not bring them back.
- **Blank start**: a startup apply of a full export (its first line is the `# ... by RouterOS ...` header) first sends
  `/system reset-configuration no-defaults=yes skip-backup=yes`, answers the confirmation, waits for the reboot and logs
  in again, so the node ends in exactly the state of the text: a default the text does not mention (the DHCP client)
  is gone. This adds about 20 s to the first start. A short hand-written text, and an apply to a running node, never
  reset anything: they merge into the configuration.
- **Replay**: a merge also meets items the router already has (the factory defaults). An error that only says the item
  exists (`already used`, `already exists`, `already have such ...`) is skipped; any other error stops the replay
  and names the command.
- **Missing values**: an `add` without a mandatory value (an export of an entry whose interface is gone, for
  example `/ip dhcp-client add disabled=no`) makes the CLI ask for it and swallow the next command. The replay cancels
  the prompt (Ctrl-C) and fails with `interface: a value is required` and the command index. Complete or remove the line.
- **Verified on a real image** (RouterOS 6.46.5, file named `mikrotik-ros-7.11.2.qcow2`, which only boots with
  an IDE system disk; a virtio disk shuts the guest down): export in 2.5 s, capture into a set, wipe, start and
  replay (36 s including the reset), live apply to the running node, and the failure of the unreplayable `dhcp-client` lines. The
  RouterOS 7 export flag could not be verified on a real image.
