---
name: docker-iptables-forward-bridge
description: Docker iptables FORWARD DROP blocks kernel bridge forwarding, fix and symptoms
metadata:
  type: reference
---

Docker sets the iptables `FORWARD` chain default policy to `DROP` when the
Docker daemon starts. This blocks **all** forwarded traffic through Linux
kernel bridges on the host — including `gns3br{N}` bridges created by the
builtin Ethernet Switch (ubridge `brctl`).

## Symptoms

- Nodes connected to the switch can send frames into the bridge (visible in
  `tcpdump -i gns3br{N}`) but never receive forwarded unicast frames.
- `bridge fdb show` may fail to learn MAC addresses (frames dropped before
  the bridge learning path).
- ARP and multicast/broadcast may appear to work because they flood, but
  unicast replies never reach the destination.
- OSPF Hello / CDP visible on both sides but ICMP echo reply never returns.
- `ubridge bridge get_stats` shows symmetric IN/OUT counts (relay is fine),
  `bridge fdb show` shows learned MACs, `bridge link show` shows `state forwarding`
  on all ports — yet unicast still doesn't work.

## Fix

Run once per host boot, or make persistent via iptables-persistent / firewall config:

```bash
sudo iptables -P FORWARD ACCEPT
```

## Related

- [[ethernet-switch-ubridge-brctl-migration]] — the kernel bridge that hits this
- [[gns3-server-linux-only]] — datapath constraint
- [[gns3-ubridge-permission]] — another host-level prerequisite (CAP_NET_ADMIN)
