# GNS3 Linux Bridge + eBPF + Containerlab Integration Roadmap

## Executive Summary

**Objective**: Migrate GNS3 from ubridge-based networking to a hybrid **Linux bridge + eBPF + Containerlab** architecture.

**Key Benefits**:
- ⚡ **Performance**: 5-10x throughput improvement for local connections
- 🔌 **Ecosystem**: Access to containerlab's rich network device catalog
- 🔥 **eBPF Support**: Kernel-space packet processing with near-zero overhead
- 🚀 **CI/CD Ready**: Better automation and cloud-native integration

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

## Performance Expectations

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
| Linux bridge performance issues | High | Low | Early benchmarking, optimization |
| eBPF security vulnerabilities | High | Low | Code review, sandboxing, kernel verifier |
| Containerlab API compatibility | Medium | Medium | Version locking, adapter layer |
| User experience disruption | Medium | Low | Gradual rollout, documentation |
| Cross-platform compatibility | Medium | High | Maintain ubridge fallback |
| Deployment complexity | Medium | Medium | Automated tooling, guides |

### Migration Strategy

**Phased Approach**:
1. **Phase 1**: Foundation & Abstraction Layer
2. **Phase 2**: Linux Bridge Implementation
3. **Phase 3**: eBPF Integration
4. **Phase 4**: Containerlab Integration
5. **Phase 5**: Testing & Production

**Rollback Capabilities**:
- Configuration-based backend selection
- Runtime fallback to ubridge
- Per-project backend choice
- Automatic detection of suitable backend

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

## Technical Requirements

### Dependencies

```
# Python packages
bcc>=0.25.0              # eBPF toolchain
libbpf>=1.0.0            # eBPF library
clang>=12.0.0            # eBPF compiler
llvm>=12.0.0             # eBPF JIT backend
aiohttp>=3.8.0           # HTTP client
pyyaml>=6.0              # YAML parser

# System requirements
- Linux kernel >= 5.8    # eBPF support
- CAP_NET_ADMIN          # Network management
- bridge-utils           # Linux bridge tools
```

### System Capabilities

- Root or CAP_NET_ADMIN for bridge creation
- eBPF JIT compiler enabled
- Sufficient file descriptors for veth pairs
- Network namespace support

---

**Version**: 1.0
**Status**: 🎯 Proposal
**Last Updated**: January 7, 2025
