#
# Copyright (C) 2026 GNS3 Technologies Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Live end-to-end test for link-local frame transparency on kernel-datapath
links (pytest marker ``e2e``): a per-link Linux bridge stands in for a cable,
so the IEEE 802.1D reserved range must cross it exactly like the uBridge UDP
relay always carried it. uBridge opens every enslave'd port's
``IFLA_BRPORT_GROUP_FWD_MASK`` to ``0xfffd`` (ubridge commit 0284500; the
contract lives in ``docs/design/ubridge-link-local-frame-forwarding-spec.md``),
which makes STP, LACP, 802.1X and LLDP/DCBX flow between the guests while the
kernel keeps hard-dropping MAC PAUSE.

``test_docker_link_local_frames`` — two real Alpine containers on a kernel
link; a static raw-Ethernet probe (built at run time, docker-cp'd in — the
image has no raw-frame tool) injects frames from guest 1's eth0 while guest
2's eth0 counts what actually arrived, per destination MAC. The scenario
asserts, through the server's own wiring path:

* the per-link bridge carries both anchors and each anchor's sysfs
  ``brport/group_fwd_mask`` reads 65533 (0xfffd) — the uBridge default
  applied by ``brctl addif``, which is the only place gns3-server wires ports;
* the bridge-level ``group_fwd_mask`` stays 0 (the fix is per-port only);
* the live matrix from the guest: ordinary multicast crosses (wire sanity),
  STP / LACP / EAPOL / LLDP cross, and PAUSE does not — ``br_handle_frame``'s
  ``case 0x01`` drops it unconditionally, so PFC stays unsupported by design;
* a container stop/start replays the NIO wiring and the mask is re-applied
  (the reconnect story), with a fresh LACP round surviving it.

The negative control for the old behaviour is the uBridge suite's
``setportgroupfwd 0`` case (stock kernel semantics), not a second server run.
"""

import functools
import io
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.e2e import harness

pytestmark = pytest.mark.e2e

# every standard Docker adapter has a single port
ETH = (0, 0)
R1_IP = "10.2.1.1"
R2_IP = "10.2.1.2"

# (destination MAC, ethertype) — what the guest protocol would emit
CONTROL = ("01005e000001", "0800")  # ordinary multicast: must always cross
STP = ("0180c2000000", "0026")  # STP BPDU
LACP = ("0180c2000002", "8809")  # LACP / slow protocols
EAPOL = ("0180c2000003", "888e")  # 802.1X EAPOL
LLDP = ("0180c200000e", "88cc")  # LLDP / DCBX
PAUSE = ("0180c2000001", "8808")  # 802.3x PAUSE — kernel hard-drop

MUST_CROSS = [CONTROL, STP, LACP, EAPOL, LLDP]
MUST_NOT_CROSS = [PAUSE]

RECV_WINDOW = 12

_LLPROBE_C = r"""
/*
 * llprobe — raw Ethernet send/recv with explicit destination MACs, for the
 * link-local forwarding e2e. Built static by the test, docker-cp'd into the
 * containers (the Alpine image has no raw-frame tool of its own).
 *
 *   llprobe send <ifname> <dst-mac-hex> <ethertype-hex> <count>
 *   llprobe recv <ifname> <window-seconds> <dst-mac-hex>...
 *
 * recv prints one "<mac>=<count>" line per requested MAC, counting only
 * inbound frames (PACKET_OUTGOING excluded — a veth host end sees its own
 * transmissions too).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/ioctl.h>
#include <net/if.h>
#include <net/ethernet.h>
#include <netpacket/packet.h>
#include <arpa/inet.h>
#include <time.h>

#define MAX_MACS 8

static int parse_mac(const char *hex, unsigned char *out)
{
    char buf[13];
    int v[6];
    size_t j = 0;
    for (size_t i = 0; hex[i] && j < 12; i++)
        if (hex[i] != ':' && hex[i] != '-')
            buf[j++] = hex[i];
    buf[j] = '\0';
    if (j != 12 || sscanf(buf, "%2x%2x%2x%2x%2x%2x", &v[0], &v[1], &v[2], &v[3], &v[4], &v[5]) != 6)
        return -1;
    for (int i = 0; i < 6; i++)
        out[i] = (unsigned char)v[i];
    return 0;
}

static int raw_socket(const char *ifname, struct ifreq *hwaddr)
{
    int sck = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if (sck < 0) {
        perror("llprobe: socket");
        return -1;
    }
    if (hwaddr) {
        memset(hwaddr, 0, sizeof(*hwaddr));
        strncpy(hwaddr->ifr_name, ifname, IFNAMSIZ - 1);
        if (ioctl(sck, SIOCGIFHWADDR, hwaddr) < 0) {
            perror("llprobe: SIOCGIFHWADDR");
            close(sck);
            return -1;
        }
    }
    struct sockaddr_ll sa;
    memset(&sa, 0, sizeof(sa));
    sa.sll_family = AF_PACKET;
    sa.sll_protocol = htons(ETH_P_ALL);
    sa.sll_ifindex = if_nametoindex(ifname);
    if (sa.sll_ifindex == 0) {
        fprintf(stderr, "llprobe: no interface %s\n", ifname);
        close(sck);
        return -1;
    }
    if (bind(sck, (struct sockaddr *)&sa, sizeof(sa)) < 0) {
        perror("llprobe: bind");
        close(sck);
        return -1;
    }
    return sck;
}

static int do_send(const char *ifname, const char *dst_hex, const char *et_hex, int count)
{
    unsigned char dst[6], frame[64];
    unsigned int et = 0;
    struct ifreq ifr;
    int sck = raw_socket(ifname, &ifr);
    if (sck < 0)
        return 1;
    if (parse_mac(dst_hex, dst) < 0 || sscanf(et_hex, "%x", &et) != 1) {
        fprintf(stderr, "llprobe: bad mac %s or ethertype %s\n", dst_hex, et_hex);
        close(sck);
        return 1;
    }
    for (int n = 0; n < count; n++) {
        memcpy(frame, dst, 6);
        memcpy(frame + 6, ifr.ifr_hwaddr.sa_data, 6);
        frame[12] = (et >> 8) & 0xff;
        frame[13] = et & 0xff;
        frame[14] = 'L';
        frame[15] = 'L';
        frame[16] = (unsigned char)n;
        memset(frame + 17, 0, sizeof(frame) - 17);
        if (send(sck, frame, sizeof(frame), 0) < 0) {
            perror("llprobe: send");
            close(sck);
            return 1;
        }
        usleep(20000);
    }
    close(sck);
    printf("sent %d frames to %s on %s\n", count, dst_hex, ifname);
    return 0;
}

static int do_recv(const char *ifname, int window, char **macs, int nmacs)
{
    unsigned char want[MAX_MACS][6];
    long counts[MAX_MACS] = {0};
    unsigned char buf[2048];
    int sck = raw_socket(ifname, NULL);
    if (sck < 0)
        return 1;
    for (int i = 0; i < nmacs; i++)
        if (parse_mac(macs[i], want[i]) < 0) {
            fprintf(stderr, "llprobe: bad mac %s\n", macs[i]);
            close(sck);
            return 1;
        }
    struct timeval tv = {0, 500000};
    setsockopt(sck, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    long deadline = time(NULL) + window;
    for (;;) {
        if (time(NULL) >= deadline)
            break;
        struct sockaddr_ll from;
        socklen_t flen = sizeof(from);
        ssize_t n = recvfrom(sck, buf, sizeof(buf), 0, (struct sockaddr *)&from, &flen);
        if (n < 14)
            continue; /* timeout, error or runt */
        if (from.sll_pkttype == PACKET_OUTGOING)
            continue;
        for (int i = 0; i < nmacs; i++)
            if (memcmp(buf, want[i], 6) == 0)
                counts[i]++;
    }
    close(sck);
    for (int i = 0; i < nmacs; i++)
        printf("%s=%ld\n", macs[i], counts[i]);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc >= 5 && strcmp(argv[1], "send") == 0)
        return do_send(argv[2], argv[3], argv[4], atoi(argv[5]));
    if (argc >= 5 && strcmp(argv[1], "recv") == 0)
        return do_recv(argv[2], atoi(argv[3]), argv + 4, argc - 4);
    fprintf(stderr, "usage: llprobe send <if> <dst> <ethertype> <count>\n"
                    "       llprobe recv <if> <window-s> <dst>...\n");
    return 2;
}
"""


@functools.cache
def _llprobe():
    """Build the static raw-Ethernet probe (cached for the session)."""
    directory = tempfile.mkdtemp(prefix="gns3-e2e-llprobe-")
    source = os.path.join(directory, "llprobe.c")
    binary = os.path.join(directory, "llprobe")
    with open(source, "w") as f:
        f.write(_LLPROBE_C)
    cc = shutil.which("cc")
    if cc is None:
        pytest.skip("cannot build the raw-frame probe (no C compiler found)")
    try:
        subprocess.run([cc, "-static", "-O2", "-o", binary, source], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        pytest.skip(f"cannot build the raw-frame probe (cc -static): {e}")
    return binary


def _upload_probe(daemon, *container_ids):
    """docker-cp the probe into every container's /tmp."""
    with open(_llprobe(), "rb") as f:
        payload = f.read()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        info = tarfile.TarInfo("llprobe")
        info.size = len(payload)
        info.mode = 0o755
        tar.addfile(info, io.BytesIO(payload))
    archive = buffer.getvalue()
    for container_id in container_ids:
        daemon.cp(container_id, archive, "/tmp")


def _recv_counts(daemon, container_id, window, macs):
    """Run the receiver to completion and parse its "<mac>=<count>" lines."""
    code, output = daemon.exec(container_id, ["/tmp/llprobe", "recv", "eth0", str(window), *macs], timeout=window + 30)
    assert code == 0, output
    return {line.split("=")[0]: int(line.split("=")[1]) for line in output.strip().splitlines() if "=" in line}


def _send_all(daemon, container_id, matrix, count=5):
    for mac, ethertype in matrix:
        code, output = daemon.exec(container_id, ["/tmp/llprobe", "send", "eth0", mac, ethertype, str(count)])
        assert code == 0, output


def _port_mask(anchor):
    """The anchor's link-local forwarding mask, as an int — newer kernels
    print the sysfs attribute in hex (``0xfffd``), older ones in decimal."""
    return int(harness.sysfs(f"/sys/class/net/{anchor}/brport/group_fwd_mask"), 0)


def test_docker_link_local_frames():
    server = harness.live_server(kernel=True)
    compute = server.compute
    image = harness.ensure_docker_image(server)

    project = compute.create_project("docker-ll")
    pid = project["project_id"]
    try:
        nodes = []
        for suffix, address in (("1", R1_IP), ("2", R2_IP)):
            node = compute.create_docker_node(pid, f"LL-{suffix}", image)
            harness.configure_docker_interfaces(node, address)
            nodes.append(node)
        n1, n2 = nodes
        daemon = harness.DockerDaemon()
        for node in nodes:
            node["container_id"] = daemon.container_id(f"GNS3.{node['name']}.{pid}")
            assert node["container_id"], f"container for {node['name']} not found"
        c1, c2 = n1["container_id"], n2["container_id"]

        link = compute.create_link(pid, (n1["node_id"], *ETH), (n2["node_id"], *ETH))
        lid = link["link_id"]
        assert link["kernel_datapath"] is True, link

        print(".. starting containers")
        for node in nodes:
            compute.call("POST", f"/projects/{pid}/nodes/{node['node_id']}/start")
        for node, address in zip(nodes, (R1_IP, R2_IP), strict=True):
            harness.docker_wait_address(daemon, node["container_id"], address)

        a1 = harness.docker_anchor_name(n1["node_id"], *ETH)
        a2 = harness.docker_anchor_name(n2["node_id"], *ETH)
        bridge = harness.link_bridge_name(lid)
        assert harness.bridge_members(bridge) == sorted([a1, a2]), harness.bridge_members(bridge)

        # The uBridge default as reached through the server's own wiring:
        # both anchors open to 0xfffd, the bridge level untouched.
        for anchor in (a1, a2):
            mask = _port_mask(anchor)
            assert mask == 0xFFFD, f"{anchor}: group_fwd_mask {mask:#x} != 0xfffd"
        assert int(harness.sysfs(f"/sys/class/net/{bridge}/bridge/group_fwd_mask"), 0) == 0

        print(".. injecting the link-local matrix from guest 1")
        _upload_probe(daemon, c1, c2)
        matrix = MUST_CROSS + MUST_NOT_CROSS
        with ThreadPoolExecutor(max_workers=1) as pool:
            receiver = pool.submit(_recv_counts, daemon, c2, RECV_WINDOW, [mac for mac, _ in matrix])
            time.sleep(1.5)  # let the receiver bind before the first frame
            _send_all(daemon, c1, matrix)
            counts = receiver.result()
        print(f".. guest 2 received: {counts}")
        for mac, _ in MUST_CROSS:
            assert counts.get(mac, 0) > 0, f"{mac} did not cross the kernel link: {counts}"
        for mac, _ in MUST_NOT_CROSS:
            assert counts.get(mac, 0) == 0, f"{mac} unexpectedly crossed: {counts}"

        print(".. restarting container 1: the NIO replay must re-apply the mask")
        compute.call("POST", f"/projects/{pid}/nodes/{n1['node_id']}/stop")
        harness.wait_until(lambda: not harness.tap_exists(a1), timeout=15)
        compute.call("POST", f"/projects/{pid}/nodes/{n1['node_id']}/start")
        harness.docker_wait_address(daemon, c1, R1_IP)
        assert harness.wait_until(lambda: harness.bridge_members(bridge) == sorted([a1, a2]), timeout=15)
        mask = _port_mask(a1)
        assert mask == 0xFFFD, f"{a1} after restart: group_fwd_mask {mask:#x} != 0xfffd"

        with ThreadPoolExecutor(max_workers=1) as pool:
            receiver = pool.submit(_recv_counts, daemon, c2, 8, [LACP[0]])
            time.sleep(1.5)
            _send_all(daemon, c1, [LACP])
            counts = receiver.result()
        assert counts.get(LACP[0], 0) > 0, f"LACP dead after the container restart: {counts}"
    except BaseException:
        harness.release(server, pid, failed=True)
        raise
    harness.release(server, pid)
