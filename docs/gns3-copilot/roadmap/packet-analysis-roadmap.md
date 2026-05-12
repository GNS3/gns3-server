<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This document is a roadmap/planning document. The described features have not been implemented yet.


# Protocol-Oriented Packet Analysis — Roadmap

## Problem

The current `PacketCaptureTool` (`analyze_packets`) only accepts a single `packet_number` parameter and runs `tshark -V` on that one frame. This approach:

- Forces the LLM to guess packet numbers without any visibility into the capture
- Returns raw verbose output instead of structured data
- Has no protocol awareness — every protocol looks the same to the tool
- Provides no built-in anomaly detection; the LLM must infer issues from raw output each time
- Downloads the same pcap from the server on every call (no caching)

## Proposed Architecture

Move from number-based to **protocol-oriented** packet analysis. Protocol definitions (fields, display filters, anomaly checks) are stored as YAML files in the GNS3-Skills repository. The tool only needs `link_id` + `protocol` — no complex parameters for the LLM to get wrong.

### Data Flow

```
GNS3-Skills/packet_analysis/<protocol>.yaml
        │
        ▼  loaded at startup / reload
PACKET_ANALYSIS_REGISTRY (in-memory dict)
        │
        ▼
PacketAnalysisTool(link_id, protocol)
        │
        ├── download pcap (with link_id caching)
        ├── tshark -T fields -e <predefined fields>
        ├── run anomaly checks from YAML
        └── return structured JSON + check results
                │
                ▼
        LLM produces natural language explanation
```

### YAML Format

```yaml
name: "OSPF Packet Analysis"
protocol: "ospf"
display_filter: "ospf"
fields:
  - label: "Source IP"
    field: "ip.src"
    description: "Source IPv4 address"
  - label: "OSPF Message Type"
    field: "ospf.msg"
    description: "1=Hello, 2=DBD, 3=LSR, 4=LSU, 5=LSAck"
checks:
  - name: hello_dead_mismatch
    severity: critical
    message: "Hello/Dead Interval mismatch between {src} and {dst}"
    condition: "Same broadcast domain has inconsistent hello/dead intervals"
```

### Planned Protocols

| File | Protocols | Key Checks |
|------|-----------|------------|
| `arp.yaml` | ARP, NDP (ICMPv6 NS/NA) | Duplicate IP, no ARP reply, ARP flooding |
| `icmp.yaml` | ICMPv4, ICMPv6 | Unreachable classification, ping loss, PMTUD issues |
| `ospf.yaml` | OSPFv2, OSPFv3 | Hello/Dead mismatch, Area ID mismatch, Router ID conflict |
| `bgp.yaml` | BGPv4, BGP+ | Hold timer mismatch, Notification analysis, AS_PATH loop |

### Tool Interface

```json
{
    "link_id": "uuid (required)",
    "protocol": "arp | icmp | ospf | bgp (required)",
    "summary_only": "bool (optional, default: false)"
}
```

## Status

- [ ] GNS3-Skills: create `packet_analysis/` directory and YAML definitions
- [ ] gns3-server: add `PACKET_ANALYSIS_REGISTRY` loading from skills repo
- [ ] gns3-server: implement `PacketAnalysisTool` with tshark field extraction
- [ ] gns3-server: implement protocol-specific anomaly checks
- [ ] gns3-server: add pcap caching by `link_id`
- [ ] gns3-server: register tool in teaching assistant and lab automation modes
- [ ] gns3-server: deprecate and remove old `PacketCaptureTool`
