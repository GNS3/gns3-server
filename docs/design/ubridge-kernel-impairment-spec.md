<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> Frozen requirements spec for the **uBridge** project. Delivery status:
> **all parts delivered and integrated.** A (netem keyword extensions,
> uBridge `feature/tc-netem-ext`), C + D + E (cBPF match-drop, full-restore
> idempotent `tc reset`, `tc capabilities` — uBridge `feature/tc-bpf-drop`)
> and **B (eBPF stateful classifier — uBridge `feature/tc-precision`
> 59e2b38, including the non-root setcap load fix)** are consumed by
> gns3-server on the branch stack ending at `feat/docker-kernel-ebpf-drops`
> (B: `frequency_drop` → `tc nth_drop`, the new kernel-only `quota` type →
> `tc quota_drop`). The originally shipped netem surface (delay/jitter/
> loss/dup/corrupt) exists in uBridge 1.2.3+ and is verified against
> gns3-server branch `feat/docker-kernel-filters`.
>
> **Deviation found during integration (part A/D):** the delivered
> `tc netem set` uses NLM_F_REPLACE, but the *kernel's* netem change merges
> optional attributes — rate, correlation, reorder, corrupt, gemodel,
> distribution and seed keep their previous value when the new message
> omits them, so "netem set atomically replaces" (D's reconcile
> assumption) does not hold for parameter *removals*. gns3-server works
> around it by sending `tc reset` before every `netem set` (the bpf_drop
> filters are re-added right after in the same flow, so clsact churn is
> invisible). If uBridge later emits explicit zero/absent clears for every
> optional attribute, the server-side reset-before-set can be dropped; the
> two behaviours are compatible either way.
>
> **Deviation found during B integration:** `window_drop`'s implementation
> advances the window start by one length on expiry with no gap, making the
> windows back-to-back — after the first `start_ms` the "outside the window
> packets pass" behaviour described in B.2 is unreachable (inside ≡ always).
> gns3-server therefore does **not** expose window_drop yet; it needs either
> a second length field (outage vs period) or a next-start semantics fix on
> the uBridge side. `flow_drop` is delivered and functional but not yet
> exposed as a GNS3 filter type (its mask/target parameter shape needs a
> UX decision). Additionally, the delivered B.1 program had to fold the
> flow-hash L4 port reads to constant offsets (IHL==20 only) because the
> verifier prohibits variable packet-pointer arithmetic for non-root —
> even with CAP_BPF (Spectre-mitigation gating by uid); documented in
> uBridge's doc/tc.md.

# uBridge kernel impairment: tc netem extensions + eBPF classifiers

## 0. Background & scope

On the kernel datapath (Docker veth pairs enslaved into per-link Linux
bridges) frames never pass through uBridge's userspace relay, so link
impairment must live in the kernel: a **netem qdisc** on each veth host end
(serving delay / jitter / loss / dup / corrupt — *shipped*) plus **tc
classifiers** on the clsact egress hook for everything netem cannot express.

This spec freezes:

| Part | Content | New capability needed |
|---|---|---|
| A | netem keyword extensions: `rate`, `reorder`, loss models, jitter distributions, correlation, `seed`, `limit` | none (netlink only) |
| B | eBPF stateful classifier: `frequency_drop` (nth-packet), byte quota, time window, flow select | **CAP_BPF** |
| C | classic-BPF match-drop: the GNS3 `bpf` filter | none (netlink only) |
| D | lifecycle, composition & ordering contract, `tc reset` semantics fix | — |
| E | error strings, `tc capabilities` probe | — |
| F | test requirements | — |

Non-goals (explicitly out of scope for now): packet mangling (`pedit`,
`csum`), mirroring (`mirred`), HTB hierarchies, RST/connection-kill
injection, ingress-side (XDP) impairment.

All commands operate on **egress of the veth host end** (traffic entering
the container), consistent with the existing netem placement.

---

## A. `tc netem set` keyword extensions *(P6a)*

Extend the shipped grammar — existing keywords and their encoding are
frozen and unchanged:

```
tc netem set <if>
   [delay <ms>] [jitter <ms>] [distribution uniform|normal|pareto|paretonormal] [seed <u32>]
   [loss <pct> [correl <pct>]]
   [loss gemodel <p> [<r> [<1-h>]]]              # mutually exclusive with plain loss
   [dup <pct> [correl <pct>]] [corrupt <pct>]
   [reorder <pct> [correl <pct>] [gap <n>]]      # requires delay
   [rate <bw>]                                    # e.g. 10mbit, 512kbit
   [limit <pkts>]
```

### A.1 Parameter validation

| Keyword | Range / format | Errors |
|---|---|---|
| `rate` | `<bw>` = integer + unit `bit\|kbit\|mbit\|gbit\|bps\|kbps\|mbps` (decimal), max 100gbit | 204 `invalid rate '<v>'` |
| `reorder` | pct 0–100, correl 0–100, gap 1–1000 | 204; 204 `reorder requires delay` if no `delay` present (mirror the kernel's EINVAL instead of passing it through — the server keys on the string) |
| `loss gemodel` | p 0–100, r 0–100, h as `1-h` where h is 0–100 (default r=0, 1-h=0) | 204 |
| `distribution` | one of the four names | 204 `unknown distribution '<v>'` |
| `seed` | u32 decimal | 204 |
| `limit` | 1–1000000 packets (replaces the current fixed 1000 default) | 204 |
| `correl` suffix on loss/dup | 0–100, only directly after its keyword | 204 |

Max token count for the command table rises accordingly (recommend 32).

### A.2 Netlink encoding notes

* Correlation: loss/dup/reorder use their existing nested structs with the
  `correlation` field set (`tc_netem_loss`? no — see `struct tc_netem_qopt`
  + `TCA_NETEM_CORR` carrying `tc_netem_corr` {delay, loss, dup}). Fill the
  loss correlation there; dup likewise.
* gemodel: `TCA_NETEM_LOSS` nested attr, kind `TCA_NETEM_LOSS_GEMODEL`
  (`struct tc_netem_gemodel` {p, r, h}), probabilities in the same % × 2³²
  encoding as `qopt.loss`. When gemodel is set, `qopt.loss` stays 0.
* reorder: `TCA_NETEM_REORDER` (`struct tc_netem_reorder`
  {probability, correlation}).
* rate: prefer `TCA_NETEM_RATE64` (u64 bits/s) and also fill legacy
  `TCA_NETEM_RATE` (`tc_netem_rate`) with the truncated value for older
  kernels; `slot_overhead = 0`.
* distribution: `TCA_NETEM_JITTER64` + `TCA_NETEM_DIST` must carry the
  distribution table (s16 deltas). **Embed the three standard tables**
  (normal / pareto / paretonormal — same values iproute2 ships as
  `*.dist`, generated by netem's `maketable`) as const arrays in uBridge;
  select by name. Without DIST the kernel silently uses uniform jitter.
* seed: `TCA_NETEM_SEED` (u64 allowed) — makes random draws reproducible
  for tests. When omitted keep the current behaviour (kernel picks).

### A.3 Reply contract (unchanged shape)

```
100-netem set on <if>
204-invalid <kw> value '<v>'
204-reorder requires delay
207-Could not set netem on <if>: <strerror>
```

---

## B. eBPF stateful classifier *(frequency_drop + P6b modes)*

**One** SCHED_CLS eBPF program, loaded once per interface, attached to the
clsact egress hook. All modes are configured through one ARRAY map entry —
no program reload on parameter changes.

### B.1 Program

* Source `src/tc_impair.bpf.c` committed for reference; the build commits
  the compiled object (`tc_impair.bpf.o`, freestanding: no CO-RE, no
  BTF-typed ptr, plain `struct __sk_buff` + direct packet access).
  No runtime clang/libbpf dependency.
* Maps:
  * `CFG` — `BPF_MAP_TYPE_ARRAY`, 1 entry:
    ```
    struct cfg {
        __u32 nth;          /* 0 = off, else drop every Nth packet      */
        __u64 quota_bytes;  /* 0 = off                                  */
        __u32 quota_pct;    /* random drop % after quota reached        */
        __u64 win_start_ns; /* recurring window start (monotonic)       */
        __u64 win_len_ns;   /* 0 = off                                  */
        __u32 win_pct;      /* random drop % inside the window          */
        __u32 flow_mask;    /* bitmask: 1=src 2=dst 4=sport 8=dport 16=proto */
        __u32 flow_target;  /* required hash remainder, 0 = off         */
    };
    ```
  * `CNT` — `BPF_MAP_TYPE_ARRAY`, 1 entry: `{__u64 packets; __u64 bytes; __u64 nth_state;}`
    Counters are updated with `__sync_fetch_and_add` on the map/global value
    so the every-Nth count is exact across CPUs (requires kernel ≥ 5.1 —
    acceptable; probe at load, see E).
* Evaluation order is fixed: **nth → quota → window → flow**; the first
  rule that decides a drop returns `TC_ACT_SHOT`, otherwise `TC_ACT_OK`.
  Random percentages use the same 2³²-probability comparison as netem
  (`prandom` seeded via map so tests are reproducible).
* Verifier-friendly: no loops, bounded accesses (check `data + eth+h` before
  reading fields; when flow_mask touches ports, verify L4 header length).

### B.2 Command surface

```
tc nth_drop   <if> <n | off>
tc quota_drop <if> <bytes> <pct> | off
tc window_drop <if> <start_ms> <len_ms> <pct> | off
tc flow_drop  <if> <mask> <target> | off
```

* First enable on an interface: create clsact (EEXIST tolerated), load the
  program, attach one filter at **prio 1** (see D). Subsequent commands only
  update `CFG`/reset the relevant `CNT` fields.
* `off` for every mode → the filter is removed (and the prog fd closed).
  Each `off` resets that mode's counters.
* `flow_drop` mask is the decimal bitmask from B.1 (server composes it);
  hash = Jenkins/equal-fold over the selected header fields modulo
  `flow_target` == remainder 0 → drop. Server documents: per-flow drop only
  (a filter cannot delay; delay stays netem's job).
* Window semantics: `win_start_ns`/`win_len_ns` define a recurring window on
  the monotonic clock — inside the window drop with `win_pct`; outside pass.
  The server computes the first start; the program advances by `len` when
  `now >= start + len` (single writer — the CFG update — so this is safe).

### B.3 Capability requirement

`BPF_PROG_LOAD(SCHED_CLS)` needs **CAP_BPF** (or CAP_SYS_ADMIN) on kernels
≥ 5.8. Installation must therefore set:

```
setcap cap_bpf,cap_net_admin,cap_net_raw=ep <ubridge>
```

On EPERM: reply `210-uBridge lacks CAP_BPF (setcap cap_bpf,cap_net_admin,cap_net_raw=ep) and the kernel requires it for stateful filters`
— the gns3-server side falls back to the relay datapath on this string (E).

---

## C. classic-BPF match drop (the GNS3 `bpf` filter)

No eBPF, no CAP_BPF: `cls_bpf` accepts **classic bytecode** via
`TCA_BPF_BYTECODE` (`sock_fprog`), and the kernel internally migrates it to
eBPF. uBridge already links libpcap.

```
tc bpf_drop add <if> <prio> "<expression>"    # prio: 10..99, server-assigned
tc bpf_drop flush <if>
```

* `add`: `pcap_compile(DLT_EN10MB, snaplen 65535)` the expression; on
  failure reply
  `209-Cannot compile filter '<expr>': <pcap_geterr>` — gns3-server keys on
  this exact prefix (same shape as the relay's error so one regex serves
  both datapaths). Netlink: RTM_NEWTFILTER on clsact egress, protocol
  ETH_P_ALL, `TCA_KIND "bpf"`, `TCA_BPF_BYTECODE`, action nested
  `TCA_BPF_ACT` → `gact` with `action = TC_ACT_SHOT` (pcap match ≠ 0 →
  filter matches → drop; non-match falls through, no action → pass).
* Multiple expressions (GNS3 sends one line per filter): server adds one
  filter per line at successive prios — any match drops (OR).
* `flush`: delete every bpf_drop filter uBridge added on this interface
  (track prios in-process), tolerate ENOENT per filter. Does NOT touch the
  eBPF prio-1 filter or netem.
* Update-by-replace: server always `flush` + re-`add` (mirrors `netem set`).

---

## D. Lifecycle, composition & ordering (frozen contract)

* **clsact coexists with the netem root qdisc** — never replace the root.
* Execution order on egress: classifier filters by ascending prio —
  eBPF impair filter at **prio 1**, `bpf_drop` at **prio 10..99** — then the
  root netem qdisc. Dropped packets therefore never reach netem **nor the
  AF_PACKET tap points** (capture/markers will not observe cls_bpf-dropped
  frames; documented server-side).
* **`tc reset <if>` becomes the full restore** (behaviour change + fix):
  1. remove all bpf_drop filters and the eBPF filter (clsact egress side we
     own), 2. delete clsact, 3. delete the root qdisc. On an untouched
     interface it must now reply **100-OK** (idempotent — currently returns
     207-ENOENT; gns3-server tolerates both, but the new contract is OK).
* All state is kernel state tied to the interface: deleting the veth
  (container stop) clears everything; no ubridge-side bookkeeping survives
  a restart (a re-attached link rebuilds from the NIO, as today).

---

## E. Errors & capability probe

Error strings are contract (gns3-server matches them):

| Reply | Meaning |
|---|---|
| `100-netem set on <if>` / `100-qdisc reset on <if>` | success |
| `203-Bad number of parameters (%d with min/max=%d/%d)` | argc mismatch |
| `204-invalid <kw> value '<v>'` | value validation |
| `204-reorder requires delay` | keyword dependency |
| `207-Could not (set netem\|reset qdisc) on <if>: <strerror>` | netlink/kernel failure |
| `209-Cannot compile filter '<expr>': <err>` | bpf_drop pcap_compile failure |
| `210-uBridge lacks CAP_BPF ...` | stateful filters unavailable |

New introspection command (also serves the gns3-server degradation TODO —
old uBridge without these commands simply stays on the relay datapath):

```
tc capabilities
100-netem=delay,jitter,loss,dup,corrupt,rate,reorder,gemodel,dist,seed,limit;ebpf=1;cbpf=1
```

`ebpf=0` when the load probe fails at startup (kernel < 5.1 or no CAP_BPF);
`cbpf=0` when RTM_NEWTFILTER/cls_bpf is unavailable. gns3-server hides the
corresponding filter types per capability.

---

## F. Test requirements

* **Unit**: per keyword → expected netlink attrs (assert message bytes);
  every 204 table row; `bpf_drop` compile-fail path; capabilities string.
* **Functional** (root, veth pair + netns + nsenter ping):
  delay+reorder observable (mdev), gemodel loss within ±5% of target,
  rate within ±10% (measured byte throughput), nth_drop **exact** pattern
  (ICMP seq survives 1,2,…,N-1, Nth dropped), quota/window/flow with
  crafted senders, `tc reset` idempotent on a clean interface, P5 surface
  regression (delay/jitter/loss/dup/corrupt, REPLACE semantics).
* Determinism: netem `seed` + the CFG-seeded prandom make runs repeatable;
  CI asserts identical drop patterns for identical seeds.

---

## gns3-server alignment (informational — not uBridge scope)

* **Done** (`feat/docker-kernel-netem-ext`): the P6a types map 1:1 onto new
  GNS3 filter entries (rate, reorder, gemodel, duplicate, seed, limit, plus
  the delay `distribution` and loss/dup `correlation` parameters), translated
  in `DockerVM._ubridge_apply_netem`; extension keywords are gated on the
  `tc capabilities` netem token list (old uBridge builds are never probed
  for the original surface).
* **Done** (`feat/docker-kernel-bpf-drop`): `bpf` runs as cBPF match-drop.
* **Done** (`feat/docker-kernel-ebpf-drops`): the eBPF classifier (part B)
  is consumed — `frequency_drop` → `tc nth_drop` (-1 → every 1st), the new
  kernel-only `quota` type → `tc quota_drop`, both keyed on `ebpf=1` from
  the per-process `tc capabilities` probe. `KERNEL_UNSUPPORTED_FILTERS` is
  gone entirely: kernel/relay eligibility is purely topological now.
  Not yet exposed: `window_drop` (implementation deviation above),
  `flow_drop` (parameter-shape UX decision).
* Every veth end owns one qdisc + its filters: per-direction impairment is
  an architectural freebie to expose later (API `direction` field), aligned
  with marker `dir` semantics.
