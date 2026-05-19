# GNS3 Linux Bridge + eBPF + Containerlab Integration Roadmap

---

**Copyright (C) 2026 GNS3 Technologies Inc.**

This work is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License (CC BY-SA 4.0).

For full license terms, see: [../LICENSE](../LICENSE)

---

## Executive Summary

**Objective**: Migrate GNS3 from ubridge-based networking to a hybrid **Linux bridge + eBPF + Containerlab** architecture.

**Key Benefits (Design Targets)**:
- ⚡ **Performance**: Target 4x throughput improvement for local connections
- 🔌 **Ecosystem**: Access to containerlab's rich network device catalog
- 🔥 **eBPF Support**: Kernel-space packet processing with near-zero overhead
- 🚀 **CI/CD Ready**: Better automation and cloud-native integration

> **Note**: Performance figures throughout this document are **design targets**, not measured benchmarks. Actual gains depend on workload, kernel version, NIC offloading, and node type. A Phase 1 POC is required to validate these assumptions before committing to subsequent phases.

---

## Architecture Overview

### High-Level Architecture

```mermaid
graph TB
    subgraph "GNS3 Controller"
        Controller[Controller Layer]
    end

    subgraph "Compute Node 1"
        GNS1[GNS3 Node QEMU]
        GNS2[GNS3 Node Docker]
        LB1[Linux Bridge]
        UB1[Ubridge UDP]

        GNS1 -->|veth| LB1
        GNS2 -->|veth| LB1
        LB1 -->|veth| UB1
    end

    subgraph "Compute Node 2"
        CL1[Containerlab Node]
        CL2[Containerlab Node]
        LB2[Linux Bridge]
        UB2[Ubridge UDP]

        CL1 -->|veth| LB2
        CL2 -->|veth| LB2
        LB2 -->|veth| UB2
    end

    subgraph "Network Layer"
        Net[Physical Network]
    end

    UB1 -->|UDP Tunnel| Net
    Net -->|UDP Tunnel| UB2

    Controller --> GNS1
    Controller --> GNS2
    Controller --> CL1
    Controller --> CL2
```

### Network Backend Decision Flow

```mermaid
flowchart TD
    Start[Link Creation Request] --> CheckCompute{Nodes on Same Compute?}

    CheckCompute -->|Yes| LocalUse[Use Linux Bridge Backend]
    CheckCompute -->|No| RemoteUse[Use Hybrid Backend]

    LocalUse --> CreateLB[Create Linux Bridge]
    CreateLB --> AddVeth1[Create veth pairs for nodes]
    AddVeth1 --> AttachLB[Attach to bridge]
    AttachLB --> CompleteLocal[Local Link Complete]

    RemoteUse --> CreateHybrid[Create Hybrid Backend]
    CreateHybrid --> CreateLB2[Create Linux Bridge Local]
    CreateLB2 --> CreateUBridge[Create Ubridge Instance]
    CreateUBridge --> ConnectLBUB[Connect Bridge to Ubridge]
    ConnectLBUB --> SetupUDP[Setup UDP Tunnel]
    SetupUDP --> CompleteRemote[Remote Link Complete]
```

---

## Phase 1: Foundation & Abstraction Layer

### Network Backend Abstraction

**Goal**: Create a unified interface that supports multiple network implementations.

**Design Principles**:
- Pluggable backend architecture
- Backward compatibility with ubridge
- Performance-optimized path selection
- Seamless fallback mechanisms

### Backend Type Comparison

| Backend Type | Use Case | Performance | Complexity |
|--------------|----------|-------------|------------|
| **Pure Linux Bridge** | Local connections (same compute) | Highest (>20 Gbps) | Low |
| **Hybrid (Linux Bridge + Ubridge)** | Remote connections | Medium (>2 Gbps) | Medium |
| **Pure Ubridge** | Fallback/legacy | Baseline (~5 Gbps local) | Low |

### Component Architecture

```mermaid
graph LR
    subgraph "Abstraction Layer"
        Base[NetworkBackend Interface]
    end

    subgraph "Implementations"
        LB[LinuxBridgeBackend]
        HB[HybridBackend]
        UB[UbridgeBackend]
    end

    subgraph "Supporting Components"
        VM[Veth Manager]
        BM[Bridge Manager]
        UM[Ubridge Manager]
        EBL[eBPF Loader]
    end

    Base --> LB
    Base --> HB
    Base --> UB

    LB --> VM
    LB --> BM
    LB --> EBL

    HB --> VM
    HB --> BM
    HB --> UM

    UB --> UM
```

**Key Interfaces**:

| Method | Purpose | Implementation Variants |
|--------|---------|------------------------|
| `create_bridge()` | Create network bridge | Linux bridge command / ubridge bridge create |
| `add_node_interface()` | Connect node to bridge | veth pair / ubridge nio_tap |
| `add_udp_tunnel()` | Setup remote connection | ubridge nio_udp only |
| `apply_filters()` | Apply packet filters | eBPF XDP/TC / ubridge filters |
| `delete()` | Cleanup resources | Remove bridge / stop ubridge |

### Node Type Adaptation Strategy

Connecting each node type to a Linux bridge requires different strategies. The current codebase has no uniform "attach to bridge" path — each node type implements `adapter_add_nio_binding()` independently.

| Node Type | Current Connection | Linux Bridge Adapter | Complexity | Work Required |
|-----------|-------------------|---------------------|------------|---------------|
| **Docker** | ubridge TAP + UDP NIO | TAP already present; replace ubridge bridge with `ip link set tapX master brY` | Low | Add namespace-aware veth, keep tap for container-side |
| **QEMU** | UDP NIO → ubridge bridge | Add `-netdev tap` or use vhost-user intermediary | Medium | QEMU must connect to a tap on the Linux bridge; replace UDP NIO with tap on `brY` |
| **VPCS** | UDP NIO → ubridge bridge | Host-level veth pair, one end on Linux bridge, other to VPCS UDP | Medium | VPCS is a userspace process; needs a local UDP ↔ veth bridge helper if direct tap impossible |
| **IOU** | UDP NIO → ubridge bridge | Same as VPCS — veth + local helper | Medium | IOU is also userspace; similar helper approach |
| **Dynamips** | UDP NIO → ubridge bridge | Same as VPCS/IOU | Medium | Dynamips is userspace |
| **Cloud** | ubridge bridge (per-port) | Direct Linux bridge via `ip link` | Low | Cloud already manages interface attachments; replace ubridge bridge with `brctl`/`ip link` |
| **Ethernet Switch** | ubridge bridge | Direct Linux bridge (kernel already has bridging) | Low | Native `ip link add brX type bridge` |

**Userspace Node Helper**: For VPCS, IOU, and Dynamips (processes that speak UDP directly), a lightweight local shim (`localhost:UDP ⇄ veth`) is needed. This could be a new `gns3-bridge-helper` process or a small eBPF program, and is one of the highest-risk items in Phase 1.

### Controller Layer Refactoring

The current `UDPLink.create()` (`gns3server/controller/udp_link.py:49`) hard-codes a UDP tunnel flow:

```
allocate UDP port on compute A → allocate UDP port on compute B → create NIOUDP on both
```

For local links on a Linux bridge, a new `LocalLink` subclass (or feature flag on `UDPLink`) is needed:

```
detect same-compute → skip UDP allocation → attach both nodes to shared Linux bridge via veth
```

The decision logic belongs in `controller/link.py` or a new link factory. The `Link` base class (`controller/link.py:69`) provides `create()` / `update()` / `delete()` — these must be overridden without assuming UDP endpoints.

### Configuration Schema Additions

The config schema at `gns3server/schemas/config.py` must be extended with new settings:

```python
class LinuxBridgeSettings(BaseModel):
    enable_local_bridge: bool = False
    bridge_prefix: str = "gns3"
    veth_prefix: str = "veth"
    mtu: int = 1500

class EBPSettings(BaseModel):
    enabled: bool = False
    program_directory: str = "/var/lib/gns3/ebpf"

class ContainerlabSettings(BaseModel):
    enabled: bool = False
    api_endpoint: str = "http://localhost:5000"

class HybridSettings(BaseModel):
    auto_detect_local: bool = True
    prefer_linux_bridge: bool = True
```

These are then composed into `ServerConfig` — none exist today.

### Port Management Implications

`PortManager` (`gns3server/compute/port_manager.py`) currently reserves UDP ports for all links. With Linux bridges for local connections, same-compute links would not consume UDP ports at all. The `get_free_udp_port()` / `release_udp_port()` calls in `UDPLink.create()` must become conditional on the backend decision.

---

## Phase 2: Linux Bridge + Hybrid Ubridge Architecture

### Multi-Compute Hybrid Architecture

This is the **core architecture** enabling optimal performance across distributed deployments.

#### Architecture Diagram

```mermaid
graph TB
    subgraph "Compute Node 1"
        N1[Node A - QEMU]
        N2[Node B - Docker]
        N3[Node C - IOU]

        LB1[Linux Bridge<br/>gns3-comp1-xxxx]

        UB1[Ubridge UDP Tunnel<br/>Endpoint]

        N1 -->|veth| LB1
        N2 -->|veth| LB1
        N3 -->|veth| LB1
        LB1 -->|veth| UB1
    end

    subgraph "Compute Node 2"
        N4[Node D - Nokia SR Linux]
        N5[Node E - Arista EOS]

        LB2[Linux Bridge<br/>gns3-comp2-yyyy]

        UB2[Ubridge UDP Tunnel<br/>Endpoint]

        N4 -->|veth| LB2
        N5 -->|veth| LB2
        LB2 -->|veth| UB2
    end

    subgraph "Physical Network"
        NET[Network Infrastructure]
    end

    UB1 -->|UDP Packet<br/>src:192.168.1.10:10000<br/>dst:192.168.1.21:10001| NET
    NET -->|UDP Packet<br/>src:192.168.1.21:10001<br/>dst:192.168.1.10:10000| UB2
```

#### Packet Flow: Local vs Remote

**Local Connection (Node A → Node B)**:
```mermaid
sequenceDiagram
    participant NA as Node A (QEMU)
    participant LB as Linux Bridge
    participant NB as Node B (Docker)

    NA->>LB: Packet via veth
    Note over LB: Kernel-space<br/>switching
    LB->>NB: Forward via veth

    Note over NA,NB: <10μs latency<br/>>20 Gbps throughput
```

**Remote Connection (Node A → Node D)**:
```mermaid
sequenceDiagram
    participant NA as Node A (Comp1)
    participant LB1 as Linux Bridge 1
    participant UB1 as Ubridge 1
    participant NET as Network
    participant UB2 as Ubridge 2
    participant LB2 as Linux Bridge 2
    participant ND as Node D (Comp2)

    NA->>LB1: Packet via veth
    LB1->>UB1: Forward via veth
    UB1->>NET: UDP encapsulation
    NET->>UB2: UDP packet
    UB2->>LB2: Decapsulate
    LB2->>ND: Forward via veth

    Note over NA,ND: <50μs latency<br/>>2 Gbps throughput
```

### Hybrid Backend Components

| Component | Responsibility | Technology |
|-----------|---------------|------------|
| **Linux Bridge Manager** | Create/delete bridges | `ip link add bridge` |
| **Veth Manager** | Create veth pairs | `ip link add veth` |
| **Bridge-Ubridge Connector** | Connect bridge to ubridge | veth pair + tap |
| **UDP Tunnel Manager** | Setup cross-compute tunnels | ubridge nio_udp |
| **eBPF Loader** | Attach filters to bridge | XDP/TC programs |

### Connection Decision Matrix

| Node A Location | Node B Location | Backend Used | Data Path |
|----------------|-----------------|--------------|-----------|
| Compute 1 | Compute 1 | Pure Linux Bridge | Kernel-space |
| Compute 1 | Compute 2 | Hybrid (LB + Ubridge UDP) | Kernel → User → Network |
| Compute 1 | Compute 3 | Hybrid (LB + Ubridge UDP) | Kernel → User → Network |
| Compute 1 (non-Linux) | Compute 1 | Pure Ubridge | User-space |

### Network Namespace Handling for Container Nodes

Docker containers run in isolated network namespaces. Connecting them to a host Linux bridge requires crossing namespace boundaries — this is a critical complexity that differs from ubridge's approach (which operates in host context via TAP interfaces).

**Current ubridge path** (Docker VM in `gns3server/compute/docker/docker_vm.py`):
```
Container eth0 ↔ host TAP (created in container ns) ↔ ubridge userspace bridge ↔ UDP NIO
```

**Proposed Linux bridge path**:
```
Container eth0 ↔ host TAP ↔ Linux bridge (host ns)
```

| Component | Namespace | Challenge |
|-----------|-----------|-----------|
| Linux bridge | Host | Always in host namespace |
| veth pair end | Host → Container | One end moved with `ip link set netns` |
| Docker container | Isolated | TAP already created inside; need to find host-side ifindex |

**Implementation approach**:

```python
# Attach Docker container interface to host bridge
tap_iface = f"tap{adapter_number}"  # already exists in container ns
host_tag = f"veth{node_id[:8]}{adapter_number}"

# Create veth pair and move one end into container
await run(f"ip link add {host_tag} type veth peer name {tap_iface}")
await run(f"ip link set {tap_iface} netns {container_id}")
await run(f"ip link set {host_tag} master {bridge_name}")
await run(f"ip link set {host_tag} up")
await run(f"ip netns exec {container_id} ip link set {tap_iface} up")
```

**Key risks**:
- Requires `CAP_NET_ADMIN` and `CAP_SYS_ADMIN` for namespace operations
- Container restart loses interfaces — GNS3 must re-attach on restart
- Mixed namespace environments (some Docker, some QEMU, some VPCS) increase complexity
- The current `_add_ubridge_connection()` in `docker_vm.py:1112` would need a parallel code path

---

## Phase 3: eBPF Integration

### eBPF Architecture

```mermaid
graph TB
    subgraph "Application Layer"
        App[GNS3 Application]
    end

    subgraph "eBPF Programs"
        XDP[XDP Layer - L2/L3 Processing]
        TC[TC Layer - L4+ Processing]
    end

    subgraph "eBPF Maps"
        CFG[Configuration Maps]
        STATS[Statistics Maps]
        STATE[State Tracking]
    end

    subgraph "Linux Kernel"
        Kernel[Kernel Network Stack]
    end

    App -->|Configure| XDP
    App -->|Configure| TC

    XDP -->|Read/Write| CFG
    TC -->|Read/Write| CFG

    XDP -->|Update| STATS
    TC -->|Update| STATS

    XDP -->|Access| STATE
    TC -->|Access| STATE

    XDP -->|Hook into| Kernel
    TC -->|Hook into| Kernel
```

### eBPF Filter Types

| Filter Type | Hook Point | Use Case | Performance Impact |
|-------------|------------|----------|-------------------|
| **Packet Loss** | XDP | Simulate packet drops | <1μs |
| **Delay Injection** | TC | Add latency to packets | ~5μs |
| **Corruption** | XDP | Modify packet contents | <1μs |
| **Bandwidth Limit** | TC | Traffic shaping | ~2μs |
| **Custom BPF** | XDP/TC | User-defined filters | Variable |
| **Connection Tracking** | TC | Stateful filtering | ~10μs |

### eBPF vs Userspace Filters

```mermaid
graph LR
    subgraph "Userspace Filters Current"
        UF1[Packet Capture]
        UF2[Userspace Processing]
        UF3[Filter Application]
        UF4[Packet Forward]

        UF1 -->|50μs| UF2
        UF2 -->|20μs| UF3
        UF3 -->|10μs| UF4
    end

    subgraph "eBPF Filters Proposed"
        EF1[Packet Capture]
        EF2[eBPF Processing]
        EF3[Kernel Forward]

        EF1 -->|<5μs| EF2
        EF2 -->|<1μs| EF3
    end
```

**Performance Comparison**:

| Metric | Userspace | eBPF | Improvement |
|--------|-----------|------|-------------|
| Packet processing | ~50μs | ~5μs | 10x faster |
| CPU overhead | 15-20% | <5% | 4x better |
| Max throughput | ~5 Gbps | ~20 Gbps | 4x higher |
| Dynamic updates | Requires restart | Hot reload | Instant |

### eBPF Program Categories

| Category | Programs | Complexity | Use Cases |
|----------|----------|------------|-----------|
| **Basic Filters** | Drop, Delay, Corrupt | Low | Network simulation |
| **Advanced Filters** | Bandwidth, QoS | Medium | Traffic engineering |
| **Stateful Filters** | Connection tracking | High | Stateful inspection |
| **Analytics** | Packet counting, timing | Medium | Monitoring |
| **Custom** | User-defined | Variable | Specialized needs |

### eBPF Build Pipeline & Distribution

eBPF programs are written in C and compiled to BPF bytecode. This introduces a build dependency not present in the Python-only codebase today.

**Source Structure**:
```
gns3-server/
├── gns3server/
│   ├── ebpf/                    # eBPF C source programs
│   │   ├── Makefile
│   │   ├── drop.c
│   │   ├── delay.c
│   │   ├── bandwidth.c
│   │   ├── monitor.c
│   │   └── include/
│   │       └── common.h
│   └── compute/
│       ├── ebpf/
│       │   ├── loader.py        # Load/attach/detach eBPF programs
│       │   └── maps.py          # eBPF map management
```

**Build Requirements**:

| Tool | Version | Purpose |
|------|---------|---------|
| `clang` | >= 12.0 | Compile C to BPF bytecode |
| `llvm` | >= 12.0 | BPF backend for target `bpf` |
| `libbpf` | >= 1.0 | Userspace library for loading (or `ctypes` bindings) |
| `kernel-headers` | Match running kernel | Required for `vmlinux.h` / BTF |

**CO-RE (Compile Once, Run Everywhere) Strategy**:

Pre-compiled `.o` files should be shipped with the Python package using BTF relocation:

1. Build: `clang -target bpf -O2 -c drop.c -o drop.o`
2. Ship: Include `drop.o` in the Python package (`gns3server/ebpf/programs/`)
3. Load: libbpf performs CO-RE relocation against the running kernel's BTF info
4. Fallback: If `/sys/kernel/btf/vmlinux` is unavailable → log warning, ubridge filter fallback

**Runtime Loading**:
```python
# gns3server/compute/ebpf/loader.py
async def load_xdp_program(interface: str, program_path: str) -> int:
    """Load eBPF XDP program onto interface using libbpf."""
    # Uses ctypes or pyroute2 to:
    # 1. Open and load .o file via libbpf
    # 2. Pin maps to bpffs
    # 3. Attach XDP program to interface
    # Returns fd for later detach
```

**Fallback Architecture**:
- If eBPF is unavailable (kernel < 5.8, no BTF, no permissions): ubridge filters are used
- If eBPF loading fails at runtime: per-link fallback to ubridge filter path
- Config knob: `[eBPF] enabled = false` to skip eBPF entirely

**Cross-Platform Constraints**:
- eBPF is Linux-only. On macOS/Windows, all eBPF config is ignored and ubridge remains the sole backend.
- Unit tests can use `unittest.mock` to simulate eBPF loader responses.
- Integration tests require a VM with kernel >= 5.8.

---

## Phase 4: Containerlab Integration

### Integration Architecture

```mermaid
graph TB
    subgraph "GNS3 Ecosystem"
        GNS3[GNS3 Server]
        GNS3Nodes[GNS3 Nodes<br/>QEMU, Docker, IOU]
    end

    subgraph "Containerlab Ecosystem"
        CLAB[Containerlab Runtime]
        CLABNodes[Containerlab Nodes<br/>Nokia SR, Arista EOS, Cisco XR]
    end

    subgraph "Integration Layer"
        API[Containerlab API Client]
        CONV[Topology Converter]
        SYNC[Bridge Sync Manager]
    end

    subgraph "Network Fabric"
        LB[(Linux Bridges)]
        VETH[veth pairs]
    end

    GNS3 <--> API
    CLAB <--> API

    GNS3 --> CONV
    CLAB --> CONV

    CONV --> SYNC
    SYNC --> LB
    LB --> VETH

    GNS3Nodes --> LB
    CLABNodes --> LB
```

### Topology Conversion Flow

```mermaid
flowchart LR
    subgraph "GNS3 to Containerlab"
        G1[GNS3 Topology<br/>.gns3] --> P1[Parse XML/JSON]
        P1 --> C1[Convert Nodes]
        C1 --> C2[Convert Links]
        C2 --> G2[Generate YAML<br/>.clab.yml]
        G2 --> D1[Deploy to Containerlab]
    end

    subgraph "Containerlab to GNS3"
        C3[Containerlab Topology<br/>.clab.yml] --> P2[Parse YAML]
        P2 --> C4[Convert Nodes]
        C4 --> C5[Convert Links]
        C5 --> G3[Create GNS3 Project]
    end
```

### Node Type Mapping

| GNS3 Node Type | Containerlab Kind | Conversion Complexity | Notes |
|----------------|-------------------|----------------------|-------|
| Docker | docker | Low | Direct mapping |
| QEMU | vm | Medium | Needs VM configuration |
| IOU | N/A | High | Requires container wrapper |
| Ethernet Switch | bridge | Low | Native Linux bridge |
| Cloud | bridge | Low | Special bridge config |
| Nokia SR Linux | nokia_srl | Low | Native support |
| Arista EOS | arista_ceos | Low | Native support |

### Bridge Synchronization

```mermaid
sequenceDiagram
    participant G as GNS3 Bridge
    participant S as Sync Manager
    participant C as Containerlab Bridge
    participant V as veth Connector

    G->>S: Discover GNS3 bridges
    C->>S: Discover Containerlab bridges
    S->>S: Identify shared topology
    S->>V: Create veth pair
    V->>G: Attach end to GNS3 bridge
    V->>C: Attach end to Containerlab bridge
    S->>S: Verify connectivity
    Note over G,C: Hybrid topology connected
```

### Integration Benefits

| Aspect | GNS3 Standalone | Containerlab Standalone | Integrated |
|--------|----------------|------------------------|------------|
| Network Devices | Limited | Extensive | ✅ Both ecosystems |
| Performance | Good (ubridge) | Excellent (Linux) | ✅ Linux bridge |
| Vendor Images | Community | Official | ✅ Official support |
| CI/CD Integration | Basic | Excellent | ✅ Inherits advantages |
| Development Speed | Medium | Fast | ✅ Accelerated |

### Containerlab Lifecycle Management

Containerlab is an external process, not a Python library. GNS3 must manage its lifecycle explicitly.

**Process Model**:

| Responsibility | Owner | Details |
|----------------|-------|---------|
| **Start containerlab** | GNS3 Server | `subprocess.run(["containerlab", "deploy", "-t", topo.yml])` when a containerlab-backed project opens |
| **Stop containerlab** | GNS3 Server | `containerlab destroy -t topo.yml` when project closes |
| **Detect changes** | Polling / Hook | Containerlab has no push API; GNS3 must either poll `containerlab inspect` or hook into containerlab logs |
| **Error recovery** | GNS3 Server | Detect `containerlab` process exit, reconcile with project state |

**Topology Synchronization Challenges**:

| Direction | Challenge | Approach |
|-----------|-----------|----------|
| GNS3 → Containerlab | GNS3 links modified after deploy | Must regenerate `.clab.yml` and call `containerlab deploy --reconfigure` |
| Containerlab → GNS3 | External `containerlab` CLI commands modify topology | Periodic `containerlab inspect` → diff → update GNS3 project model |
| Concurrent modification | User changes both GNS3 GUI and containerlab CLI | Last-writer-wins with warning; document as unsupported |

**Implementation Sketch**:
```python
class ContainerlabManager:
    """Manages a containerlab instance for a GNS3 project."""

    def __init__(self, project_id: str):
        self._project_id = project_id
        self._process: asyncio.subprocess.Process | None = None
        self._topology_path: str | None = None

    async def deploy(self, topology: ClabTopology) -> bool:
        """Convert GNS3 topology to .clab.yml and run containerlab deploy."""
        yaml_content = self._convert_to_clab(topology)
        self._topology_path = os.path.join(
            self._project_dir, "containerlab.yml"
        )
        with open(self._topology_path, "w") as f:
            f.write(yaml_content)
        proc = await asyncio.create_subprocess_exec(
            "containerlab", "deploy", "-t", self._topology_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode == 0

    async def destroy(self):
        """Tear down containerlab topology."""
        if self._topology_path:
            proc = await asyncio.create_subprocess_exec(
                "containerlab", "destroy", "-t", self._topology_path,
                "--cleanup"
            )
            await proc.wait()
```

**Dependencies**:
- Containerlab must be installed and in `$PATH`
- Requires Docker (containerlab dependency)
- Root/CAP_NET_ADMIN for bridge operations
- Not available on macOS/Windows

---

## Deployment Scenarios

### Scenario 1: Single Compute, All Local

```mermaid
graph TB
    subgraph "Single Compute Node"
        N1[Node 1]
        N2[Node 2]
        N3[Node 3]
        N4[Node 4]
        LB[Linux Bridge]

        N1 --> LB
        N2 --> LB
        N3 --> LB
        N4 --> LB
    end

    style LB fill:#90EE90
```

**Characteristics**:
- All nodes on same physical machine
- Pure Linux bridge backend
- Maximum performance (>20 Gbps)
- eBPF filters available
- Latency: <10μs

### Scenario 2: Multi-Compute, Hybrid

```mermaid
graph TB
    subgraph "Compute Node 1"
        N1[Node 1]
        N2[Node 2]
        LB1[Linux Bridge]
        UB1[Ubridge UDP]

        N1 --> LB1
        N2 --> LB1
        LB1 --> UB1
    end

    subgraph "Compute Node 2"
        N3[Node 3]
        N4[Node 4]
        LB2[Linux Bridge]
        UB2[Ubridge UDP]

        N3 --> LB2
        N4 --> LB2
        LB2 --> UB2
    end

    UB1 <-->|UDP Tunnel| UB2

    style LB1 fill:#90EE90
    style LB2 fill:#90EE90
    style UB1 fill:#FFD700
    style UB2 fill:#FFD700
```

**Characteristics**:
- Nodes distributed across machines
- Local: Linux bridge (fast)
- Remote: Ubridge UDP (scalable)
- Optimal performance mix

### Scenario 3: Hybrid GNS3 + Containerlab

```mermaid
graph TB
    subgraph "GNS3 Domain"
        GN1[GNS3 Node 1]
        GN2[GNS3 Node 2]
        GLB[GNS3 Bridge]

        GN1 --> GLB
        GN2 --> GLB
    end

    subgraph "Containerlab Domain"
        CN1[Containerlab Node 1]
        CN2[Containerlab Node 2]
        CLB[Containerlab Bridge]

        CN1 --> CLB
        CN2 --> CLB
    end

    GLB <-->|veth sync| CLB

    style GLB fill:#87CEEB
    style CLB fill:#FFA07A
```

**Characteristics**:
- Best of both ecosystems
- Seamless interoperability
- Unified management
- Expanded device catalog

---

## Performance Expectations (Design Targets)

All figures below are **design targets**, not empirical measurements. They are estimated based on the architectural differences between kernel-space bridging (proposed) and userspace bridging via ubridge (current). Actual results depend on hardware, kernel version, NIC offloading, node count, and traffic patterns. A Phase 1 benchmark suite should validate these assumptions before committing architectural decisions.

### Throughput Comparison

| Scenario | Current (Ubridge) | Proposed (Linux Bridge) | Improvement |
|----------|------------------|----------------------|-------------|
| Local (2 nodes) | ~5 Gbps | >20 Gbps | 4x |
| Local (8 nodes) | ~3 Gbps | >20 Gbps | 6.7x |
| Remote (same rack) | ~2 Gbps | >2 Gbps | Baseline |
| Remote (cross DC) | ~1.5 Gbps | >1.5 Gbps | Baseline |

### Latency Comparison

| Connection Type | Current (Ubridge) | Proposed (Linux Bridge) | Improvement |
|----------------|------------------|----------------------|-------------|
| Local (same compute) | ~50μs | <10μs | 5x faster |
| Remote (same rack) | ~100μs | ~50μs | 2x faster |
| Remote (cross datacenter) | ~500μs | ~450μs | Marginal |

### Resource Usage

| Metric | Current | Proposed | Improvement |
|--------|---------|----------|-------------|
| CPU (10 nodes, all local) | 20% | 5% | 4x better |
| Memory per node | 50MB | 10MB | 5x better |
| Packet copy overhead | 4 copies | 1 copy | 4x reduction |

---

## Risk Assessment & Mitigation

### Risk Matrix

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|-------------------|
| **Node type adaptation complexity** | High | High | Prototype with Docker first; add shim for userspace-only nodes (VPCS/IOU/Dynamips) |
| **Network namespace management** | High | High (Docker nodes common) | Careful `ip netns` integration; restart-detection hooks |
| **eBPF security vulnerabilities** | High | Low | Code review, sandboxing, kernel verifier, privilege proxy |
| **eBPF build pipeline + distribution** | Medium | High | Ship pre-compiled .o files; CO-RE BTF support; graceful fallback |
| **Controller link refactoring scope** | High | Medium | Ship parallel Link subclass (not rewrite); feature-gated |
| **Containerlab API compatibility** | Medium | Medium | Version locking, adapter layer; containerlab may break CLI flags |
| **Containerlab lifecycle management** | Medium | High | Defensive process mgmt; health-check polling; state reconciliation |
| **Performance claims unvalidated** | Medium | High | Phase 1 benchmark gate before Phase 2 investment |
| **User experience disruption** | Medium | Low | Graduated rollout (per-project toggle); ubridge fallback retained |
| **Cross-platform compatibility** | Medium | High | Linux bridge/eBPF/containerlab Linux-only; macOS/Windows retain ubridge |
| **Deployment complexity** | Medium | Medium | Automated tooling, documentation, config validation |

### Migration Strategy

**Phased Approach**:
1. **Phase 1**: Foundation & Abstraction Layer — Node adaptation, controller refactoring, config schema, POC benchmark
2. **Phase 2**: Linux Bridge Implementation — Bridge Manager, Veth Manager, Docker + QEMU support, namespace handling
3. **Phase 3**: eBPF Integration — Build pipeline, loader, filter parity, monitor integration
4. **Phase 4**: Containerlab Integration — Lifecycle management, topology conversion, bridge sync
5. **Phase 5**: Testing & Production — Benchmark gate passes; phased rollout

**Rollback Capabilities**:
- Configuration-based backend selection: `[Server] use_linux_bridge = false`
- Runtime fallback to ubridge: if Linux bridge operations fail, per-project fallback
- Per-project backend choice (stored in .gns3 topology file)
- Automatic detection of suitable backend (Linux-only features auto-disabled on other platforms)

**Migration Path for Existing Projects**:
- Projects saved before Phase 2 load with `ubridge_fallback = true` by default
- User can opt in per-project: project settings → "Use Linux Bridge"
- Running nodes are NOT migrated mid-session; apply on next project open
- GNS3 topology format (.gns3) gains optional `"linux_bridge": true` flag in the project object

---

## Success Metrics

### Performance KPIs

| KPI | Target | Measurement Method |
|-----|--------|-------------------|
| Local throughput | >20 Gbps | iperf3 |
| Remote throughput | >2 Gbps | iperf3 |
| Local latency | <10μs | packet timestamping |
| CPU efficiency | <5% @ 10 nodes | system monitoring |
| Memory efficiency | <100MB @ 10 nodes | process metrics |

### Functional KPIs

| KPI | Target | Validation |
|-----|--------|-----------|
| Backend compatibility | 100% | All node types work |
| Topology conversion | 100% | Import/export success |
| eBPF filter coverage | >90% | Common filters implemented |
| Containerlab node support | >80% | Major vendors supported |

### Quality KPIs

| KPI | Target | Measurement |
|-----|--------|-------------|
| Test coverage | >85% | Code coverage tools |
| Security audit | Pass | External review |
| Performance regression | None | Benchmark suite |
| User acceptance | >90% | Survey feedback |

---

## Configuration Examples

### Basic Configuration

```ini
[Server]
# Enable Linux bridge backend
use_linux_bridge = true

# Enable eBPF filters
enable_ebpf = true

[LinuxBridge]
# Bridge naming pattern
bridge_prefix = gns3

# Enable local bridge for intra-node traffic
enable_local_bridge = true
```

### Advanced Configuration

```ini
[Server]
use_linux_bridge = true
ubridge_fallback = true

[LinuxBridge]
bridge_prefix = gns3
veth_prefix = veth
enable_vlan_filtering = false
mtu = 9000

[eBPF]
enabled = true
program_directory = /var/lib/gns3/ebpf
enable_custom_bpf = true
security_sandbox = true

[Containerlab]
enabled = true
api_endpoint = http://localhost:5000
auto_sync_bridges = true
supported_kinds = nokia_srlinux,arista_ceos,cisco_xrd

[Hybrid]
auto_detect_local = true
prefer_linux_bridge = true
udp_buffer_size = 1048576
```

---

## Future Enhancements

### Post-Integration Features

**Advanced eBPF Capabilities**:
- Connection tracking
- Traffic analytics and monitoring
- Custom metrics collection
- Advanced QoS

**Multi-Cloud Support**:
- AWS/Azure/GCP integration
- Distributed topology deployment
- Cloud-native networking

**Windows/macOS Support**:
- WSL2 integration (Windows)
- Linux VM approach (macOS)
- Feature parity detection

**AI Integration**:
- Intelligent topology optimization
- Automated failure detection
- Performance tuning recommendations

---

## Key Technical Considerations and Best Practices

### 1. eBPF Filter Hot-Loading Design

**Challenge**: Users need to adjust link quality parameters (latency, packet loss, bandwidth) in real-time through the GNS3 GUI without performance degradation.

**Solution**: Implement eBPF Maps-based dynamic control instead of frequent program reloads.

```mermaid
sequenceDiagram
    participant GUI as GNS3 GUI
    participant API as Backend API
    participant Map as eBPF Map
    participant XDP as XDP Program

    GUI->>API: Adjust latency slider (50ms → 100ms)
    API->>Map: Update map value (instant)
    Note over Map: No program reload
    Map->>XDP: New value applied next packet
    XDP->>XDP: Apply 100ms delay

    Note over GUI,XDP: <1ms response time
```

**Architecture Benefits**:

| Approach | Reload Time | CPU Impact | GUI Responsiveness |
|----------|-------------|------------|-------------------|
| **Program Reload** | 10-50ms | High | Laggy |
| **Map Update** | <1ms | Negligible | Instant |

**Implementation Strategy**:
```c
// eBPF program with configurable parameters
struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct filter_config);
} filter_config_map SEC(".maps");

struct filter_config {
    __u32 latency_ms;
    __u32 packet_loss_rate;
    __u32 bandwidth_limit_kbps;
};

SEC("xdp")
int packet_filter(struct xdp_md *ctx) {
    __u32 key = 0;
    struct filter_config *config = bpf_map_lookup_elem(&filter_config_map, &key);

    if (config && should_apply_filter(config)) {
        // Apply filter using current config values
    }
    return XDP_PASS;
}
```

**Key Advantages**:
- Zero-downtime configuration changes
- No process restarts required
- Sub-millisecond GUI response
- Supports real-time slider adjustments

---

### 2. Linux Bridge MTU Optimization for Hybrid Mode

**Problem**: UDP tunnel encapsulation adds ~50 bytes overhead. Default 1500-byte MTU causes fragmentation when physical network doesn't support jumbo frames.

```mermaid
graph LR
    subgraph "Before MTU Optimization"
        P1[1500 byte packet]
        P2[+50 byte UDP header]
        P3[1550 byte > 1500 MTU]
        P4[❌ Fragmentation]

        P1 --> P2
        P2 --> P3
        P3 --> P4
    end

    subgraph "After MTU Optimization"
        P5[1450 byte packet]
        P6[+50 byte UDP header]
        P7[1500 byte = 1500 MTU]
        P8[✅ No fragmentation]

        P5 --> P6
        P6 --> P7
        P7 --> P8
    end
```

**Recommended MTU Settings**:

| Component | Standard MTU | Hybrid Mode MTU | Reasoning |
|-----------|--------------|-----------------|-----------|
| **Linux Bridge** | 1500 | 1450 | Reserve space for UDP header |
| **veth pairs** | 1500 | 1450 | Match bridge MTU |
| **Ubridge UDP** | N/A | 1450 | Internal tunnel MTU |
| **Physical interface** | 1500 | 1500 | Standard Ethernet |

**Automatic MTU Calculation**:
```python
def calculate_optimal_mtu(
    base_mtu: int = 1500,
    encapsulation_overhead: int = 50,  # UDP + IP headers
    safety_margin: int = 0
) -> int:
    """
    Calculate optimal MTU for hybrid mode.

    Args:
        base_mtu: Physical network MTU
        encapsulation_overhead: UDP tunnel overhead
        safety_margin: Additional safety margin
    """
    return base_mtu - encapsulation_overhead - safety_margin

# Example usage
hybrid_mtu = calculate_optimal_mtu(
    base_mtu=1500,
    encapsulation_overhead=50,
    safety_margin=0
)  # Returns 1450
```

**Performance Impact**:

| Scenario | MTU | Fragmentation | Throughput | CPU Usage |
|----------|-----|---------------|------------|-----------|
| **Default 1500** | 1500 | Yes | ~1.2 Gbps | High (fragmentation) |
| **Optimized 1450** | 1450 | No | ~2.0 Gbps | Low |

**Configuration Example**:
```ini
[Hybrid]
# Automatic MTU calculation
auto_mtu = true
mtu_base = 1500
encapsulation_overhead = 50
safety_margin = 0

# Manual override
# bridge_mtu = 1450
# veth_mtu = 1450
```

---

### 3. Containerlab Bridge Synchronization Strategies

**Challenge**: Efficiently synchronize network state between GNS3 and Containerlab without complex veth management.

#### Option A: Direct veth Pair Connection

```mermaid
graph TB
    subgraph "GNS3 Domain"
        GNS3_Bridge[gns3-bridge]
    end

    subgraph "Containerlab Domain"
        CLAB_Bridge[clab-bridge]
    end

    subgraph "Connection Layer"
        VETH1[veth-gns3]
        VETH2[veth-clab]
    end

    GNS3_Bridge --> VETH1
    CLAB_Bridge --> VETH2
    VETH1 -.-> VETH2

    style VETH1 fill:#FFE4B5
    style VETH2 fill:#FFE4B5
```

**Pros**: Native Linux bridge support
**Cons**: Complex management, scalability issues

#### Option B: Open vSwitch (Recommended)

```mermaid
graph TB
    subgraph "Unified Fabric"
        OVS[(OVS Bridge<br/>gns3-clab-fabric)]
    end

    subgraph "GNS3 Domain"
        GNS3_Nodes[GNS3 Nodes]
        GNS3_Ports[Port 1, 2, 3]
    end

    subgraph "Containerlab Domain"
        CLAB_Nodes[Containerlab Nodes]
        CLAB_Ports[Port 1, 2, 3]
    end

    GNS3_Nodes --> GNS3_Ports
    CLAB_Nodes --> CLAB_Ports

    GNS3_Ports --> OVS
    CLAB_Ports --> OVS

    style OVS fill:#90EE90
```

**OVS Advantages**:

| Feature | Linux Bridge | Open vSwitch |
|---------|--------------|--------------|
| **Management** | Manual veth setup | Centralized configuration |
| **Scalability** | Limited | Excellent |
| **VLAN support** | Basic | Advanced (802.1Q) |
| **Flow monitoring** | Limited | Built-in sFlow/NetFlow |
| **Debugging** | Basic tools | Rich tooling ecosystem |
| **Containerlab integration** | Custom required | Native support |

**Implementation Example**:
```python
class OVSBridgeSyncManager:
    """
    Synchronize GNS3 and Containerlab using Open vSwitch.
    """

    def __init__(self, bridge_name: str = "gns3-clab-fabric"):
        self._bridge_name = bridge_name
        self._ovs_vsctl = "/usr/bin/ovs-vsctl"

    async def create_fabric(self):
        """Create OVS bridge fabric."""
        subprocess.run([
            self._ovs_vsctl,
            "add-br", self._bridge_name
        ], check=True)

        # Enable bridge
        subprocess.run([
            "ip", "link", "set", self._bridge_name, "up"
        ], check=True)

    async def attach_gns3_node(self, veth_interface: str):
        """Attach GNS3 node to fabric."""
        subprocess.run([
            self._ovs_vsctl,
            "add-port", self._bridge_name, veth_interface
        ], check=True)

    async def attach_containerlab_node(self, veth_interface: str):
        """Attach Containerlab node to fabric."""
        subprocess.run([
            self._ovs_vsctl,
            "add-port", self._bridge_name, veth_interface
        ], check=True)

    async def get_flow_stats(self) -> dict:
        """Get traffic statistics from OVS."""
        result = subprocess.run([
            "ovs-ofctl",
            "dump-ports", self._bridge_name
        ], capture_output=True, text=True)

        # Parse flow statistics
        return self._parse_flow_stats(result.stdout)
```

**Configuration**:
```ini
[Containerlab]
# Use OVS for bridge synchronization
bridge_backend = ovs  # ovs | linux_bridge
ovs_bridge_name = gns3-clab-fabric

# OVS-specific settings
enable_flow_monitoring = true
enable_vlan_tagging = false
```

---

### 4. eBPF Security and Isolation

**Security Consideration**: eBPF requires `CAP_BPF` or `CAP_SYS_ADMIN` capabilities, which pose security risks in multi-tenant environments.

#### Privileged Proxy Architecture

```mermaid
graph TB
    subgraph "Unprivileged Zone"
        GNS3[GNS3 Server<br/>Low Privileges]
    end

    subgraph "Privileged Zone"
        PROXY[eBPF Privilege Proxy<br/>CAP_BPF only]
        VERIFIER[Kernel Verifier]
    end

    subgraph "Kernel Space"
        XDP[eBPF Programs]
    end

    GNS3 -->|Unix Socket| PROXY
    PROXY -->|Load & Verify| VERIFIER
    VERIFIER -->|Approved| XDP

    style PROXY fill:#FFB6C1
    style VERIFIER fill:#90EE90
```

**Security Benefits**:

| Approach | Attack Surface | Privilege Scope | Isolation |
|----------|----------------|-----------------|-----------|
| **Direct eBPF** | Large | Full CAP_SYS_ADMIN | None |
| **Privileged Proxy** | Minimal | CAP_BPF only | Process-based |

**Implementation Strategy**:

```python
class EbpfPrivilegeProxy:
    """
    Privileged proxy for eBPF operations.
    Runs with minimal capabilities (CAP_BPF only).
    """

    REQUIRED_CAPABILITIES = ["CAP_BPF", "CAP_PERFMON"]

    def __init__(self, socket_path: str = "/var/run/gns3-ebpf.sock"):
        self._socket_path = socket_path
        self._process = None

    async def start(self):
        """Start the privileged proxy process."""

        # Drop all capabilities except required ones
        capabilities = ",".join(self.REQUIRED_CAPABILITIES)

        self._process = await asyncio.create_subprocess_exec(
            "gns3-ebpf-proxy",
            "--socket", self._socket_path,
            "--capabilities", capabilities,
            # Security options
            "--no-new-privileges",
            "--seccomp",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

    async def load_ebpf_program(
        self,
        program_bytes: bytes,
        program_type: str
    ) -> bool:
        """
        Request eBPF program loading through proxy.

        Args:
            program_bytes: Compiled eBPF program
            program_type: XDP or TC

        Returns:
            bool: Success status
        """

        request = {
            "action": "load",
            "program": base64.b64encode(program_bytes).decode(),
            "type": program_type
        }

        # Send request through Unix socket
        async with aiohttp.UnixConnector(path=self._socket_path) as conn:
            async with conn.post("http://localhost/load", json=request) as resp:
                return resp.status == 200
```

**Security Features**:

1. **Capability Dropping**: Only retain `CAP_BPF` and `CAP_PERFMON`
2. **Seccomp Filtering**: Restrict system calls
3. **Namespace Isolation**: Run in separate network namespace
4. **No New Privs**: Prevent privilege escalation
5. **Resource Limits**: Enforce memory and CPU limits

**Configuration**:
```ini
[eBPF]
# Security settings
enable_privilege_proxy = true
proxy_socket_path = /var/run/gns3-ebpf.sock
proxy_capabilities = CAP_BPF,CAP_PERFMON

# Sandbox settings
enable_seccomp = true
enable_namespace_isolation = true
max_program_size = 4096
max_map_entries = 1024
```

---

### 5. Real-Time Performance Monitoring with eBPF

**Opportunity**: Leverage eBPF for zero-overhead traffic monitoring and visualization.

#### Monitoring Architecture

```mermaid
graph TB
    subgraph "Data Plane"
        PKTS[Packets]
        XDP[eBPF XDP Program]
        STATS_MAP[Statistics Map]
    end

    subgraph "Control Plane"
        READER[Map Reader]
        AGGREGATOR[Data Aggregator]
        GUI[GNS3 GUI Display]
    end

    PKTS --> XDP
    XDP -->|Update counters| STATS_MAP
    STATS_MAP -->|Poll @ 100ms| READER
    READER --> AGGREGATOR
    AGGREGATOR --> GUI

    style STATS_MAP fill:#FFE4B5
    style GUI fill:#90EE90
```

**eBPF Monitoring Program**:

```c
// Statistics tracking structure
struct link_stats {
    __u64 packets_in;
    __u64 bytes_in;
    __u64 packets_out;
    __u64 bytes_out;
    __u64 drops;
    __u64 errors;
    __u64 timestamp_ns;
};

struct {
    __uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, struct link_stats);
} link_stats_map SEC(".maps");

SEC("xdp")
int monitor_packet(struct xdp_md *ctx) {
    __u32 key = 0;
    struct link_stats *stats = bpf_map_lookup_elem(&link_stats_map, &key);

    if (stats) {
        __u64 now = bpf_ktime_get_ns();
        __u32 packet_size = ctx->data_end - ctx->data;

        // Update statistics (atomic operations)
        __sync_fetch_and_add(&stats->packets_in, 1);
        __sync_fetch_and_add(&stats->bytes_in, packet_size);
        stats->timestamp_ns = now;
    }

    return XDP_PASS;
}
```

**GNS3 GUI Integration**:

```python
class LinkMonitor:
    """
    Real-time link monitoring using eBPF statistics.
    """

    def __init__(self, link_id: str, ebpf_map_fd: int):
        self._link_id = link_id
        self._map_fd = ebpf_map_fd
        self._update_interval = 0.1  # 100ms
        self._running = False

    async def start_monitoring(self, gui_callback):
        """Start monitoring loop."""
        self._running = True

        while self._running:
            # Read statistics from eBPF map
            stats = await self._read_stats()

            # Calculate metrics
            bps = self._calculate_bps(stats)
            pps = self._calculate_pps(stats)

            # Update GUI
            await gui_callback(
                link_id=self._link_id,
                bandwidth_mbps=bps / 1_000_000,
                packets_per_sec=pps,
                drop_rate=stats.drops / stats.packets_in if stats.packets_in > 0 else 0
            )

            await asyncio.sleep(self._update_interval)

    def _calculate_bps(self, stats: LinkStats) -> float:
        """Calculate bits per second."""
        if stats.timestamp_ns == 0:
            return 0.0

        time_delta_ns = stats.timestamp_ns - self._last_timestamp
        if time_delta_ns <= 0:
            return 0.0

        bytes_delta = stats.bytes_in - self._last_bytes
        return (bytes_delta * 8) / (time_delta_ns / 1_000_000_000)  # bits/sec
```

**GUI Display Examples**:

```mermaid
graph LR
    subgraph "Link Visualization"
        A[Node A]
        B[Node B]

        A -->|1.2 Gbps<br/>150k pps<br/>0.01% drops| B
    end

    style A fill:#87CEEB
    style B fill:#87CEEB
```

**Monitoring Features**:

| Metric | Update Rate | Accuracy | Overhead |
|--------|-------------|----------|----------|
| **Bandwidth** | 100ms | ±0.1% | <0.1% CPU |
| **Packet rate** | 100ms | ±0.1% | <0.1% CPU |
| **Drop rate** | 100ms | Exact | <0.1% CPU |
| **Latency** | 1s | ±5μs | <0.5% CPU |

**Comparison with Traditional Monitoring**:

| Approach | CPU Overhead | Accuracy | Real-time |
|----------|-------------|----------|-----------|
| **pcap/tcpdump** | 5-10% | High | No |
| **iptables counters** | 1-2% | Medium | No |
| **eBPF maps** | <0.5% | High | Yes |

**Configuration**:
```ini
[Monitoring]
# Enable real-time monitoring
enable_ebpf_monitoring = true
update_interval_ms = 100

# Metrics to collect
collect_bandwidth = true
collect_packet_rate = true
collect_drop_rate = true
collect_latency = false  # Higher overhead

# GUI display
show_realtime_stats = true
stats_display_format = bandwidth_and_pps  # bandwidth_only | bandwidth_and_pps | detailed
```

---

### 6. Node Type Adaptation Strategy

**Problem**: Each GNS3 node type connects to the network differently (Docker via TAP, QEMU via UDP socket, VPCS via direct UDP, etc.). A Linux bridge backend cannot use a one-size-fits-all adapter.

```mermaid
graph TB
    subgraph "Current: All via Ubridge"
        D[Docker] -->|TAP| UB1[ubridge bridge]
        Q[QEMU] -->|UDP NIO| UB1
        V[VPCS] -->|UDP NIO| UB1
        I[IOU] -->|UDP NIO| UB1
        UB1 -->|UDP Tunnel| Remote
    end

    subgraph "Proposed: Node-Type Adapters"
        D2[Docker] -->|TAP| TAP1[TAP → veth adapter]
        Q2[QEMU] -->|tap/nic| TAP2[TAP → veth adapter]
        V2[VPCS] -->|UDP| SHIM[Local UDP ⇄ veth shim]
        I2[IOU] -->|UDP| SHIM
        TAP1 --> LB[Linux Bridge]
        TAP2 --> LB
        SHIM --> LB
        LB -->|veth| UB2[ubridge UDP]
        UB2 -->|UDP Tunnel| Remote
    end
```

**Adapter Matrix**:

| Node Type | Connector | Direction | Notes |
|-----------|-----------|-----------|-------|
| **Docker** | TAP to veth | Container ↔ Host bridge | Native TAP already exists inside container; needs host-side veth with namespace crossing |
| **QEMU** | `-netdev tap` | QEMU process ↔ Host bridge | Replace `-netdev socket` with `-netdev tap`; requires privileged or pre-configured tap |
| **VPCS** | UDP local shim | VPCS UDP port ↔ veth on bridge | New small helper process: `gns3-bridge-shim` listens on localhost UDP, forwards to veth |
| **IOU** | UDP local shim | Same as VPCS | Share the same shim process design |
| **Dynamips** | UDP local shim | Same as VPCS | Share the same shim process design |
| **Cloud (host iface)** | Direct bridge attach | Host iface ↔ Linux bridge | Use `ip link set ethX master brY` instead of ubridge raw socket |
| **Ethernet Switch** | Native Linux bridge | Already a bridge | Map to kernel bridge directly |

**Implementation Priority**:

```
Phase 1 POC: Docker only (simplest adaptation path)
Phase 2a:    Docker + Cloud + Ethernet Switch
Phase 2b:    QEMU (tap adapter)
Phase 2c:    VPCS / IOU / Dynamips (UDP shim — highest risk)
```

---

## Technical Requirements

### Dependencies

```
# Python packages
pyroute2>=0.7.0           # Netlink (bridge, veth, addr management)
pyyaml>=6.0               # YAML parser (for .clab.yml)
aiohttp>=3.8.0            # HTTP client (containerlab API)

# Build dependencies (not runtime)
clang>=12.0               # eBPF C → BPF bytecode compilation
llvm>=12.0                # BPF backend (target bpf)
libbpf>=1.0.0             # eBPF CO-RE library (or shipped as .so)
kernel-headers            # For BTF/CO-RE generation

# System requirements
- Linux kernel >= 5.8     # eBPF support (XDP, TC, BPF_MAP_TYPE_ARRAY)
- CAP_NET_ADMIN           # Bridge/veth creation, network management
- CAP_BPF + CAP_PERFMON   # eBPF program loading (via privilege proxy)
- iproute2                # `ip link`, `ip netns`, `bridge` commands
- containerlab            # External binary for containerlab integration

# Optional system packages
- openvswitch-switch      # OVS bridge sync (Phase 4, advanced option)
- bridge-utils            # Legacy `brctl` (prefer `ip link` / `bridge` from iproute2)
```

### System Capabilities

- Root or CAP_NET_ADMIN for bridge creation
- eBPF JIT compiler enabled
- Sufficient file descriptors for veth pairs
- Network namespace support

---

**Version**: 1.0
**Status**: 🎯 Proposal (reviewed and corrected based on codebase audit)
**Last Updated**: May 19, 2026
