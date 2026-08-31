<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This document is a roadmap/planning document. The described features have not been implemented yet.

# AIOps Fault Injection Testing Pipeline — Roadmap

## Overview

Build a realistic testing pipeline that duplicates the company's production network architecture into GNS3, then systematically injects network faults using the AI Copilot's fault injection capabilities to validate and train the AIOps module before production deployment.

```
┌─────────────────────────────────────────────────────────────────┐
│                      AIOps Testing Pipeline                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │  Network      │    │  Fault       │    │  AIOps           │   │
│  │  Duplication  │───▶│  Injection   │───▶│  Validation      │   │
│  │  (Phase 1)    │    │  (Phase 2)   │    │  (Phase 3)       │   │
│  └──────────────┘    └──────────────┘    └──────────────────┘   │
│         │                   │                      │            │
│         ▼                   ▼                      ▼            │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │ GNS3 Network  │    │ Fault        │    │ Results &        │   │
│  │ Replica       │    │ Scenarios    │    │ Reporting        │   │
│  └──────────────┘    └──────────────┘    └──────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Core Concept

1. **Duplicate** the company's production network architecture into a GNS3 simulation environment
2. **Select** a set of fault types to test (OSPF, BGP, VxLAN, STP, packet filter, etc.)
3. **Inject** faults automatically using the AI Copilot's fault injection capabilities
4. **Validate** whether the AIOps module correctly identifies and reports each fault
5. **Loop** through all selected fault scenarios, building a comprehensive test matrix
6. **Train** the AIOps module on results to improve accuracy before production deployment

## Phase 1: Network Architecture Duplication

### Goal

Create a high-fidelity replica of the company production network in GNS3.

### Key Tasks

- [ ] **Topology Mapping**: Document production network topology (devices, links, protocols)
- [ ] **Device Selection**: Map production devices to GNS3-compatible images (Cisco IOSv, XRv, Juniper vSRX, etc.)
- [ ] **Configuration Extraction**: Export sanitized production configs (remove passwords, public IPs, sensitive data)
- [ ] **GNS3 Deployment**: Build the network in GNS3 with accurate device placement and links
- [ ] **Config Replication**: Apply adapted configurations to GNS3 devices
- [ ] **Connectivity Validation**: Verify OSPF/BGP adjacencies, VLANs, VRFs, and end-to-end reachability
- [ ] **Baseline Capture**: Record normal operation metrics (CPU, memory, interface counters, routing tables)

### Considerations

- Sanitize all production configurations before importing into GNS3
- Use environment-specific IP addressing where necessary (loopbacks, management)
- Document all deviations from production for traceability

## Phase 2: Fault Injection Pipeline

### Goal

Systematically inject network faults and validate AIOps detection using the existing AI Copilot fault injection infrastructure.

### Components

```
┌──────────────────────────────────────────────────────────────────┐
│                     Fault Injection Pipeline                      │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐  │
│  │ Scenario │   │ Inject   │   │ AIOps    │   │ Record       │  │
│  │ Selector │──▶│ Fault    │──▶│ Validate │──▶│ & Report     │  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────────┘  │
│       │              │              │               │           │
│       │              │              │               │           │
│       └──────────────┴──────────────┴───────────────┘           │
│                           │                                      │
│                           ▼                                      │
│                    Loop until all scenarios tested                │
└──────────────────────────────────────────────────────────────────┘
```

### 2.1 Scenario Selector

- Read fault scenarios from the GNS3-Skills repository
- Support filtering by:
  - Protocol (OSPF, BGP, VxLAN, STP, VLAN, etc.)
  - Severity (critical, high, medium, low)
  - Difficulty (beginner, intermediate, advanced)
- Track which scenarios have been tested
- Randomize selection order to avoid bias
- Exclude previously tested scenarios

### 2.2 Fault Injection

- Use existing `manage_gns3_packet_filter` tool for network-level faults
- Use existing `execute_multiple_device_config_commands` for configuration faults
- Use existing `InjectionSkillsTool` to query and select appropriate faults
- Support combined faults (multiple simultaneous issues)
- Auto-recovery between scenarios (restore baseline state)

### 2.3 AIOps Validation

- Feed network state (after fault injection) to the AIOps module
- Record AIOps diagnosis output
- Compare AIOps results against expected fault definition:
  - **Correct identification**: AIOps names the exact fault
  - **Partial identification**: AIOps identifies related symptoms but not root cause
  - **Missed**: AIOps fails to detect any issue
  - **False positive**: AIOps reports a fault that doesn't exist

### 2.4 Test Execution Flow

```
1. Reset network to clean baseline state
2. Select next untested fault scenario
3. Inject the fault into the GNS3 network
4. Wait for convergence (configurable delay)
5. Query AIOps module for diagnosis
6. Compare AIOps output with expected fault definition
7. Record result (pass/fail/partial)
8. Restore network to baseline
9. Repeat from step 2 until all scenarios completed
```

## Phase 3: Traffic Injection (Enhanced Realism)

### Goal

Add realistic network traffic to the GNS3 simulation so that AIOps has real telemetry data to analyze, rather than a static network.

### Approaches

#### 3.1 Traffic Generators in GNS3

- Deploy traffic generator appliances in GNS3 (e.g., TRex, Ostinato, Scapy on Linux nodes)
- Generate realistic traffic patterns:
  - VoIP/RTP streams
  - HTTP/HTTPS web traffic
  - Database replication
  - Routing protocol updates (OSPF hellos, BGP keepalives)
  - ICMP monitoring traffic

#### 3.2 tcpreplay with Captured Traffic

- Capture real production traffic (sanitized)
- Use `tcpreplay` to replay traffic through the GNS3 network
- More realistic than synthetic traffic generators

#### 3.3 Integration with Network Monitoring

- Feed simulated device telemetry (SNMP, syslog, NetFlow) to the AIOps module
- Enable AIOps to analyze real-time telemetry during fault conditions
- Validate that AIOps can distinguish between traffic anomalies and actual faults

## Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Fault detection rate | >95% | AIOps correctly identifies injected faults |
| False positive rate | <5% | AIOps reports fault when none exists |
| Time to detection | <30s | Duration from injection to AIOps alert |
| Coverage | >80% of defined scenarios | Percentage of scenarios tested |
| Accuracy improvement | Measurable per cycle | Compare pass rates across test cycles |

## Technical Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                     Test Orchestrator                               │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Test Runner (Python)                                        │   │
│  │  - Scenario selection & scheduling                            │   │
│  │  - Fault injection coordination                               │   │
│  │  - AIOps query & result collection                            │   │
│  │  - Report generation                                          │   │
│  └──────────┬────────────────────────────────────────────┬───────┘   │
│             │                                            │           │
│             ▼                                            ▼           │
│  ┌────────────────────┐                    ┌────────────────────┐   │
│  │  GNS3 Controller    │                    │  AIOps Module      │   │
│  │  (gns3-server)      │                    │                    │   │
│  │  - Network mgmt     │                    │  - Fault diagnosis │   │
│  │  - Fault injection  │                    │  - Alert detection │   │
│  │  - State queries    │                    │  - Root cause      │   │
│  └────────────────────┘                    └────────────────────┘   │
│             │                                                        │
│             ▼                                                        │
│  ┌────────────────────┐                                              │
│  │  GNS3 Network      │                                              │
│  │  Replica           │                                              │
│  │  - Devices         │                                              │
│  │  - Traffic         │                                              │
│  │  - Telemetry       │                                              │
│  └────────────────────┘                                              │
└────────────────────────────────────────────────────────────────────┘
```

## Reporting

Each test cycle produces:

- **Summary report**: Pass/fail rates, coverage, trends
- **Detailed per-scenario report**: Injection details, AIOps response, comparison
- **Regression tracker**: Which scenarios regressed since last cycle
- **Accuracy trend**: Improvement or degradation over time

### Example Report Entry

```yaml
test_cycle: 7
date: "2026-06-01"
scenarios_planned: 20
scenarios_completed: 18
failed_injections: 1
skipped: 1
results:
  - scenario: ospf_hello_dead_mismatch
    protocol: ospf
    severity: major
    injection_method: device_config
    target_device: R1
    aiops_detection: true
    aiops_diagnosis: "OSPF Hello/Dead interval mismatch between R1 and R2"
    detection_latency_ms: 12000
    match: exact
  - scenario: packet_loss_heavy
    protocol: performance
    severity: high
    injection_method: packet_filter
    target_link: "R1 ↔ R2 (ethernet)"
    aiops_detection: true
    aiops_diagnosis: "High packet loss detected on link R1-R2"
    detection_latency_ms: 45000
    match: partial
```

## Dependencies

- [ ] GNS3 network replica ready and validated
- [ ] AI Copilot fault injection tools operational
- [ ] AIOps module query interface available
- [ ] Traffic generation tools deployed (for Phase 3)
- [ ] Test orchestrator framework (to be built)
- [ ] Result database and reporting system

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| P1: Network Duplication | 2-4 weeks | GNS3 replica of production network |
| P2: Fault Injection Pipeline | 2-3 weeks | Automated test runner + first results |
| P3: Traffic Injection | 2-4 weeks | Realistic traffic simulation integrated |

## Status

- [ ] P1: Network architecture duplication
  - [ ] Topology mapping documented
  - [ ] Device configurations sanitized and adapted
  - [ ] GNS3 replica deployed
  - [ ] Baseline connectivity verified
- [ ] P2: Fault injection pipeline
  - [ ] Scenario selection framework
  - [ ] Automated fault injection
  - [ ] AIOps validation interface
  - [ ] Report generation
  - [ ] Loop/retry mechanism
- [ ] P3: Traffic injection
  - [ ] Traffic generator deployment
  - [ ] Traffic pattern library
  - [ ] AIOps telemetry integration

