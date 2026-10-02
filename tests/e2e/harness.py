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
* ``GNS3_E2E_IDLEPC`` — use this idle-PC value for the dynamips routers
  instead of detecting one (see ``dynamips_idlepc``; without an idle-PC each
  router burns a full CPU core for the whole scenario).
* ``GNS3_E2E_DOCKER_IMAGE`` — the image the Docker scenarios run (default
  ``alpine:3``, pinned by digest and pulled on a cache miss; see
  ``ensure_docker_image``).
* ``GNS3_E2E_DOCKER_SOCKET`` — the Docker daemon socket the Docker guest
  driver talks to (default ``/var/run/docker.sock`` — the same daemon the
  server uses).
* ``GNS3_E2E_KEEP=1`` — keep the project (and the isolated instance) when a
  test fails, and print their ids, for inspection.
"""

import contextlib
import http.client
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
import urllib.parse
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

    def create_dynamips_router(self, project_id, name, image, slots, platform="c7200", ram=512, idlepc=None):
        properties = {"platform": platform, "image": image, "ram": ram}
        if idlepc:
            properties["idlepc"] = idlepc
        properties.update(slots)
        return self.call(
            "POST",
            f"/projects/{project_id}/nodes",
            {"compute_id": "local", "name": name, "node_type": "dynamips", "properties": properties},
        )

    def create_docker_node(self, project_id, name, image, adapters=1):
        """A standard Docker node (the veth datapath): the scenario addresses
        its eth0 from the host and pings through it."""
        return self.call(
            "POST",
            f"/projects/{project_id}/nodes",
            {
                "compute_id": "local",
                "name": name,
                "node_type": "docker",
                "properties": {"image": image, "adapters": adapters, "console_type": "telnet"},
            },
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

    def _stop_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)

    def stop(self):
        self._stop_process()
        if self.tmpdir:
            shutil.rmtree(self.tmpdir, ignore_errors=True)

    def restart(self, kernel=True):
        """Restart an isolated instance in place: stop the process — the
        temporary directory (config, controller DB, projects) survives — and
        start a new one on the same paths with the given kernel-datapath
        setting and a fresh port. This is how the reopen-upgrade scenario
        flips the datapath choice and reopens a project created on the
        relay."""
        if not self.isolated:
            raise AssertionError("restart() needs an isolated instance (the harness did not start one)")
        self._stop_process()
        self.process, self.compute = _spawn_isolated(self.tmpdir, kernel)
        return self


def _spawn_isolated(tmpdir, kernel):
    """Start one isolated instance inside *tmpdir* (its config is written
    there; a fresh free port each boot) and return ``(process, compute)``,
    logged in. Shared by the first boot and by ``Server.restart``."""
    ubridge = shutil.which("ubridge")
    dynamips = shutil.which("dynamips")
    if not ubridge:
        pytest.skip("ubridge is not in PATH (needed to start an isolated instance)")
    if not dynamips:
        pytest.skip("dynamips is not in PATH (needed to start an isolated instance)")
    images = os.environ.get("GNS3_E2E_IMAGES", os.path.expanduser("~/GNS3/images"))
    if not os.path.isdir(images):
        pytest.skip(f"images directory not found: {images} (set GNS3_E2E_IMAGES)")

    os.makedirs(os.path.join(tmpdir, "projects"), exist_ok=True)
    port = _free_port()
    config = ISOLATED_CONFIG.format(
        port=port, ubridge=ubridge, dynamips=dynamips, images=images, tmp=tmpdir, kernel=kernel
    )
    config_path = os.path.join(tmpdir, "gns3_server.conf")
    with open(config_path, "w") as f:
        f.write(config)

    log = open(os.path.join(tmpdir, "server.log"), "a")
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
    # The controller's connection to its own local compute comes up
    # asynchronously; until it reports capabilities the compute counts as
    # disconnected and a project open is refused. Same wait as live_server.
    if not wait_until(lambda: (compute.capabilities() or {}).get("version"), timeout=45):
        raise AssertionError(f"{compute.url}: the controller's local compute did not report capabilities within 45s")
    return process, compute


def _start_isolated(kernel):
    tmpdir = tempfile.mkdtemp(prefix="gns3-e2e-")
    process, compute = _spawn_isolated(tmpdir, kernel)
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
# Dynamips idle-PC (CPU)
# ---------------------------------------------------------------------------

# Detected values, keyed by image identity; the detection needs a throwaway
# boot, so it is worth caching across runs.
IDLEPC_CACHE_PATH = os.path.join(os.path.expanduser("~/.cache/gns3-e2e"), "idlepc.json")


def dynamips_idlepc(server, image, platform="c7200", ram=512):
    """The idle-PC value the scenarios' dynamips routers should be created
    with — detected once per image and cached.

    Without one, dynamips busy-waits and burns a *full CPU core per router*
    for the whole scenario: the e2e creates raw nodes, and no template
    supplies an idle-PC. Detection goes through the controller's
    ``auto_idlepc`` endpoint — the GUI's idle-PC finder path: a throwaway
    project boots the image, candidate values are validated by measuring the
    actual process CPU (first candidate under 70 % wins) — and the result is
    cached in ``~/.cache/gns3-e2e/idlepc.json`` keyed by the image's
    checksum, so the cost is paid once per image, not once per run.

    ``GNS3_E2E_IDLEPC`` overrides detection and cache entirely. Any failure
    returns None: the scenarios then run without an idle-PC (and burn the
    cores) rather than fail on a CPU optimisation.
    """
    override = os.environ.get("GNS3_E2E_IDLEPC")
    if override:
        return override

    checksum = None
    for entry in server.compute.call("GET", "/computes/local/dynamips/images"):
        if entry["filename"] == image:
            checksum = entry.get("md5sum")
            break
    key = f"{image}:{checksum}" if checksum else image

    cache = {}
    try:
        with open(IDLEPC_CACHE_PATH) as f:
            cache = json.load(f)
    except (OSError, ValueError):
        pass
    if cache.get(key):
        print(f".. idle-PC {cache[key]} for {image} (cached)")
        return cache[key]

    print(f".. detecting an idle-PC for {image} (once per image — this takes a few minutes)")
    try:
        result = server.compute.call(
            "POST",
            "/computes/local/dynamips/auto_idlepc",
            {"platform": platform, "image": image, "ram": ram},
            timeout=600,
        )
    except Exception as e:
        print(f".. idle-PC detection failed ({e}); the routers will burn a core each")
        return None
    idlepc = (result or {}).get("idlepc")
    if not idlepc:
        print(f".. no idle-PC value found for {image}; the routers will burn a core each")
        return None
    cache[key] = idlepc
    try:
        os.makedirs(os.path.dirname(IDLEPC_CACHE_PATH), exist_ok=True)
        with open(IDLEPC_CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2, sort_keys=True)
    except OSError as e:
        print(f".. could not write the idle-PC cache {IDLEPC_CACHE_PATH}: {e}")
    print(f".. idle-PC {idlepc} for {image} (cached for later runs)")
    return idlepc


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
# Docker guest driver (Docker Engine API over the daemon socket)
# ---------------------------------------------------------------------------

# The e2e needs two things the server's REST surface does not expose: the
# identity of the image a container runs (to verify a cached image is the
# pinned build) and a way to run commands inside a booted container (address
# the guest, drive real ICMP from it). Both are plain Engine API calls over
# the same socket the server itself uses.

DOCKER_SOCKET = os.environ.get("GNS3_E2E_DOCKER_SOCKET", "/var/run/docker.sock")

# The image the Docker scenarios run. Both the registry digest (what to pull
# on a cache miss; a rolling tag resolved once and then pinned forever) and
# the repo-digest it must resolve to locally are pinned, so every developer
# tests the same bytes. The Docker daemon is the cache: a hit costs no
# network, a miss pulls through the server's own route (the WebUI's path),
# and no cache + no registry skips the scenario.
DOCKER_IMAGE = "alpine:3"
DOCKER_IMAGE_DIGEST = "sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b"


class _UnixHTTPConnection(http.client.HTTPConnection):
    """An HTTP connection speaking over a Unix socket (stdlib only)."""

    def __init__(self, socket_path, timeout):
        super().__init__("localhost", timeout=timeout)
        self._socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._socket_path)


class DockerDaemon:
    """Minimal Docker Engine API client over the daemon socket."""

    def __init__(self, socket_path=DOCKER_SOCKET, timeout=60):
        self.socket_path = socket_path
        self.timeout = timeout

    def _request(self, method, path, body=None, timeout=None):
        conn = _UnixHTTPConnection(self.socket_path, timeout or self.timeout)
        try:
            data = None
            headers = {}
            if body is not None:
                data = json.dumps(body).encode()
                headers["Content-Type"] = "application/json"
            conn.request(method, path, body=data, headers=headers)
            response = conn.getresponse()
            return response.status, response.read()
        except (OSError, http.client.HTTPException) as e:
            raise AssertionError(f"docker {method} {path} failed: {e}") from None
        finally:
            conn.close()

    def container_id(self, name):
        """The id of the container called *name* (any state), or None. The
        controller's node payload does not carry a Docker node's container
        id (a compute-side read-only field); the daemon knows the container
        by the deterministic name the server gives it (DockerVM.docker_name:
        ``GNS3.<node name>.<project id>``)."""
        filters = urllib.parse.quote(json.dumps({"name": [name]}), safe="")
        status, payload = self._request("GET", f"/containers/json?all=1&filters={filters}")
        assert status == 200, f"docker container list -> HTTP {status}: {payload[:300]!r}"
        for container in json.loads(payload):
            if name in [entry.lstrip("/") for entry in container.get("Names") or []]:
                return container["Id"]
        return None

    def image_inspect(self, reference):
        """The image record stored under *reference*, or None."""
        status, payload = self._request("GET", "/images/" + urllib.parse.quote(reference, safe="") + "/json")
        if status == 404:
            return None
        assert status == 200, f"docker image inspect {reference} -> HTTP {status}: {payload[:300]!r}"
        return json.loads(payload)

    def pull(self, reference, timeout=600):
        """Pull *reference* (digest-pinned when the caller wants
        reproducibility). Raises AssertionError on the daemon's error
        stream — offline, unknown manifest, ..."""
        status, payload = self._request(
            "POST", "/images/create?fromImage=" + urllib.parse.quote(reference, safe=""), timeout=timeout
        )
        if status != 200:
            raise AssertionError(f"docker pull {reference} -> HTTP {status}: {payload[:300]!r}")
        # the body is a stream of JSON progress objects; any object carrying
        # an error key (in either shape) is a failure
        text = payload.decode(errors="replace").strip()
        decoder = json.JSONDecoder()
        while text:
            try:
                obj, index = decoder.raw_decode(text)
            except ValueError:
                break
            error = obj.get("error") or (obj.get("errorDetail") or {}).get("message")
            if error:
                raise AssertionError(f"docker pull {reference} failed: {error}")
            text = text[index:].strip()

    def exec(self, container_id, cmd, timeout=60):
        """Run *cmd* inside a container; returns (exit_code, combined
        output)."""
        status, payload = self._request(
            "POST",
            f"/containers/{container_id}/exec",
            {"AttachStdout": True, "AttachStderr": True, "Tty": False, "Cmd": list(cmd)},
        )
        assert status == 201, f"docker exec create in {container_id[:12]} -> HTTP {status}: {payload[:300]!r}"
        exec_id = json.loads(payload)["Id"]
        try:
            status, payload = self._request(
                "POST", f"/exec/{exec_id}/start", {"Detach": False, "Tty": False}, timeout=timeout
            )
        except AssertionError as e:
            # A stalled stream is diagnosable: was the process still running
            # (stream open, nothing flushed) or already gone?
            raise AssertionError(f"{e} (exec {exec_id[:12]} still running: {self._exec_running(exec_id)})") from None
        assert status == 200, f"docker exec start {exec_id[:12]} -> HTTP {status}: {payload[:300]!r}"
        # the hijacked stream multiplexes stdout/stderr: 8-byte frame headers
        # (stream id + big-endian length) — demultiplex into one buffer
        output = bytearray()
        index = 0
        while index + 8 <= len(payload):
            length = int.from_bytes(payload[index + 4 : index + 8], "big")
            output += payload[index + 8 : index + 8 + length]
            index += 8 + length
        status, payload = self._request("GET", f"/exec/{exec_id}/json")
        assert status == 200, f"docker exec inspect {exec_id[:12]} -> HTTP {status}: {payload[:300]!r}"
        return json.loads(payload)["ExitCode"], output.decode(errors="replace")

    def _exec_running(self, exec_id):
        """Whether an exec is still running (diagnostic only, never raises)."""
        try:
            status, payload = self._request("GET", f"/exec/{exec_id}/json", timeout=10)
            return json.loads(payload).get("Running") if status == 200 else f"HTTP {status}"
        except (AssertionError, ValueError):
            return "unknown"


def ensure_docker_image(server):
    """The Docker image the scenarios run, ensured present locally.

    The pinned reference (``DOCKER_IMAGE``, digest ``DOCKER_IMAGE_DIGEST``)
    is pulled through the server's own pull route on a cache miss and
    verified against the pinned repo digest afterwards. A cached image that
    resolves to another digest is used with a warning if the pull fails
    (offline developer), but with no cached image and no registry the
    scenario skips. ``GNS3_E2E_DOCKER_IMAGE`` overrides the reference
    entirely (the operator then owns its content)."""

    override = os.environ.get("GNS3_E2E_DOCKER_IMAGE")
    daemon = DockerDaemon()
    if override:
        info = daemon.image_inspect(override)
        if info is None:
            pytest.skip(f"GNS3_E2E_DOCKER_IMAGE={override} is not present on the Docker daemon")
        print(f".. using GNS3_E2E_DOCKER_IMAGE={override} ({info['Id'][:19]}…)")
        return override

    reference = f"{DOCKER_IMAGE}@{DOCKER_IMAGE_DIGEST}"
    info = daemon.image_inspect(DOCKER_IMAGE)
    if info is not None and any(DOCKER_IMAGE_DIGEST in d for d in (info.get("RepoDigests") or [])):
        print(f".. Docker image {DOCKER_IMAGE} is cached at the pinned digest ({info['Id'][:19]}…)")
        return DOCKER_IMAGE
    if info is None:
        print(f".. Docker image {DOCKER_IMAGE} is not cached — pulling the pinned digest")
    else:
        print(
            f".. cached {DOCKER_IMAGE} is {info.get('RepoDigests') or info['Id'][:19]}…, not the pinned digest — pulling"
        )
    try:
        server.compute.call("POST", "/computes/local/docker/images/pull", {"image": reference}, timeout=600)
    except AssertionError as e:
        if info is None:
            pytest.skip(f"Docker image {DOCKER_IMAGE} is not cached and could not be pulled: {e}")
        print(f".. pull failed ({e}); using the cached {DOCKER_IMAGE} — not the pinned build")
        return DOCKER_IMAGE
    print(f".. pulled {reference}")
    return DOCKER_IMAGE


def configure_docker_interfaces(node, address, netmask="255.255.255.0", adapter=0):
    """Give the container's eth{adapter} a static address the way a GNS3
    user does: write the persistent ``/etc/network/interfaces`` the server
    bind-mounts into the container and init.sh applies with busybox ifup at
    boot (CIDR is not understood — separate address/netmask lines). Call
    before starting the node."""
    directory = node.get("node_directory")
    if not directory or not os.path.isdir(directory):
        pytest.skip(f"cannot reach the node directory {directory!r} — this scenario needs the compute on this host")
    path = os.path.join(directory, "etc", "network", "interfaces")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(f"auto eth{adapter}\niface eth{adapter} inet static\n\taddress {address}\n\tnetmask {netmask}\n")


def docker_wait_address(daemon, container_id, address, timeout=30):
    """Wait until the container's eth0 carries *address* — init.sh applies
    the interfaces file (busybox ifup) a moment after container start."""

    def present():
        _code, output = daemon.exec(container_id, ["ip", "-4", "-o", "addr", "show", "dev", "eth0"])
        return address in output

    if not wait_until(present, timeout=timeout, interval=0.5):
        raise AssertionError(f"container {container_id[:12]} did not configure {address} within {timeout}s")


_BUSYBOX_PING_LOSS_RE = re.compile(r"(\d+)% packet loss")
_BUSYBOX_PING_RTT_RE = re.compile(r"round-trip min/avg/max = [\d.]+/([\d.]+)/[\d.]+ ms")


def docker_ping(daemon, container_id, target, count=3, timeout=1, interval=0.2, size=None):
    """Run a real busybox ping inside a container; returns
    ``{loss, avg, raw, exit}`` (loss in percent, avg in ms). The default
    0.2 s interval packs more samples into loss measurements; loss-based
    checks pass a higher count.

    The ping is wrapped in busybox `timeout` with a generous cap so a
    misbehaving guest can never hold the exec stream open past it — the
    harness then reports a normal failed ping instead of a socket timeout.
    """
    cap = int(count * interval + timeout + 15)
    cmd = ["timeout", str(cap), "ping", "-c", str(count), "-W", str(timeout)]
    if interval is not None:
        cmd += ["-i", str(interval)]
    if size is not None:
        cmd += ["-s", str(size)]
    cmd.append(target)
    code, output = daemon.exec(container_id, cmd, timeout=cap + 10)
    loss = _BUSYBOX_PING_LOSS_RE.search(output)
    rtt = _BUSYBOX_PING_RTT_RE.search(output)
    return {
        "loss": int(loss.group(1)) if loss else 100,
        "avg": float(rtt.group(1)) if rtt else None,
        "raw": output,
        "exit": code,
    }


def docker_wait_ping(daemon, container_id, target, attempts=4, **kwargs):
    """ping until it fully succeeds (a fresh veth/bridge needs a beat for
    carrier and ARP); returns the last result either way."""
    result = None
    for _ in range(attempts):
        result = docker_ping(daemon, container_id, target, **kwargs)
        if result["loss"] == 0:
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


def docker_anchor_name(node_id, adapter, port=0):
    """The standard Docker node's anchor: the veth host end the server keeps
    in the root namespace (see DockerKernelDatapathMixin._veth_names and
    utils.kernel_anchor)."""
    return "gv" + node_id.replace("-", "")[:8] + f"e{adapter}p{port}"


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
