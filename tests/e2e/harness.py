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
Shared harness for live end-to-end tests (pytest marker ``e2e``).

These tests drive a **real** gns3-server process against real uBridge, real
kernel interfaces and real emulator binaries — things a unit-test run cannot
provide (privileges, images, a live kernel). They exist to verify what mocks
cannot: that kernel bridges actually enslave anchors, that tc impairments
actually shape traffic, that a datapath actually forwards. Run them with::

    pytest -m e2e tests/e2e -s

The harness targets an **already running server** when ``GNS3_E2E_URL`` is
set (``GNS3_E2E_USER`` / ``GNS3_E2E_PASSWORD`` default to admin/admin), and
otherwise starts an **isolated instance** — its own config dir, controller
DB, project paths and free port, all under a temporary directory that is
removed on exit. Either way every test creates its own project and deletes
it again (``GNS3_E2E_KEEP=1`` keeps the project for inspection).

Environment knobs:

* ``GNS3_E2E_URL`` — target server, e.g. ``http://127.0.0.1:3080/v3``;
  when unset, an isolated instance is started for each test.
* ``GNS3_E2E_USER`` / ``GNS3_E2E_PASSWORD`` — credentials for the target.
* ``GNS3_E2E_IMAGES`` — images directory the isolated instance uses
  (default ``~/GNS3/images``); also where the dynamips test finds its image.
* ``GNS3_E2E_KEEP=1`` — keep the project (and the isolated instance) when a
  test fails, and print their ids, for inspection.
"""

import contextlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# tc lives in /usr/sbin on most distributions; subprocesses do not always
# inherit a PATH that has it.
TC = shutil.which("tc", path=os.environ.get("PATH", "") + ":/usr/sbin:/sbin")
# Reading addresses with iproute2 needs no privileges; the L2 assertions
# below refuse to pass silently when it is missing.
IP = shutil.which("ip", path=os.environ.get("PATH", "") + ":/usr/sbin:/sbin")

# IOS prompt as the last thing on the stream: any hostname/mode shape.
PROMPT_RE = re.compile(r"[A-Za-z0-9\-_.()/]+[>#]\s*$")

# Test-only default credentials (every real deployment overrides them via
# GNS3_E2E_USER / GNS3_E2E_PASSWORD); a freshly started isolated instance
# seeds exactly these.
DEFAULT_USER = "admin"
DEFAULT_PASSWORD = "admin"


def keep_on_failure():
    return os.environ.get("GNS3_E2E_KEEP") == "1"


# ---------------------------------------------------------------------------
# REST client
# ---------------------------------------------------------------------------


class Compute:
    """REST client for one server (controller API), token-authenticated."""

    def __init__(self, url, username=DEFAULT_USER, password=DEFAULT_PASSWORD):
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self.token = None

    def call(self, method, path, body=None, timeout=60):
        # S310: the base URL comes from the operator (GNS3_E2E_URL or the
        # isolated instance this harness just started), not untrusted input
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method.upper())  # noqa: S310
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                payload = resp.read()
                return json.loads(payload) if payload else None
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise AssertionError(f"{method} {path} -> {e.code}: {detail}") from None

    def login(self):
        body = self.call("POST", "/access/users/authenticate", {"username": self.username, "password": self.password})
        self.token = body["access_token"]
        return self

    # -- common controller operations ------------------------------------

    def create_project(self, name="e2e"):
        return self.call("POST", "/projects", {"name": f"{name}-{int(time.time())}"})

    def create_dynamips_router(self, project_id, name, image, slots, platform="c7200", ram=512):
        properties = {"platform": platform, "image": image, "ram": ram}
        properties.update(slots)
        return self.call(
            "POST",
            f"/projects/{project_id}/nodes",
            {"compute_id": "local", "name": name, "node_type": "dynamips", "properties": properties},
        )

    def create_iol_router(self, project_id, name, image, adapters=2):
        """An IOL runner container (iol-runner images), the appliance's
        template properties."""
        return self.call(
            "POST",
            f"/projects/{project_id}/nodes",
            {
                "compute_id": "local",
                "name": name,
                "node_type": "docker",
                "properties": {
                    "image": image,
                    "adapters": adapters,
                    "console_type": "telnet",
                    "environment": "GNS3_IOL_RUNNER=1\nGNS3_IOL_STARTUP_CONFIG=iol-xe-base.txt",
                    "extra_volumes": ["/config"],
                },
            },
        )

    def create_link(self, project_id, a, b):
        return self.call(
            "POST",
            f"/projects/{project_id}/links",
            {
                "nodes": [
                    {"node_id": a[0], "adapter_number": a[1], "port_number": a[2]},
                    {"node_id": b[0], "adapter_number": b[1], "port_number": b[2]},
                ]
            },
        )

    def delete_project(self, project_id):
        self.call("DELETE", f"/projects/{project_id}")

    def node(self, project_id, node_id):
        return self.call("GET", f"/projects/{project_id}/nodes/{node_id}")

    def capabilities(self):
        return self.call("GET", "/computes/local").get("capabilities") or {}

    def dynamips_images(self):
        return [image["filename"] for image in self.call("GET", "/computes/local/dynamips/images")]

    def docker_images(self):
        return [image["image"] for image in self.call("GET", "/computes/local/docker/images")]


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

ISOLATED_CONFIG = """\
[Controller]
jwt_secret_key = 00000000000000000000000000000000000000000000000000000000000000e2
default_admin_username = admin
default_admin_password = admin

[Server]
host = 127.0.0.1
port = {port}
ubridge_path = {ubridge}
enable_kernel_datapath = {kernel}
report_errors = False
projects_path = {tmp}/projects
configs_path = {tmp}/configs
images_path = {images}
appliances_path = {tmp}/appliances
symbols_path = {tmp}/symbols

[Dynamips]
dynamips_path = {dynamips}
images_path = {images}
allocate_aux_console_ports = False
mmap_support = False
sparse_memory_support = False
ghost_ios_support = False
"""


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Server:
    """A server under test: an external one, or a freshly started isolated
    instance (own config dir — the controller DB and every path follow it —
    under a temporary directory removed on stop)."""

    def __init__(self, compute, process=None, tmpdir=None):
        self.compute = compute
        self.process = process
        self.tmpdir = tmpdir

    @property
    def isolated(self):
        return self.process is not None

    def log_tail(self, lines=40):
        if not self.tmpdir:
            return ""
        path = os.path.join(self.tmpdir, "server.log")
        if not os.path.exists(path):
            return ""
        with open(path) as f:
            return "".join(f.readlines()[-lines:])

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        if self.tmpdir:
            shutil.rmtree(self.tmpdir, ignore_errors=True)


def _start_isolated(kernel):
    ubridge = shutil.which("ubridge")
    dynamips = shutil.which("dynamips")
    if not ubridge:
        pytest.skip("ubridge is not in PATH (needed to start an isolated instance)")
    if not dynamips:
        pytest.skip("dynamips is not in PATH (needed to start an isolated instance)")
    images = os.environ.get("GNS3_E2E_IMAGES", os.path.expanduser("~/GNS3/images"))
    if not os.path.isdir(images):
        pytest.skip(f"images directory not found: {images} (set GNS3_E2E_IMAGES)")

    tmpdir = tempfile.mkdtemp(prefix="gns3-e2e-")
    os.makedirs(os.path.join(tmpdir, "projects"), exist_ok=True)
    port = _free_port()
    config = ISOLATED_CONFIG.format(
        port=port, ubridge=ubridge, dynamips=dynamips, images=images, tmp=tmpdir, kernel=kernel
    )
    config_path = os.path.join(tmpdir, "gns3_server.conf")
    with open(config_path, "w") as f:
        f.write(config)

    log = open(os.path.join(tmpdir, "server.log"), "w")
    # S603: fixed argv, this interpreter, no shell involvement
    argv = [sys.executable, "-m", "gns3server", "--config", config_path]
    if os.environ.get("GNS3_E2E_DEBUG"):
        argv.append("-d")  # debug logging — the uBridge command stream lands in server.log
    process = subprocess.Popen(  # noqa: S603
        argv,
        cwd=REPO_ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    process.log = log  # keep the file object alive with the process handle
    compute = Compute(f"http://127.0.0.1:{port}/v3")

    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            # S310: the port is ours, the host loopback
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/v3/version", timeout=2):
                break
        except Exception:
            if process.poll() is not None:
                raise AssertionError(
                    f"isolated server exited early:\n{open(os.path.join(tmpdir, 'server.log')).read()[-2000:]}"
                )
            time.sleep(0.3)
    else:
        raise AssertionError("isolated server did not come up within 60s")

    compute.login()
    return Server(compute, process, tmpdir)


def live_server(kernel=True):
    """The server under test.

    With ``GNS3_E2E_URL`` set, that server is used for kernel mode (it must
    already be configured for it); everything else starts an isolated
    instance. Relay-mode tests always need an isolated instance — the
    datapath choice is a server configuration.

    Either way this waits for the controller's local compute to finish
    connecting: the connection's ``GET /capabilities`` runs the uBridge
    probes (several ubridge spawns, seconds), and until it completes the
    controller caches a default dict with every capability None — a test
    reading capabilities in that window would wrongly skip itself.
    """
    url = os.environ.get("GNS3_E2E_URL")
    if url and kernel:
        compute = Compute(
            url,
            os.environ.get("GNS3_E2E_USER", "admin"),
            os.environ.get("GNS3_E2E_PASSWORD", "admin"),
        ).login()
        server = Server(compute)
    else:
        server = _start_isolated(kernel)
    if not wait_until(lambda: (server.compute.capabilities() or {}).get("version"), timeout=45):
        raise AssertionError(
            f"{server.compute.url}: the controller's local compute did not report capabilities within 45s"
        )
    return server


def release(server, project_id, failed=False):
    """Delete the test project (unless it should be kept), then stop the
    isolated instance if this harness started one."""
    if failed and keep_on_failure():
        print(f"\n!! kept project {project_id} on {server.compute.url} for inspection")
    else:
        try:
            server.compute.delete_project(project_id)
        except Exception as e:  # keep the original failure visible
            print(f"!! could not delete project {project_id}: {e}")
    if server.isolated and not (failed and keep_on_failure()):
        server.stop()


# ---------------------------------------------------------------------------
# IOS console (dynamips telnet console)
# ---------------------------------------------------------------------------


class IOSConsole:
    """A deliberately dumb IOS console driver.

    ``run`` sends one line and returns *everything* received until the prompt
    is back and the stream has been quiet — no split between "consumed" and
    "remaining" buffers, so a caller can always parse the whole exchange.
    Pacing matters: the IOS console drops characters typed while it is busy
    (a long boot, the tail of a previous command), so every line goes out
    after the previous exchange has settled.
    """

    def __init__(self, host, port):
        self.sock = socket.create_connection((host, port), timeout=10)
        self.sock.settimeout(0.3)
        self.buf = ""

    def _read(self):
        """Drain whatever arrived; True when at least one byte was read."""
        got = False
        while True:
            try:
                data = self.sock.recv(65536)
            except TimeoutError:
                return got
            if not data:
                return got
            self.buf += data.decode(errors="replace")
            got = True

    def run(self, line, timeout=30, quiet=0.8):
        """Send one line; return the full exchange once the prompt is back
        and nothing new arrived for *quiet* seconds."""
        self.buf = ""
        self.sock.sendall((line + "\r").encode())
        deadline = time.time() + timeout
        last_growth = time.time()
        while time.time() < deadline:
            if self._read():
                last_growth = time.time()
            if PROMPT_RE.search(self.buf) and time.time() - last_growth > quiet:
                break
            time.sleep(0.05)
        out, self.buf = self.buf, ""
        return out

    def boot_wait(self, timeout=360, straight_prompt=False):
        """Wait until the IOS prompt is ready, answering the initial config
        dialog if it appears. The prompt only counts once the stream around
        it goes quiet — a boot banner still printing is not a prompt.

        ``straight_prompt`` accepts a quiet prompt without the "Press RETURN"
        sentinel — images that boot straight from a startup config into the
        CLI (IOL from its NVRAM) never print it."""
        answered = False
        deadline = time.time() + timeout
        self.buf = ""
        last_growth = time.time()
        while time.time() < deadline:
            if self._read():
                last_growth = time.time()
            if not answered and "initial configuration dialog" in self.buf:
                self.sock.sendall(b"no\r")
                answered = True
                last_growth = time.time()
            sentinel = straight_prompt or "Press RETURN" in self.buf or answered
            prompt_seen = sentinel and PROMPT_RE.search(self.buf)
            if prompt_seen and time.time() - last_growth > 1.2:
                self.buf = ""
                return
            if not prompt_seen and time.time() - last_growth > 1.5:
                # nudge the "Press RETURN" prompt along; never nudge an
                # already-visible prompt (the echo would restart the quiet
                # timer forever)
                self.sock.sendall(b"\r")
            time.sleep(0.1)
        raise AssertionError(f"IOS console did not reach a prompt; tail: {self.buf[-300:]!r}")

    def close(self):
        self.sock.close()


def dynamips_console(server, project_id, node_id):
    node = server.compute.node(project_id, node_id)
    host = node["console_host"] if node["console_host"] not in ("0.0.0.0", "::") else "127.0.0.1"
    return IOSConsole(host, node["console"])


def configure_ios(console, hostname, eth_ip=None, serial_ip=None, clock=False, eth_if="f1/0", serial_if="s2/0"):
    """Baseline config on a freshly booted router: hostname, no console spam,
    optional interface addresses."""
    console.run("enable")
    console.run("conf t")
    console.run(f"hostname {hostname}")
    console.run("no ip domain-lookup")
    # global form: console logging off in one step, no line sub-mode to lose
    # characters in
    console.run("no logging console")
    if eth_ip:
        console.run(f"interface {eth_if}")
        console.run(f"ip address {eth_ip} 255.255.255.0")
        console.run("no shutdown")
        console.run("exit")
    if serial_ip:
        console.run(f"interface {serial_if}")
        console.run(f"ip address {serial_ip} 255.255.255.0")
        if clock:
            console.run("clock rate 64000")
        console.run("no shutdown")
        console.run("exit")
    console.run("end")


def ping(console, target, repeat=3, timeout=1):
    """Run an IOS ping; returns {success, avg, raw} (success in percent)."""
    out = console.run(f"ping {target} repeat {repeat} timeout {timeout}", timeout=repeat * timeout + 20)
    success = re.search(r"Success rate is (\d+) percent", out)
    rtt = re.search(r"round-trip min/avg/max = (\d+)/(\d+)/(\d+)", out)
    return {"success": int(success.group(1)) if success else 0, "avg": int(rtt.group(2)) if rtt else None, "raw": out}


def wait_ping(console, target, attempts=4, repeat=3, timeout=1):
    """ping until it fully succeeds (the first packets of a fresh adjacency
    are legitimately lost while the line protocol settles or ARP resolves);
    returns the last result either way."""
    result = None
    for _ in range(attempts):
        result = ping(console, target, repeat=repeat, timeout=timeout)
        if result["success"] == 100:
            return result
        time.sleep(1.5)
    return result


# ---------------------------------------------------------------------------
# Host-side inspection (same machine as the compute)
# ---------------------------------------------------------------------------


def sysfs(path):
    with open(path) as f:
        return f.read().strip()


def tap_exists(name):
    return os.path.exists(f"/sys/class/net/{name}")


def tap_up(name):
    """The tap's administrative state (IFF_UP): what the kernel datapath
    drives for carrier on attach/detach/suspend."""
    return bool(int(sysfs(f"/sys/class/net/{name}/flags"), 16) & 1)


def bridge_members(bridge):
    """Interfaces enslaved to a kernel bridge, or None when the bridge does
    not exist."""
    if not os.path.exists(f"/sys/class/net/{bridge}/brif"):
        return None
    return sorted(os.listdir(f"/sys/class/net/{bridge}/brif"))


# ---------------------------------------------------------------------------
# L2-anchor spec assertions (docs/design/ubridge-l2-anchor-spec.md §E)
# ---------------------------------------------------------------------------

# uBridge's creators harden every host-side datapath device with
# ``link l2only``; these assertions verify the result from the server side.
# They need the probe below to confirm the command exists — the spec's
# degradation contract is a skip on old builds, where anchors keep the
# kernel-default L3 behaviour (measured: 6 frames of MLD/DAD noise per 2 s).


def l2only_supported():
    """Whether this host's uBridge knows ``link l2only`` (probed once).

    Sends the command for a nonexistent device to a throwaway uBridge: a
    208 reply means the command exists, ``202-Unknown command`` an old
    build. Anything unreadable also degrades to False — the L2 assertions
    skip rather than fail, mirroring the tc-capability degradation."""
    global _l2only_support
    if _l2only_support is None:
        _l2only_support = _probe_l2only()
    return _l2only_support


_l2only_support = None


def _probe_l2only():
    ubridge = shutil.which("ubridge")
    if not ubridge:
        return False
    port = _free_port()
    with tempfile.TemporaryDirectory(prefix="gns3-e2e-l2probe-") as workdir:
        # S603: resolved binary, fixed argv, no shell
        proc = subprocess.Popen(  # noqa: S603
            [ubridge, "-H", f"127.0.0.1:{port}"],
            cwd=workdir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            sock = None
            deadline = time.time() + 10
            while time.time() < deadline and sock is None:
                if proc.poll() is not None:
                    return False
                try:
                    sock = socket.create_connection(("127.0.0.1", port), timeout=1)
                except OSError:
                    time.sleep(0.1)
            if sock is None:
                return False
            with sock:
                sock.settimeout(3)
                sock.sendall(b"link l2only e2el2probe0\n")
                buf = b""
                deadline = time.time() + 5
                while time.time() < deadline:
                    try:
                        chunk = sock.recv(4096)
                    except TimeoutError:
                        break
                    if not chunk:
                        break
                    buf += chunk
                    if re.match(rb"\d{3}-", buf.split(b"\n")[0]):
                        break
            reply = buf.decode(errors="replace").splitlines()[0] if buf else ""
            # 208 = the command ran and refused the nonexistent device
            return reply.startswith("208-")
        finally:
            proc.terminate()
            with contextlib.suppress(Exception):
                proc.wait(timeout=5)


def assert_pure_l2(name):
    """§E.1: a host-side datapath device (anchor or bridge) carries no L3
    identity — no IPv4/IPv6 address, and addrgenmode none so none can
    self-provision (no DAD, MLD or RS is ever generated from it)."""
    mode_path = f"/sys/class/net/{name}/addr_gen_mode"
    mode = sysfs(mode_path) if os.path.exists(mode_path) else None
    assert mode in (None, "1"), f"{name}: addr_gen_mode is {mode!r}, expected none ('1')"
    if os.path.exists("/proc/net/if_inet6"):
        with open("/proc/net/if_inet6") as f:
            assigned = [line.strip() for line in f if line.split()[-1] == name]
        assert not assigned, f"{name}: unexpected IPv6 address: {assigned}"
    if not IP:
        raise AssertionError("ip binary not found — cannot verify the anchor has no IPv4 address")
    # S603: resolved binary, fixed argv, no shell
    v4 = subprocess.run(  # noqa: S603
        [IP, "-o", "-4", "addr", "show", "dev", name], capture_output=True, text=True, check=False
    ).stdout.strip()
    assert not v4, f"{name}: unexpected IPv4 address: {v4}"


def brport_state(name):
    """The interface's bridge-port STP state (None when not enslaved); the
    kernel reports 3 for forwarding."""
    path = f"/sys/class/net/{name}/brport/state"
    return sysfs(path) if os.path.exists(path) else None


def assert_forwarding(name):
    """Silent-failure guard found while validating the L2 spec: an attached
    bridge port must be FORWARDING. A bridge device left DOWN keeps its
    ports disabled and forwards nothing — with no error anywhere, this
    assertion is the only signal."""
    state = brport_state(name)
    assert state == "3", f"{name}: bridge port state {state!r}, expected forwarding (3)"


def packet_counters(name):
    """(rx, tx) packet counters of a host interface."""
    return (
        int(sysfs(f"/sys/class/net/{name}/statistics/rx_packets")),
        int(sysfs(f"/sys/class/net/{name}/statistics/tx_packets")),
    )


def assert_idle_silence(*names, settle=2.5, window=5.0):
    """§E.2: after the one-shot enslavement burst settles (the IGMP/MLD
    membership reports of the bridge are accepted residual, see §0), an
    idle device in its normal role shows no traffic for *window* seconds.
    The baseline without the hardening: 6 frames / 2 s, continuous."""
    time.sleep(settle)
    before = {name: packet_counters(name) for name in names}
    time.sleep(window)
    noisy = {name: (before[name], packet_counters(name)) for name in names if packet_counters(name) != before[name]}
    assert not noisy, f"idle devices saw traffic (before -> after): {noisy}"


def link_bridge_name(link_id):
    """The per-link kernel bridge name the controller derives from a link
    id (see UDPLink._prepare)."""
    return "gns3" + link_id.replace("-", "")[:11]


def anchor_name(node_id, adapter, port):
    """The dynamips anchor TAP name for a slot/port (see Router._tap_name)."""
    return "gd" + node_id.replace("-", "")[:8] + f"e{adapter}p{port}"


def iol_anchor_name(node_id, adapter, port):
    """The IOL runner container's anchor TAP name (see IOLDockerVM._tap_name)."""
    return "gx" + node_id.replace("-", "")[:8] + f"e{adapter}p{port}"


def stage_iol_base_config(server):
    """
    Copy the shipped iol-xe base config into an isolated instance's configs
    directory (its GNS3_IOL_STARTUP_CONFIG lookup path) so nodes boot past
    the setup dialog. A no-op for an external server — there the operator's
    install provides it.
    """

    if not server.isolated:
        return
    src = os.path.join(REPO_ROOT, "gns3server", "configs", "iol-xe-base.txt")
    configs_dir = os.path.join(server.tmpdir, "configs")
    os.makedirs(configs_dir, exist_ok=True)
    shutil.copy(src, os.path.join(configs_dir, "iol-xe-base.txt"))


def qdiscs(dev):
    """The tc qdisc listing of a host interface ('' when tc is missing)."""
    if not TC:
        return ""
    # S603: resolved binary, fixed argv, no shell
    result = subprocess.run(  # noqa: S603
        [TC, "qdisc", "show", "dev", dev], capture_output=True, text=True, check=False
    )
    return result.stdout


def wait_until(predicate, timeout=10, interval=0.3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def pcap_records(path):
    """Count the records of a pcap file and collect the ethertype of the
    first few (hex, e.g. '0800') — enough to prove a capture is real."""
    import struct

    ethertypes = []
    with open(path, "rb") as f:
        header = f.read(24)
        if len(header) < 24:
            return 0, ethertypes
        endian = "<" if header[:4] in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
        count = 0
        while True:
            rec = f.read(16)
            if len(rec) < 16:
                break
            _ts, _tus, caplen, _orig = struct.unpack(endian + "IIII", rec)
            data = f.read(caplen)
            if len(data) < caplen:
                break
            count += 1
            if len(ethertypes) < 5 and caplen >= 14:
                ethertypes.append(data[12:14].hex())
    return count, ethertypes
