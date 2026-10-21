---
name: documentation
description: Use this skill when creating or updating technical documentation under docs/ directory for GNS3 server
version: 3.1.0
---

# GNS3 Server Technical Documentation Standard

## Core Principle

Documentation answers: **What is this, how does it work at a high level.**

Code details are left to the codebase — readers can use AI to find implementation specifics.

---

## Document Structure

```markdown
# Feature Name

## Overview
[What it does, in 2-3 sentences]

## Architecture
[Mermaid diagram: components and their relationships]

## Business Process
[Mermaid sequence/flowchart: key flows]

## API Endpoints
[Table: Method | Path | Description | Privilege]

## Notes
[Known limitations, performance data, security — only when relevant]
```

---

## What to Include

- Mermaid diagrams for architecture and flow (GitHub renders natively) — see Mermaid Diagram Rules below
  - `graph` for component relationships
  - `sequenceDiagram` for request/response flows
  - `flowchart` for data processing steps
- API endpoint tables
- Request/response JSON examples (for interfaces)
- Performance data (only measured numbers, no estimates)

## Mermaid Diagram Rules

Draw only the diagram kinds the story needs — each kind answers exactly one reader question, in reading order:

- **Anatomy — "what exists, and who owns it?"** — `flowchart LR` with the fewest nodes that show ownership: one subgraph per ownership boundary (a process, a namespace, userspace vs kernel), anything shared between owners a bare node inside the enclosing boundary. The steady-state path is bidirectional solid (`<-->`) edges labeled with the carrying technology, never with a direction; each observer/configurator gets one dashed sideband edge per role.
- **Comparison — "how does X differ from Y?"** — the mirror of its counterpart diagram: same scenario, same node ids, same concrete names, one variable changed. Draw one direction with unidirectional `-->` and state in prose that the reverse is the mirror image.
- **Control sequence — "how is it built / torn down?"** — `sequenceDiagram` spanning every layer (API → coordinator → per-node handlers → the managed process): local steps are self-messages, concurrent fan-out is a `par / and / end` block, each message to the bottom layer is one real command in real order, and a closing `Note` names the steady state.
- **Walkthrough — "how does one item traverse it?"** — `flowchart LR` as a linear pipeline: one subgraph per stage, titled with that stage's role in this trace (`X — ingress`), sideband dashed edges (reverse-direction role, observation point) anchored at the stage they belong to.

Whatever the kind:

- **One step per node, one short line per label.** If a label needs `<br/>` lines to explain itself, split the node into smaller steps instead of packing text — needing many words means the flow needs further decomposition.
- **Details belong to prose.** Parentheticals, exceptions, and parameter lists go to the surrounding text or the section that owns the topic; a diagram never duplicates what prose already says.
- **Define jargon before the first diagram.** A Term | Meaning table placed above the diagrams covers the domain terms they use (interface names, kernel mechanisms), so readers don't have to scan forward.
- **Edge style is semantics.** Solid arrows carry the main flow (data plane); dashed `-.->` edges are sideband relationships (taps, control installs). A node with multiple sideband roles gets one dashed edge per role, each labeled with a single function — and edge *direction* matters too: a config edge points from the configurere to its target, an observation edge from the target to the observer.
- **Decision points are diamonds with labeled outcomes**, not text-packed rectangles spelling out every branch inside one node.
- **A comparison diagram changes exactly one variable.** When two diagrams contrast approaches (kernel vs relay, old vs new), everything else — scenario, topology, node names — stays identical between them; a difference that isn't the point belongs in a prose aside, not in the picture.
- **Numbered crossings stay consistent.** When kernel/user or process-boundary copies are the point of a diagram, number the crossing edges (`copy N: user→kernel`) and keep one numbering scheme across every diagram in the document.
- **Concrete names instantiate stated rules.** Every interface/bridge/instance name appearing in a diagram instantiates a deterministic naming rule stated in prose before the first diagram — never invent ad-hoc names.

## What to Skip

- Code snippets — let readers search the codebase
- Verbose prose — use diagrams and tables
- Implementation details — link file paths instead of pasting code
