# QEMU support

GNS3 server requires QEMU 6.2 or newer. This is the minimum QEMU version that the server actively supports on Linux.

For compatibility checks, the project evaluates the Linux distributions that are commonly used in server deployments and that still have supported releases: CentOS Stream, Debian, Fedora, openSUSE, RHEL, SLES, and Ubuntu LTS. Other distributions are assumed to ship similar package versions and are treated by the same rule: if the distro ships QEMU 6.2 or newer, it is considered compatible; if it ships an older version, it is not supported by GNS3 server.

This document reflects the currently supported release set as of October 2026, based on the active releases listed by the major distro end-of-life trackers and package versions shipped by those releases.

## Minimum supported version

- Minimum supported QEMU version: 6.2
- QEMU 6.2 was first shipped in Ubuntu 22.04 LTS and is the baseline used to determine whether a Linux distribution is suitable for GNS3 server.
- Distributions shipping QEMU 6.2 or later are generally acceptable.
- Older package versions are considered unsupported by policy.

## Currently supported Linux releases and shipped QEMU versions

The following supported releases are the current reference points used by the project. They are based on the active release lists published by the distributions' end-of-life trackers and the QEMU versions typically shipped by those releases.

| Distribution | Current supported OS release(s) | QEMU version shipped | Source |
| --- | --- | --- | --- |
| Ubuntu LTS | 24.04 LTS, 22.04 LTS | 8.2 for 24.04, 6.2 for 22.04 | https://endoflife.date/ubuntu |
| Debian | 13 (trixie), 12 (bookworm) | 9.x for 13, 7.2 for 12 | https://endoflife.date/debian |
| Fedora | 42, 41, 40 | 9.x | https://endoflife.date/fedora |
| openSUSE | Leap 15.6, Tumbleweed | 8.x to 9.x | https://endoflife.date/opensuse |
| CentOS Stream | 10, 9 | 9.x / 8.x | https://endoflife.date/centos |
| RHEL | 10, 9.5, 9.4 | 9.x / 8.x | https://endoflife.date/redhat-enterprise-linux |
| SLES | 15 SP7, 15 SP6 | 8.x | https://endoflife.date/sles |
