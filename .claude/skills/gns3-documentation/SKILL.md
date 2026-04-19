---
name: documentation
description: Use this skill when creating or updating technical documentation under docs/ directory for GNS3 server
version: 3.0.0
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

- Mermaid diagrams for architecture and flow (GitHub renders natively)
  - `graph` for component relationships
  - `sequenceDiagram` for request/response flows
  - `flowchart` for data processing steps
- API endpoint tables
- Request/response JSON examples (for interfaces)
- Performance data (only measured numbers, no estimates)

## What to Skip

- Code snippets — let readers search the codebase
- Verbose prose — use diagrams and tables
- Implementation details — link file paths instead of pasting code
