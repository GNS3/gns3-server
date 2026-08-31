<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This document is a roadmap/planning document. The described features have not been implemented yet.


# Injection Fault Tracking — Roadmap

## Problem

When using the AI Copilot in troubleshooting injection mode across multiple chat sessions within the same project, there is no mechanism to prevent the same fault from being injected repeatedly. Each new session starts with a clean slate, unaware of what faults have already been used. This leads to:

- Duplicate injection scenarios across different sessions
- No visibility for instructors into which faults have been used
- No record of which devices were affected or whether faults were resolved

## Proposed Solution

Track injected faults per chat session and feed the history into the LLM's system prompt as context, so the model actively avoids repeating scenarios.

### 1. Storage

The existing `chat_sessions` table has `metadata` and `stats` JSON columns. After each fault injection, the agent records:

```json
// stored in chat_session.metadata
{
    "injected_fault": {
        "fault_type": "injection_ospf",
        "issue_key": "ospf_hello_dead_mismatch",
        "issue_name": "OSPF Hello/Dead Interval Mismatch",
        "device": "R1",
        "severity": "major",
        "injected_at": "2026-05-11T23:00:00Z",
        "resolved": false
    }
}
```

### 2. Context Injection

When starting a new troubleshooting session, query all previous sessions for the project, filter by `copilot_mode = "troubleshooting_injection"`, extract `injected_fault` data, and inject a summary into the system prompt via a placeholder (similar to the existing `{{topology_info}}` mechanism):

```
Previously injected faults in this project:
  1. OSPF Hello/Dead Interval Mismatch on R1 (2026-05-11) — resolved
  2. BGP Route Reflector misconfiguration on R3 (2026-05-10) — resolved

Select a fault that has NOT been used before.
```

### 3. Prompt Update

The `troubleshooting_injection.md` prompt in the GNS3-Skills repository gains an `{{injection_history}}` placeholder, and the agent is instructed to choose a fault not in the history list.

## Status

- [ ] GNS3-Skills: add `{{injection_history}}` placeholder to `troubleshooting_injection.md`
- [ ] gns3-server: implement injection fault recording in agent chat session flow
- [ ] gns3-server: implement injection history query across sessions per project
- [ ] gns3-server: inject history into system prompt via `context_manager.py`
- [ ] gns3-server: add `exclude` parameter to `InjectionSkillsTool` for filtering used faults
