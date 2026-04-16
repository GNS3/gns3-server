<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

# Template-Based System with HITL - Future Roadmap

**Status:** 💡 Proposed
**Target Version:** Next Release
**Last Updated:** 2026-03-20

## Overview

This document outlines the plan for implementing **template-based systems with Human-in-the-Loop (HITL) confirmations** for both **device configuration** and **node creation** in GNS3 AI Copilot.

### Scope & Positioning

**This system focuses on baseline configuration and topology provisioning** - getting from zero to a manageable state. Once devices are connected and have basic IP/routing configuration, modern network management tools can take over for production-grade configuration management.

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Environment Preparation (This System)              │
│ ─────────────────────────────────────────────────────────── │
│ • Create topology (nodes + links)                           │
│ • Baseline IP configuration                                 │
│ • Enable routing protocols (OSPF/BGP)                       │
│ • Management access (SSH/HTTPS/NETCONF)                     │
│ • Basic security (ACLs, passwords)                          │
│ ─────────────────────────────────────────────────────────── │
│ Result: Manageable network ready for production tools       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: Production Configuration (External Tools)          │
│ ─────────────────────────────────────────────────────────── │
│ • Terraform (Infrastructure as Code)                        │
│ • REST API (Modern device management)                       │
│ • NETCONF/YANG (Standardized configuration)                 │
│ • Network Controllers (SDN, APIC, etc.)                     │
│ • Monitoring & Observability                                │
└─────────────────────────────────────────────────────────────┘
```

**Use Cases for This System:**
- Rapid lab provisioning (training, testing, CI/CD)
- Network simulation and research
- Proof-of-concept deployments
- Disaster recovery drills
- Initial topology setup before handoff to automation tools

**Not In Scope (handled by other tools):**
- Fine-grained configuration management
- Compliance and policy enforcement
- Continuous configuration drift management
- Production-grade change management
- Advanced telemetry and monitoring

### Motivation

#### Current Configuration Challenges

The current implementation requires AI to generate complete configuration commands for every device, which:

- **Consumes excessive tokens:** Each device configuration is generated independently (~150 tokens/device × 10 devices = 1500 tokens)
- **Lacks user control:** Configurations are executed immediately without human review
- **No reusability:** Similar configurations must be regenerated from scratch
- **Higher error risk:** Direct execution without preview or confirmation

#### Current Node Creation Challenges

Similarly, creating multiple nodes has significant inefficiencies:

- **Token waste:** Each node creation requires ~50 tokens for tool calls (100 nodes = 5000 tokens)
- **Slow execution:** Nodes are created serially or with limited parallelism
- **No batch operations:** Cannot create groups of related nodes efficiently
- **Manual positioning:** Each node must be positioned individually

### Proposed Solution

Implement a **unified template-based HITL workflow** for both configuration and node creation:

1. **AI generates template** → Human reviews and confirms
2. **AI generates parameters (optional)** → Human reviews and confirms
3. **Local execution** → Results displayed

**Expected Benefits:**
- **98-99% token savings** for large-scale operations (1000+ devices/nodes)
- **90%+ time savings** through parallel execution and batch operations
- **Full user control** with preview and confirmation at every step
- **Template reusability** across similar operations

---

## Architecture Design

### Workflow Diagram

```
User Request: "Configure OSPF on all routers"
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 1: AI Generates Jinja2 Template                         │
│                                                              │
│ Output:                                                      │
│ {                                                            │
│   "template_content": "router ospf {{ pid }}\n...",         │
│   "description": "OSPF basic configuration",                │
│   "params_schema": {                                         │
│     "process_id": "int - OSPF process ID",                  │
│     "networks": "List[Dict] - network list",                │
│     "area": "str - area ID"                                 │
│   }                                                          │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ 🔵 HITL Checkpoint 1: Template Review                       │
│                                                              │
│ User sees:                                                  │
│ - Template content (Jinja2 syntax)                          │
│ - Parameter schema                                          │
│ - Example rendered output                                   │
│                                                              │
│ Options: [✓ Confirm] [✏️ Modify] [❌ Cancel]                 │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: AI Generates Parameters                             │
│                                                              │
│ Output:                                                      │
│ {                                                            │
│   "project_id": "uuid-xxx",                                  │
│   "device_params": [                                         │
│     {                                                        │
│       "device_name": "R1",                                   │
│       "process_id": 1,                                       │
│       "networks": [{"ip": "192.168.1.0", "mask": "0.0.0.255"}], │
│       "area": "0"                                            │
│     },                                                       │
│     ... // More devices                                      │
│   ]                                                          │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ 🔵 HITL Checkpoint 2: Parameter Review                      │
│                                                              │
│ User sees:                                                  │
│ - Parameter preview per device                              │
│ - Rendered configuration commands                           │
│ - Summary of changes                                         │
│                                                              │
│ Options: [✓ Execute] [✏️ Modify] [👁️ Preview] [❌ Cancel]    │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Local Rendering & Execution                         │
│                                                              │
│ Process:                                                     │
│ 1. Render template with parameters (0 tokens)               │
│ 2. Call existing ExecuteMultipleDeviceConfigCommands        │
│ 3. Return execution results                                  │
└─────────────────────────────────────────────────────────────┘
```

### Token Consumption Comparison

#### Scenario: Configure OSPF on 10 Cisco Routers

| Approach | Token Usage | Breakdown |
|----------|-------------|-----------|
| **Current Method** | **~1500 tokens** | 150 tokens/device × 10 devices |
| **Template Method** | **~400 tokens** | Template: 150 + Parameters: 250 |
| **Savings** | **73%** | 1100 tokens saved |

#### Scenario: Configure VLANs on 20 Switches

| Approach | Token Usage | Breakdown |
|----------|-------------|-----------|
| **Current Method** | **~1600 tokens** | 80 tokens/switch × 20 switches |
| **Template Method** | **~400 tokens** | Template: 100 + Parameters: 300 |
| **Savings** | **75%** | 1200 tokens saved |

#### 🔥 Scenario: Large-Scale Topology - 500+ Routers

**This is where the template-based approach truly shines for rapid environment provisioning.**

| Approach | Token Usage | Execution Time | Breakdown |
|----------|-------------|----------------|-----------|
| **Current Method (AI)** | **~75,000 tokens** | ~25 minutes | 150 tokens/device × 500 devices, serial execution |
| **Template + AI** | **~5,000 tokens** | ~10 minutes | Template once + AI generates params, but slow |
| **Template + Rules (Direct)** | **~400 tokens** | **~3 minutes** | Template once + rule engine (0 tokens) + parallel execution |
| **Savings** | **99.5%** | **88%** | **Game-changing for large deployments** |

**Key Insight:** For environments with **hundreds or thousands of nodes**, the direct execution mode (skipping AI) becomes critical for rapid topology preparation.

---

## Core Components

### System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         GNS3 Web UI / CLI                          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP/WebSocket
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       GNS3 Server (FastAPI)                         │
│                                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Chat API    │  │ Template API │  │  SSE Progress Stream      │  │
│  │ (existing)  │  │ (new)        │  │  (new)                    │  │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬───────────────┘  │
│         │                │                     │                   │
│         └────────────────┴─────────────────────┘                   │
│                               │                                     │
└───────────────────────────────┼─────────────────────────────────────┘
                                │
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   AI Copilot Agent (LangGraph)                      │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              HITL Workflow Orchestrator                       │  │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐               │  │
│  │  │ Generate │ →  │ Generate │ →  │ Execute  │               │  │
│  │  │ Template │    │ Params   │    │ Config   │               │  │
│  │  └────┬─────┘    └────┬─────┘    └────┬─────┘               │  │
│  │       │               │               │                      │  │
│  │  🔵 HITL Checkpoints (LangGraph Interrupts)                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    Core Modules                               │  │
│  │  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐    │  │
│  │  │   Template   │  │   Session   │  │   Rule Engine    │    │  │
│  │  │   Renderer   │  │   Manager   │  │  (Direct Mode)   │    │  │
│  │  └──────────────┘  └─────────────┘  └──────────────────┘    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      GNS3 Controller & Compute                      │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────────┐     │
│  │   Node     │  │   Link     │  │    Nornir + Netmiko      │     │
│  │ Management │  │ Management │  │    (Config Execution)    │     │
│  └────────────┘  └────────────┘  └──────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

### HITL State Transition Diagram

```
                    ┌─────────────┐
                    │    IDLE     │
                    └──────┬──────┘
                           │ User Request
                           ↓
                    ┌─────────────┐
                    │  GENERATING │
                    │  TEMPLATE   │
                    └──────┬──────┘
                           │ AI Complete
                           ↓
                    ┌─────────────────────────────────┐
                    │      🔵 TEMPLATE_REVIEW        │
                    │      (LangGraph Interrupt)      │
                    │                                 │
                    │  User sees:                     │
                    │  - Template content             │
                    │  - Parameter schema             │
                    │  - Example output               │
                    │                                 │
                    │  Actions:                       │
                    │  [Confirm] [Modify] [Cancel]    │
                    └─────┬───────────────┬───────────┘
                          │               │
                Confirm   │               │ Cancel
                          │               ↓
                    ┌──────┴──────┐   ┌────────┐
                    │ GENERATING  │   │  END   │
                    │  PARAMS     │   └────────┘
                    └──────┬──────┘
                           │ AI Complete OR
                           │ Rule Engine
                           ↓
                    ┌─────────────────────────────────┐
                    │      🔵 PARAMS_REVIEW          │
                    │      (LangGraph Interrupt)      │
                    │                                 │
                    │  User sees:                     │
                    │  - Device list                  │
                    │  - Parameters per device        │
                    │  - Rendered configs             │
                    │                                 │
                    │  Actions:                       │
                    │  [Execute] [Modify] [Cancel]    │
                    └─────┬───────────────┬───────────┘
                          │               │
                Execute   │               │ Cancel
                          │               ↓
                    ┌──────┴──────┐   ┌────────┐
                    │  EXECUTING  │   │  END   │
                    │  (0 tokens) │   └────────┘
                    └──────┬──────┘
                           │ Complete
                           ↓
                    ┌─────────────┐
                    │  COMPLETED  │
                    └─────────────┘
```

### Component Overview

#### 1. LangChain Tools (3 new tools)

**`GenerateConfigTemplate`**
- Purpose: Generate Jinja2 templates for human review
- Input: project_id, device_type, requirement
- Output: template_content, description, params_schema, rendered_example
- Token Cost: ~150-200 tokens

**`GenerateTemplateParams`**
- Purpose: Generate parameters for confirmed templates
- Input: project_id, confirmed_template, topology_context
- Output: device_params array with rendered previews
- Token Cost: ~50-100 tokens/device (or 0 with rule engine)

**`ExecuteTemplateBasedConfig`**
- Purpose: Execute configuration from templates (local rendering)
- Input: project_id, confirmed_template, confirmed_params
- Output: execution results per device
- Token Cost: **0 tokens** (pure local execution)

#### 2. Template Renderer Module

**Key Features:**
- Jinja2-based configuration rendering
- Preserves network config indentation
- Supports conditionals, loops, filters
- Zero token consumption (local execution)

**Supported Template Features:**
```jinja2
# Variables
hostname {{ hostname }}

# Loops
{% for interface in interfaces %}
interface {{ interface.name }}
 ip address {{ interface.ip }} {{ interface.mask }}
{% endfor %}

# Conditionals
{% if ospf_enabled %}
router ospf {{ process_id }}
 network {{ networks }} area {{ area }}
{% endif %}

# Filters
{{ ip | ip_network }}  # Custom filter for IP operations
```

#### 3. Session State Management

**Stores:**
- Confirmed templates (awaiting params)
- Template metadata (schema, description)
- Session history (for audit trail)
- User modification tracking

**Lifecycle:**
1. Created when template generated
2. Updated when user confirms/modifies
3. Cleared after execution or cancellation
4. TTL: 24 hours (auto-cleanup)

#### 4. LangGraph Workflow Integration

**Interrupt Mechanism:**
```python
# LangGraph interrupt points for HITL
@interrupt
def template_review_checkpoint(state):
    """Pause and wait for user confirmation."""
    return {
        "type": "template_review",
        "data": state["generated_template"]
    }

@interrupt
def params_review_checkpoint(state):
    """Pause and wait for user confirmation."""
    return {
        "type": "params_review",
        "data": state["generated_params"]
    }
```

**State Management:**
- State persisted across interrupts
- User can modify state before resuming
- Full audit trail of all transitions

---

## UI/UX Design

### Template Review Interface

```
┌────────────────────────────────────────────────────────────────┐
│ 📋 AI-Generated Configuration Template                         │
│ ────────────────────────────────────────────────────────────── │
│                                                                 │
│ Device Type: Cisco IOS                                          │
│ Description: OSPF basic configuration                          │
│                                                                 │
│ Template Content:                                               │
│ ┌─────────────────────────────────────────────────────────┐   │
│ │ router ospf {{ process_id }}                             │   │
│ │ {% for network in networks %}                            │   │
│ │  network {{ network.ip }} {{ network.mask }} area {{ area }} │   │
│ │ {% endfor %}                                             │   │
│ └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│ Parameter Schema:                                               │
│ • process_id: int - OSPF process ID                            │
│ • networks: List[Dict] - Network configurations                │
│   - ip: str - Network address                                  │
│   - mask: str - Wildcard mask                                  │
│ • area: str - OSPF area ID                                     │
│                                                                 │
│ Example Output:                                                 │
│ ┌─────────────────────────────────────────────────────────┐   │
│ │ router ospf 1                                            │   │
│ │  network 192.168.1.0 0.0.0.255 area 0                    │   │
│ │  network 10.0.0.0 0.255.255.255 area 0                   │   │
│ └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│ [✓ Confirm & Continue]  [✏️ Request Modification]  [❌ Cancel]  │
└────────────────────────────────────────────────────────────────┘
```

### Parameter Review Interface

```
┌────────────────────────────────────────────────────────────────┐
│ 📊 Configuration Parameters Preview                            │
│ ────────────────────────────────────────────────────────────── │
│                                                                 │
│ Total Devices: 3                                               │
│ Template: OSPF basic configuration                             │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────┐   │
│ │ Device: R1                                               │   │
│ │ ─────────────────────────────────────────────────────── │   │
│ │ • process_id: 1                                          │   │
│ │ • area: 0                                                │   │
│ │ • networks:                                              │   │
│ │   - 192.168.1.0/24 → area 0                             │   │
│ │   - 10.0.0.0/8 → area 0                                 │   │
│ │                                                          │   │
│ │ Rendered Configuration:                                  │   │
│ │ router ospf 1                                           │   │
│ │  network 192.168.1.0 0.0.0.255 area 0                   │   │
│ │  network 10.0.0.0 0.255.255.255 area 0                  │   │
│ └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│ ┌─────────────────────────────────────────────────────────┐   │
│ │ Device: R2                                               │   │
│ │ ...                                                      │   │
│ └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│ [✓ Execute Configuration]  [✏️ Modify Parameters]               │
│ [👁️ Preview All]  [❌ Cancel]                                  │
└────────────────────────────────────────────────────────────────┘
```

---

## API Design & Data Flow

### REST API Endpoints

```
POST /api/v3/projects/{project_id}/templates/config
  ├─ Request: { "device_type": "cisco_ios", "requirement": "Configure OSPF" }
  └─ Response: { "template_id": "uuid", "template_content": "...", "params_schema": {...} }

PUT /api/v3/projects/{project_id}/templates/{template_id}/confirm
  ├─ Request: { "action": "confirm" | "modify", "modifications": {...} }
  └─ Response: { "status": "confirmed", "next_step": "generate_params" }

POST /api/v3/projects/{project_id}/templates/{template_id}/params
  ├─ Request: { "mode": "ai" | "direct" }
  └─ Response: { "device_params": [...], "preview": {...} }

POST /api/v3/projects/{project_id}/templates/{template_id}/execute
  ├─ Request: { "confirmed_params": [...] }
  └─ Response: { "execution_id": "uuid", "status": "executing" }

GET /api/v3/projects/{project_id}/templates/{template_id}/status
  └─ Response: { "status": "completed", "progress": 100, "results": [...] }

DELETE /api/v3/projects/{project_id}/templates/{template_id}
  └─ Response: { "status": "cancelled" }
```

### SSE Progress Stream

```typescript
// Server-Sent Events for real-time progress
// Endpoint: GET /api/v3/projects/{project_id}/templates/{template_id}/stream

// Event Types:
event: template_generated
data: {"template_id": "uuid", "content": "..."}

event: params_generated
data: {"total_devices": 100, "params": [...]}

event: execution_progress
data: {
  "type": "batch_complete",
  "batch": 5,
  "total_batches": 10,
  "progress": 50,
  "success": 48,
  "failed": 2,
  "current_device": "R50"
}

event: execution_complete
data: {
  "total_devices": 100,
  "success": 98,
  "failed": 2,
  "duration_sec": 180
}
```

### Data Flow Diagram

```
User Request
    ↓
┌─────────────────────────────────────────────────────────────┐
│ 1. API Layer (FastAPI)                                      │
│    - Validates request                                      │
│    - Creates session state                                  │
│    - Returns template_id                                    │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. AI Agent (LangGraph)                                     │
│    - Generate template (LLM call)                           │
│    - Store in session manager                              │
│    - Trigger interrupt 🔵                                   │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. HITL Checkpoint (Frontend Display)                       │
│    - Show template to user                                  │
│    - Wait for user action                                   │
│    - [Confirm] [Modify] [Cancel]                            │
└──────────────────────┬──────────────────────────────────────┘
                       ↓ (User confirms)
┌─────────────────────────────────────────────────────────────┐
│ 4. AI Agent (LangGraph Resumes)                             │
│    Path A: Generate params (LLM) ~5000 tokens              │
│    Path B: Rule engine (0 tokens) ⚡                         │
│    - Trigger interrupt 🔵                                   │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. HITL Checkpoint (Frontend Display)                       │
│    - Show parameters to user                                │
│    - Render configuration preview                          │
│    - [Execute] [Modify] [Cancel]                            │
└──────────────────────┬──────────────────────────────────────┘
                       ↓ (User executes)
┌─────────────────────────────────────────────────────────────┐
│ 6. Execution Engine (Local, 0 tokens)                       │
│    - Render templates (Jinja2)                              │
│    - Batch execution (Nornir + Netmiko)                    │
│    - Stream progress via SSE                                │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. Result Aggregation                                       │
│    - Collect results from all devices                      │
│    - Generate summary report                               │
│    - Clean up session state                                │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
                  Return to User
```

### Error Handling Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Error Detection at Each Stage                               │
└─────────────────────────────────────────────────────────────┘

Template Generation Error:
    ├─ Invalid Jinja2 syntax → [AI Retry] + [Show Error Context]
    ├─ Incomplete template → [Request Clarification]
    └─ LLM timeout → [Retry] + [Fallback to template library]

Parameter Generation Error:
    ├─ Missing device data → [Fetch from topology]
    ├─ Invalid parameter values → [Validation Error] → [User Correction]
    └─ Rule engine failure → [Fallback to AI generation]

Execution Error:
    ├─ Device unreachable → [Retry 3x] → [Mark as failed] → [Continue]
    ├─ Invalid command → [Show error] → [Suggest fix] → [User decision]
    └─ Authentication failure → [Pause] → [Request credentials]

Error Recovery Strategies:
    ├─ Automatic retry (transient errors)
    ├─ Partial success handling (continue with remaining devices)
    ├─ Rollback support (undo partial changes)
    └─ User notification (SSE + UI alerts)
```

### Template Lifecycle Management

```
┌─────────────────────────────────────────────────────────────┐
│                      Template Lifecycle                      │
└─────────────────────────────────────────────────────────────┘

1. DRAFT
   ├─ Created by AI
   ├─ Stored in session (temporary)
   └─ User reviews and modifies

2. CONFIRMED
   ├─ User approved template
   ├─ Stored in template library (persistent)
   └─ Ready for parameter generation

3. ACTIVE
   ├─ Parameters generated
   ├─ Ready for execution
   └─ Can be cloned for similar tasks

4. EXECUTED
   ├─ Configuration applied
   ├─ Results recorded
   └─ Move to archive

5. ARCHIVED
   ├─ Historical record
   ├─ Analytics data
   └─ Cleanup after 90 days

Version Control:
    ├─ Each save creates new version
    ├─ Semantic versioning (v1.0, v1.1, v2.0)
    ├─ Diff view between versions
    └─ Rollback to previous version
```

---

## 🔥 Large-Scale Topology Support (1000+ Nodes)

### Overview

One of the most powerful use cases for the template-based configuration system is **rapid provisioning of large-scale network topologies**. This section details optimizations for environments with **hundreds to thousands of nodes**.

### Challenge: Traditional AI Approach at Scale

```
Problem: Configure 1000 routers with OSPF

Traditional AI Approach:
- AI generates config for each router: 150 tokens × 1000 = 150,000 tokens
- Serial or limited parallel execution: ~30-50 minutes
- High cost, slow execution, poor scalability
```

### Solution: Direct Execution Mode

The key innovation is allowing users to **modify and directly execute** templates without requiring AI re-analysis:

```
Template-Based Direct Execution:
1. AI generates template once: ~150 tokens
2. User reviews and modifies if needed
3. User clicks "⚡ Confirm & Execute"
4. Rule engine generates params for 1000 devices: 0 tokens
5. Parallel execution (50-100 concurrent): ~5 minutes
6. Total: 150 tokens, 5 minutes
```

### Enhanced HITL Workflow for Scale

```
┌─────────────────────────────────────────────────────────────┐
│ Step 1: AI Generates Template (Once)                         │
│                                                              │
│ User: "Configure OSPF on all 1000 routers"                   │
│                                                              │
│ AI generates template: ~150 tokens                           │
│ router ospf {{ process_id }}                                 │
│ {% for network in networks %}                                │
│  network {{ network.ip }} {{ network.mask }} area {{ area }} │
│ {% endfor %}                                                 │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ 🔵 HITL Checkpoint 1: Template Review                        │
│                                                              │
│ User can:                                                    │
│ - Review template syntax                                     │
│ - Modify template directly                                  │
│ - See preview with sample data                               │
│                                                              │
│ Actions: [✓ Confirm & Continue]  [⚡ Confirm & Execute*]     │
│          [✏️ Modify]  [❌ Cancel]                             │
│                                                              │
│ * "Confirm & Execute" = Skip AI, go to rule engine           │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2A: Rule Engine (0 tokens) OR Step 2B: AI (5000 tokens)│
│                                                              │
│ If user chose "⚡ Confirm & Execute":                        │
│   → Rule engine analyzes template                            │
│   → Extracts device names from topology                      │
│   → Auto-assigns IPs and parameters                          │
│   → Generates 1000 device param sets: 0 tokens               │
│                                                              │
│ If user chose "✓ Confirm & Continue":                       │
│   → AI analyzes template                                     │
│   → Generates parameters: ~5000 tokens                       │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ 🔵 HITL Checkpoint 2: Parameter Review                       │
│                                                              │
│ For 1000 devices, show SUMMARY:                              │
│ - Total devices: 1000                                        │
│ - Configuration patterns: 3 unique patterns                 │
│ - Sample configs (first 3 devices)                           │
│ - IP addressing scheme used                                  │
│                                                              │
│ Actions: [⚡ Execute All*]  [✓ Review & Modify]  [❌ Cancel] │
│                                                              │
│ * "Execute All" = Start parallel execution                   │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Parallel Batch Execution                             │
│                                                              │
│ Configuration execution:                                     │
│ - Batch size: 50 devices (configurable)                      │
│ - Batches: 20 total (1000 / 50)                              │
│ - Parallel execution within each batch                       │
│ - Real-time progress updates via SSE                         │
│ - Estimated time: 3-5 minutes                                │
│                                                              │
│ Progress updates:                                             │
│ Batch 1/20: Configuring devices 1-50...                      │
│ Batch 2/20: Configuring devices 51-100...                    │
│ ...                                                          │
│ Complete: 998 success, 2 failed                              │
└─────────────────────────────────────────────────────────────┘
```

### Rule Engine: Intelligent Parameter Generation

**Concept:** Use rule-based logic instead of AI for generating parameters in large topologies.

**How It Works:**
```
Input: Template + Topology (1000 devices)
         ↓
    Rule Engine (0 tokens)
         ↓
    Device Analysis
    ├─ Extract numbering from names (R1 → 1, R2 → 2, ...)
    ├─ Group by device type (routers, switches, firewalls)
    ├─ Apply addressing scheme (sequential, VLAN-based, hierarchical)
    └─ Generate parameters for each device
         ↓
Output: 1000 device parameter sets (< 1 second)
```

**Addressing Schemes:**
```
1. Sequential (Default)
   R1: 192.168.1.0/24
   R2: 192.168.2.0/24
   ...
   R1000: 192.168.1000.0/24

2. VLAN-Based
   VLAN 100: 10.0.100.0/24
   VLAN 101: 10.0.101.0/24
   ...

3. Hierarchical
   Core routers: 10.0.0.0/24
   Distribution: 10.1.0.0/16
   Access switches: 10.100.0.0/16

4. Device Type Based
   Routers: 192.168.0.0/16
   Switches: 192.169.0.0/16
   Firewalls: 192.170.0.0/16
```

### Batch Parallel Execution

**Dynamic Batching Strategy:**
```
Device Count    Batch Size    Concurrency    Estimated Time
────────────────────────────────────────────────────────────
1-10            10            10             < 30 seconds
11-50           20            20             < 1 minute
51-100          30            30             1-2 minutes
101-500         50            50             2-5 minutes
500+            100           100            3-8 minutes
```

**Execution Flow:**
```
┌─────────────────────────────────────────────────────────────┐
│ Batch 1: Devices 1-100                                       │
│ ├─ Render 100 configs (Jinja2, local)                        │
│ ├─ Execute in parallel (Nornir + Netmiko)                   │
│ ├─ Collect results                                           │
│ └─ Stream progress: "Batch 1/10 complete, 35% done"         │
├─────────────────────────────────────────────────────────────┤
│ Batch 2: Devices 101-200                                     │
│ └─ ...                                                       │
├─────────────────────────────────────────────────────────────┤
│ ...                                                          │
├─────────────────────────────────────────────────────────────┤
│ Batch 10: Devices 901-1000                                   │
│ └─ Complete: 997 success, 3 failed                          │
└─────────────────────────────────────────────────────────────┘
```

### Configuration Summary for Large Topologies

**Challenge:** Showing 1000 device configurations is impractical.

**Solution:** Intelligent summaries with pattern analysis.

```
┌─────────────────────────────────────────────────────────────┐
│ Configuration Summary: 1000 Devices                          │
├─────────────────────────────────────────────────────────────┤
│ Total Devices:        1,000                                  │
│ Unique Patterns:      3                                     │
│ Total Config Lines:   ~15,000                               │
│ Estimated Time:       ~5 minutes                            │
├─────────────────────────────────────────────────────────────┤
│ Pattern Analysis:                                              │
│ • Pattern A (650 devices): Standard OSPF config             │
│ • Pattern B (300 devices): OSPF + BGP                       │
│ • Pattern C (50 devices):  OSPF + BGP + MPLS                │
├─────────────────────────────────────────────────────────────┤
│ Sample Configurations (first 3):                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Device: R1 (Pattern A)                                  │ │
│ │ router ospf 1                                          │ │
│ │  network 192.168.1.0 0.0.0.255 area 0                  │ │
│ │  network 10.1.1.1 0.0.0.0 area 0                       │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Device: R2 (Pattern A)                                  │ │
│ │ [Similar to R1, different IPs]                          │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ...                                                          │
└─────────────────────────────────────────────────────────────┘
```

### Performance Benchmarks

#### Scenario: 1000 Router OSPF Configuration

| Metric | Traditional AI | Template + AI | Template + Direct |
|--------|---------------|---------------|-------------------|
| **Token Consumption** | 150,000 | 5,000 | **400** |
| **Execution Time** | 30-50 min | 10-15 min | **3-5 min** |
| **Cost (at $10/M tokens)** | $1.50 | $0.05 | **$0.004** |
| **User Control** | Low | Medium | **High** |
| **Parallel Execution** | Limited | Yes | **Yes (100 concurrent)** |

#### Scenario: 5000 Switch VLAN Configuration

| Metric | Traditional AI | Template + Direct |
|--------|---------------|-------------------|
| **Token Consumption** | 400,000 | **400** |
| **Execution Time** | 2-3 hours | **15-20 min** |
| **Cost** | $4.00 | **$0.004** |
| **Scalability** | Poor | **Excellent** |

### Addressing Schemes for Large Topologies

The rule engine supports multiple automatic addressing schemes:

```python
# 1. Sequential Addressing (Default)
# R1: 192.168.1.0/24, R2: 192.168.2.0/24, ..., R1000: 192.168.1000.0/24

# 2. VLAN-Based Addressing
# VLAN 100: 10.0.100.0/24, VLAN 101: 10.0.101.0/24, ...

# 3. Hierarchical Addressing
# Core routers: 10.0.0.0/24
# Distribution routers: 10.1.0.0/16
# Access switches: 10.100.0.0/16

# 4. Device Type Based
# Routers: 192.168.0.0/16
# Switches: 192.169.0.0/16
# Firewalls: 192.170.0.0/16
```

### Error Handling for Scale

For 1000+ devices, some failures are inevitable. The system provides:

```python
{
    "total_devices": 1000,
    "summary": {
        "success": 987,
        "failed": 13,
        "skipped": 0
    },
    "failed_devices": [
        {
            "device_name": "R456",
            "error": "Connection timeout",
            "retry_available": true
        },
        ...
    ],
    "retry_suggestions": {
        "auto_retry": True,
        "retry_batch_size": 10,
        "exponential_backoff": True
    }
}
```

### Use Cases for Large-Scale Support

1. **Network Training Labs**: Provision 1000+ device labs for student training
2. **CI/CD Testing**: Automated topology setup for testing network automation scripts
3. **Disaster Recovery Drills**: Rapid deployment of large backup topologies
4. **Network Simulation**: Research environments with thousands of nodes
5. **Data Center Fabric**: Configure spine-leaf topologies with hundreds of leaf switches

---

## 🔥🔥 Node Creation Templates (Batch Topology Provisioning)

### Overview

Just as configuration templates enable rapid device configuration, **node creation templates** enable rapid topology provisioning. This is particularly valuable for:

- **Training labs**: Provision 100+ device labs in minutes
- **Testing environments**: Quickly spin up complex test topologies
- **Data center simulation**: Create spine-leaf fabrics with hundreds of nodes
- **Network research**: Deploy large-scale simulation topologies

### Current vs. Template-Based Node Creation

#### Scenario: Create 100 Routers

**Current Method:**
```
AI calls create_node tool 100 times:
- Token cost: 50 tokens/node × 100 = 5000 tokens
- Execution time: 5-10 minutes (serial/limited parallel)
- No batch operations
- Manual positioning required
```

**Template Method:**
```
1. AI generates node creation template: ~100 tokens
2. User reviews and confirms template
3. Rule engine creates nodes in parallel batches: 0 tokens
4. Total: 100 tokens, 30-60 seconds
```

**Savings:** 98% tokens, 90% time

### Node Creation Workflow

```
User Request: "Create a data center topology with 2 core routers,
              10 aggregation switches, and 100 access switches"
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 1: AI Generates Node Creation Template                  │
│                                                              │
│ AI Output:                                                   │
│ {                                                            │
│   "node_groups": [                                          │
│     {                                                        │
│       "node_type": "cisco_iosv",                            │
│       "count": 2,                                           │
│       "name_pattern": "Core-R{{ id }}",                     │
│       "properties": {"ram": 4096, "cpus": 2},              │
│       "position": {"y": 100, "x_spacing": 600}             │
│     },                                                       │
│     {                                                        │
│       "node_type": "cisco_iosv_l2",                         │
│       "count": 10,                                          │
│       "name_pattern": "Agg-SW{{ id }}",                    │
│       "position": {"grid": "2x5", "y": 300}                 │
│     },                                                       │
│     {                                                        │
│       "node_type": "cisco_iosv_l2",                         │
│       "count": 100,                                         │
│       "name_pattern": "Acc-SW{{ id }}",                    │
│       "position": {"grid": "10x10", "y": 600}               │
│     }                                                       │
│   ],                                                         │
│   "layout": "auto_spine_leaf",                               │
│   "resource_limits": {"max_ram_mb": 120000}                  │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ 🔵 HITL Checkpoint: Node Template Review                    │
│                                                              │
│ User sees:                                                  │
│ • Total nodes: 112                                           │
│ • Group breakdown:                                           │
│   - 2x Core routers (Core-R1, Core-R2)                      │
│   - 10x Aggregation switches (Agg-SW1 - Agg-SW10)          │
│   - 100x Access switches (Acc-SW1 - Acc-SW100)             │
│ • Resource requirements:                                     │
│   - RAM: ~120 GB                                             │
│   - vCPUs: 112                                               │
│ • Layout preview (visual diagram)                            │
│                                                              │
│ Actions: [⚡ Batch Create]  [✏️ Modify]  [❌ Cancel]         │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Parallel Batch Node Creation (0 tokens)             │
│                                                              │
│ Process:                                                     │
│ - Validate resources                                         │
│ - Create nodes in parallel batches (20-50 concurrent)        │
│ - Auto-position nodes using layout strategy                 │
│ - Real-time progress streaming                               │
│                                                              │
│ Progress:                                                    │
│ Batch 1/6: Creating 20 nodes...                             │
│ Batch 2/6: Creating 20 nodes...                             │
│ ...                                                          │
│ Complete: 112/112 nodes created successfully                 │
└─────────────────────────────────────────────────────────────┘
```

### Node Template Schema

**Concept:** Define groups of similar nodes with positioning and auto-linking.

**Schema Structure:**
```
NodeCreationTemplate
├─ node_groups: List[NodeGroup]
│   ├─ node_type: "cisco_iosv" | "vpcs" | ...
│   ├─ count: 100
│   ├─ name_pattern: "R{{ id }}"  → R1, R2, ..., R100
│   ├─ properties: {ram, cpus, adapters}
│   └─ position: {strategy, grid, spacing}
├─ layout: "auto_grid" | "auto_spine_leaf" | "auto_star" | ...
├─ auto_link: AutoLinkConfig
│   └─ links: List[LinkPattern]
└─ resource_limits: {max_ram_mb, max_vcpus}
```

**Example: Spine-Leaf Topology**
```
{
  "node_groups": [
    {
      "name": "spine",
      "node_type": "cisco_iosv",
      "count": 4,
      "name_pattern": "Spine{{ id }}",
      "position": {"y": 100, "x_spacing": 400}
    },
    {
      "name": "leaf",
      "node_type": "cisco_iosv_l2",
      "count": 48,
      "name_pattern": "Leaf{{ id }}",
      "position": {"grid": "6x8", "y": 400}
    }
  ],
  "auto_link": {
    "links": [
      {
        "from": "spine",
        "to": "leaf",
        "strategy": "mesh"  # Each spine to all leafs
      }
    ]
  }
}

Result: 4 spine + 48 leaf + 192 links (4×48)
Time: ~2-3 minutes
```

### Automatic Layout Strategies

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Grid Layout (auto_grid)                                  │
│                                                              │
│   [1]  [2]  [3]  [4]  [5]                                   │
│   [6]  [7]  [8]  [9]  [10]                                  │
│   [11] [12] [13] [14] [15]                                  │
│                                                              │
│   Best for: Uniform node types, regular topologies         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 2. Spine-Leaf (auto_spine_leaf)                             │
│                                                              │
│   [Spine1]--------[Spine2]                                  │
│      |  |  |  |      |  |  |  |                             │
│   [Leaf1..Leaf48]  [Leaf49..Leaf96]                         │
│                                                              │
│   Best for: Data center fabrics                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 3. Star (auto_star)                                         │
│                                                              │
│              [Core]                                         │
│            /  |  |  \                                       │
│        [Edge1..Edge20]                                      │
│                                                              │
│   Best for: Hub-and-spoke topologies                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 4. Hierarchical (manual)                                    │
│                                                              │
│   [Core1]     [Core2]                                       │
│      |            |                                         │
│   [Agg1..Agg10]                                            │
│      /    |   |    \                                        │
│  [Acc1..Acc100]                                            │
│                                                              │
│   Best for: Enterprise campus networks                      │
└─────────────────────────────────────────────────────────────┘
```

### Auto-Linking Strategies

```
Link Pattern Strategies:

┌─────────────────────────────────────────────────────────────┐
│ 1. Mesh (Full Mesh)                                         │
│                                                              │
│   [A] ←→ [B]                                                │
│    ↑ ↖  ↑ ↗                                                │
│    |  \ |  |                                                │
│   [D] ←→ [C]                                                │
│                                                              │
│   Every node connects to every other node                   │
│   Links: n×(n-1)/2                                          │
│   Best for: High availability, small groups                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 2. Paired (One-to-One)                                      │
│                                                              │
│   [Group A: A1, A2, A3...]                                  │
│         ↓  ↓  ↓                                            │
│   [Group B: B1, B2, B3...]                                  │
│                                                              │
│   A1→B1, A2→B2, A3→B3, ...                                 │
│   Links: min(count_A, count_B)                              │
│   Best for: Point-to-point connections                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 3. Linear (Chain)                                           │
│                                                              │
│   [A1]→[A2]→[A3]→[A4]→...→[An]                             │
│                                                              │
│   Sequential connection                                     │
│   Links: n-1                                                │
│   Best for: Ring topologies, daisy-chains                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 4. One-to-Many (Star)                                       │
│                                                              │
│         [Center]                                            │
│       /  |  |  \                                            │
│     [E1][E2][E3][E4]...                                      │
│                                                              │
│   Center connects to all edge nodes                         │
│   Links: count_edge                                         │
│   Best for: Hub-and-spoke                                   │
└─────────────────────────────────────────────────────────────┘
```

### Performance Benchmarks

#### Scenario: 100 Router Lab

| Metric | Current Method | Template Method |
|--------|---------------|-----------------|
| **Token Consumption** | 5,000 | **100** |
| **Execution Time** | 5-10 min | **30-60 sec** |
| **User Control** | Low | **High (preview before create)** |
| **Positioning** | Manual | **Automatic** |

#### Scenario: 500 Switch Data Center

| Metric | Current Method | Template Method |
|--------|---------------|-----------------|
| **Token Consumption** | 25,000 | **150** |
| **Execution Time** | 25-30 min | **2-3 min** |
| **Links Created** | Manual | **Auto (mesh, spine-leaf)** |

#### Scenario: 1000 Node Training Lab

| Metric | Current Method | Template Method |
|--------|---------------|-----------------|
| **Token Consumption** | 50,000 | **200** |
| **Execution Time** | 50-60 min | **4-6 min** |
| **Scalability** | Poor | **Excellent** |

### Complete Example: Enterprise Data Center

```python
# User Request
"""
Create an enterprise data center topology:
- 4 spine routers (high-end)
- 20 leaf switches (10G)
- 200 access switches (1G)
- 500 servers (VPCS)

Use spine-leaf architecture with full mesh connectivity.
All servers connect to access switches in pairs.
"""

# Generated Template
{
    "node_groups": [
        {
            "name": "spine",
            "node_type": "cisco_iosv",
            "count": 4,
            "name_pattern": "Spine-R{{ id }}",
            "properties": {
                "ram": 4096,
                "cpus": 2,
                "adapters": 8
            },
            "position": {
                "strategy": "hierarchical",
                "y": 100,
                "x_spacing": 600
            }
        },
        {
            "name": "leaf",
            "node_type": "cisco_iosv_l2",
            "count": 20,
            "name_pattern": "Leaf-SW{{ id }}",
            "properties": {
                "ram": 2048,
                "cpus": 1,
                "adapters": 16
            },
            "position": {
                "strategy": "grid",
                "grid_rows": 4,
                "grid_cols": 5,
                "y": 400,
                "x_spacing": 300,
                "y_spacing": 200
            }
        },
        {
            "name": "access",
            "node_type": "cisco_iosv_l2",
            "count": 200,
            "name_pattern": "Acc-SW{{ id }}",
            "properties": {
                "ram": 1024,
                "cpus": 1,
                "adapters": 4
            },
            "position": {
                "strategy": "grid",
                "grid_rows": 10,
                "grid_cols": 20,
                "y": 800,
                "x_spacing": 120,
                "y_spacing": 100
            }
        },
        {
            "name": "server",
            "node_type": "vpcs",
            "count": 500,
            "name_pattern": "Server-{{ id }}",
            "properties": {},
            "position": {
                "strategy": "grid",
                "grid_rows": 20,
                "grid_cols": 25,
                "y": 1200,
                "x_spacing": 60,
                "y_spacing": 60
            }
        }
    ],
    "auto_link": {
        "links": [
            {
                "from_group": "spine",
                "to_group": "leaf",
                "strategy": "mesh"
            },
            {
                "from_group": "leaf",
                "to_group": "access",
                "strategy": "paired",
                "count": 10
            },
            {
                "from_group": "access",
                "to_group": "server",
                "strategy": "paired",
                "count": 2
            }
        ]
    },
    "layout": "auto_spine_leaf",
    "resource_limits": {
        "max_ram_mb": 750000,
        "max_vcpus": 724
    }
}

# Execution Result
{
    "total_nodes": 724,
    "created": 724,
    "failed": 0,
    "duration_sec": 285,  # ~4.75 minutes
    "links_created": 4280,  # Auto-created
    "groups": [
        {"name": "spine", "created": 4, "failed": 0},
        {"name": "leaf", "created": 20, "failed": 0},
        {"name": "access", "created": 200, "failed": 0},
        {"name": "server", "created": 500, "failed": 0}
    ]
}
```

### Combined Workflow: Node Creation + Configuration

The real power comes from combining both template systems:

```
1. Create topology with node templates
   - 724 nodes created in ~5 minutes
   - 4280 links auto-created

2. Configure devices with config templates
   - Generate OSPF/BGP templates
   - Configure 724 devices in ~5 minutes

Total: 724-node data center
  - Created and configured in ~10 minutes
  - Token cost: ~400 (vs ~100,000 with AI-only approach)
  - 99.6% token savings
```

---

## 🔥🔥🔥 Link Creation Templates (Batch Topology Connectivity)

### Overview

Just as node and configuration templates enable rapid provisioning, **link creation templates** enable rapid connectivity setup. This completes the template trilogy for complete topology automation.

### Current vs. Template-Based Link Creation

#### Scenario: Create Full-Mesh Network (100 Routers)

**Current Method:**
```
AI calls create_link tool 4950 times (100×99/2):
- Token cost: 30 tokens/link × 4950 = ~150,000 tokens
- Execution time: 30-40 minutes (serial/limited parallel)
- Manual port management
- Error-prone
```

**Template Method:**
```
1. AI generates link template: ~200 tokens
2. User reviews link patterns and topology preview
3. Rule engine creates links in parallel batches: 0 tokens
4. Total: 200 tokens, 2-3 minutes
```

**Savings:** 99.9% tokens, 95% time

### Link Creation Workflow

```
User Request: "Create full-mesh connectivity between all routers"
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 1: AI Generates Link Creation Template                 │
│                                                              │
│ AI Output:                                                   │
│ {                                                            │
│   "link_patterns": [                                        │
│     {                                                        │
│       "from_nodes": {"tag": "router"},                      │
│       "to_nodes": {"tag": "router"},                        │
│       "strategy": "full_mesh",                              │
│       "port_allocation": "round_robin"                       │
│     }                                                       │
│   ],                                                         │
│   "total_links": 4950                                       │
│ }                                                            │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ 🔵 HITL Checkpoint: Link Template Review                    │
│                                                              │
│ User sees:                                                  │
│ • Total links: 4,950                                         │
│ • Topology type: Full Mesh                                  │
│ • Port allocation strategy: Round-robin                     │
│ • Topology preview (visual graph)                            │
│ • Port utilization estimates                                 │
│                                                              │
│ Sample links (first 10):                                     │
│ • R1:Gi0/0 → R2:Gi0/0                                       │
│ • R1:Gi0/1 → R3:Gi0/0                                       │
│ • ...                                                        │
│                                                              │
│ Actions: [⚡ Batch Create]  [👁️ Detailed Preview]  [✏️ Modify] │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Detailed Preview (Optional)                          │
│                                                              │
│ • Port assignment per node                                   │
│ • Bandwidth calculations                                     │
│ • Redundancy analysis                                        │
│ • Link naming scheme                                         │
│                                                              │
│ [⚡ Confirm Create All]  [🔧 Adjust Ports]  [⬅️ Back]        │
└─────────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Parallel Batch Link Creation (0 tokens)             │
│                                                              │
│ Process:                                                     │
│ - Validate port availability                                  │
│ - Allocate ports using strategy                             │
│ - Create links in parallel batches (50-100 concurrent)       │
│ - Handle conflicts automatically                              │
│ - Real-time progress streaming                               │
│                                                              │
│ Progress:                                                    │
│ Batch 1/50: Creating 99 links...                            │
│ Batch 2/50: Creating 99 links...                            │
│ ...                                                          │
│ Complete: 4,950/4,950 links created successfully              │
└─────────────────────────────────────────────────────────────┘
```

### Link Template Schema (Simplified)

```python
class LinkCreationTemplate(BaseModel):
    """Template for batch link creation."""

    # Link patterns
    link_patterns: List[LinkPattern]

    # Port allocation strategy
    port_allocation: PortAllocationStrategy


class LinkPattern(BaseModel):
    """Pattern for creating links between node groups."""

    from_nodes: NodeSelector  # Source nodes
    to_nodes: NodeSelector    # Destination nodes

    strategy: Literal[
        "one_to_one",        # 1:1 pairing
        "one_to_many",       # Star topology
        "many_to_many",      # Full mesh
        "sequential",        # Linear chain
        "ring"              # Ring topology
    ]

    port_allocation: PortAllocationStrategy


class NodeSelector(BaseModel):
    """Select nodes for linking."""

    selector_type: Literal["group", "name_pattern", "tag", "all"]
    group_name: Optional[str]
    name_pattern: Optional[str]  # "R*", "Core-*"
    tag: Optional[str]


class PortAllocationStrategy(BaseModel):
    """How to allocate ports for links."""

    strategy: Literal[
        "round_robin",       # Distribute evenly
        "sequential",        # Use in order
        "optimized",         # Smart allocation
        "auto"               # Automatic selection
    ]

    on_conflict: Literal[
        "skip",              # Skip if port unavailable
        "use_next",          # Use next available port
        "fail"               # Fail on conflict
    ] = "use_next"
```

### Common Topology Patterns

The system includes pre-built topology patterns:

#### 1. Spine-Leaf (Data Center)

```
Pattern: Full mesh between spine and leaf layers

Example: 4 Spine × 48 Leaf
- Links: 4 × 48 = 192 links
- Each spine: 48 downlinks
- Each leaf: 4 uplinks
```

#### 2. Three-Tier Hierarchical

```
Core ↔ Aggregation ↔ Access

Example: 2 Core × 10 Agg × 100 Access
- Core-Agg: Full mesh (2×10 = 20 links)
- Agg-Access: Paired (10×10 = 100 links)
- Total: 120 links
```

#### 3. Ring Topology

```
Sequential connection with wrap-around

Example: 10 routers in ring
- Links: 10 (each node connects to 2 neighbors)
- Pattern: R1→R2→R3→...→R10→R1
```

#### 4. Full Mesh

```
All nodes connected to all nodes

Example: 10 routers
- Links: 45 (10×9/2)
- Every node connects to every other node
```

#### 5. Star Topology

```
Center node connects to all edge nodes

Example: 1 Core + 20 Edge
- Links: 20
- Center degree: 20
- Edge degree: 1
```

### Performance Benchmarks

#### Scenario: Spine-Leaf Data Center (8 Spine × 100 Leaf)

| Metric | Current Method | Template Method |
|--------|---------------|-----------------|
| **Token Consumption** | 30,000 | **200** |
| **Execution Time** | 15-20 min | **2-3 min** |
| **Links Created** | Manual | **Auto (800 links)** |
| **Port Management** | Manual | **Auto (round-robin)** |

#### Scenario: Full Mesh (100 Routers)

| Metric | Current Method | Template Method |
|--------|---------------|-----------------|
| **Token Consumption** | 150,000 | **200** |
| **Execution Time** | 30-40 min | **2-3 min** |
| **Links Created** | 4,950 | **4,950** |
| **Error Rate** | High (manual) | **Low (validated)** |

#### Scenario: Large-Scale Data Center

**Topology:**
- 8 Spine routers
- 100 Leaf switches (48-port each)
- 2000 Servers
- Redundant connections

**Link Creation:**
- Spine-Leaf: 8 × 100 = 800 links
- Leaf-Server: 2000 × 2 = 4000 links
- **Total: 4,800 links**

| Metric | Current Method | Template Method |
|--------|---------------|-----------------|
| **Token Consumption** | ~150,000 | **300** |
| **Execution Time** | 45-60 min | **5-8 min** |
| **Savings** | - | **99.8% tokens, 90% time** |

### Intelligent Port Allocation

The system includes smart port allocation algorithms:

```python
# Example: Optimized allocation for multi-adapter switches

Strategy: "optimized"

Considerations:
- Port speed matching (10G ports for spine-leaf, 1G for servers)
- Physical adapter separation (redundancy across modules)
- Load balancing (distribute connections evenly)
- Future expansion planning (reserve ports)

Result:
- Spine-Leaf: Use 10G ports on adapter 0-3
- Leaf-Server: Use 1G ports on adapter 4-7
- Redundant paths: Use different physical adapters
```

### Combined Workflow: Complete Topology Provisioning

```
Step 1: Node Creation Template
  - 2108 nodes created in ~4 minutes
  - Token cost: ~200

Step 2: Link Creation Template
  - 20,780 links created in ~6 minutes
  - Token cost: ~300

Step 3: Configuration Template
  - 2108 devices configured in ~5 minutes
  - Token cost: ~200

TOTAL: Large Data Center
  - 2,108 nodes + 20,780 links
  - Created, linked, and configured in ~15 minutes
  - Token cost: ~700 (vs ~250,000 with AI-only)
  - 99.7% token savings
```

### Use Cases

1. **Data Center Fabric:** Spine-Leaf with thousands of links
2. **ISP Backbone:** Full-mesh core routers
3. **Campus Network:** Three-tier hierarchical
4. **Ring Topology:** Metropolitan area networks
5. **Research Networks:** Custom experimental topologies

---

## Implementation Phases

### Phase 1: Core MVP (Minimum Viable Product)

**Status:** 📋 Planned
**Estimated Effort:** 3-5 days

**Tasks:**
1. ✅ Create `ConfigTemplateRenderer` class
2. ✅ Create `TemplateSessionManager` class
3. ✅ Implement `GenerateConfigTemplate` tool
4. ✅ Implement `GenerateTemplateParams` tool
5. ✅ Implement `ExecuteTemplateBasedConfig` tool
6. ✅ Create `config_templates/` package structure
7. ✅ Update system prompts with template workflow
8. ✅ Basic error handling and validation

**Deliverables:**
- Working three-step HITL workflow
- Template rendering for Cisco IOS devices
- Basic CLI/API responses
- Unit tests for core components

### Phase 2: Enhanced User Experience & Direct Execution

**Status:** 💡 Proposed
**Estimated Effort:** 2-3 days

**Tasks:**
1. Enhanced UI for template/parameter review
2. Configuration preview functionality
3. Template modification and retry logic
4. 🔥 **Direct execution mode** (skip AI, use rule engine)
5. Progress indicators for multi-device configs
6. Improved error messages and recovery

**Deliverables:**
- User-friendly review interfaces
- Preview-before-execute capability
- **Rule-based parameter generation (0 token cost)**
- User documentation

### Phase 2.5: Node Creation Templates

**Status:** 💡 Proposed
**Estimated Effort:** 2-3 days

**Tasks:**
1. 🔥🔥 Implement `GenerateNodeTemplate` tool
2. 🔥🔥 Implement `ExecuteBatchNodeCreation` tool
3. 🔥🔥 Create `NodeCreationTemplate` schema
4. 🔥🔥 Implement automatic positioning algorithms
5. 🔥🔥 Implement auto-linking functionality
6. Resource validation before creation

**Deliverables:**
- **Batch node creation with 0 token cost**
- **Auto-positioning (grid, spine-leaf, star, mesh)**
- **Auto-linking (mesh, paired, linear)**
- Progress streaming for large batches

### Phase 2.75: Link Creation Templates

**Status:** 💡 Proposed
**Estimated Effort:** 2-3 days

**Tasks:**
1. 🔥🔥🔥 Implement `GenerateLinkTemplate` tool
2. 🔥🔥🔥 Implement `ExecuteBatchLinkCreation` tool
3. 🔥🔥🔥 Create `LinkCreationTemplate` schema
4. 🔥🔥🔥 Implement topology pattern library (Spine-Leaf, Ring, Mesh, Star, etc.)
5. 🔥🔥🔥 Implement intelligent port allocation algorithms
6. Port availability validation and conflict handling

**Deliverables:**
- **Batch link creation with 0 token cost**
- **5+ pre-built topology patterns**
- **Smart port allocation (round-robin, optimized)**
- **Port conflict detection and auto-resolution**
- Progress streaming for thousands of links

### Phase 3: Template Library & Large-Scale Support

**Status:** 💡 Proposed
**Estimated Effort:** 2-3 days

**Tasks:**
1. Template persistence and storage
2. Pre-built template library (OSPF, BGP, VLAN, NAT, etc.)
3. 🔥 **Batch parallel execution** (dynamic batching for 100+ devices)
4. 🔥 **Rule engine enhancements** (intelligent parameter generation)
5. 🔥 **Real-time progress streaming** via SSE
6. Template versioning and history

**Deliverables:**
- 20+ pre-built templates
- **Support for 1000+ device configurations**
- **Parallel execution with 50-100 concurrent connections**
- Template management API

### Phase 4: Advanced Features & Optimization

**Status:** 💡 Proposed
**Estimated Effort:** 3-4 days

**Tasks:**
1. Multi-vendor template support (Huawei, H3C, Juniper)
2. 🔥 **Intelligent addressing schemes** (sequential, VLAN-based, hierarchical)
3. 🔥 **Configuration summary generation** (pattern analysis for large topologies)
4. Configuration diff and comparison
5. Template analytics and usage statistics
6. 🔥 **Performance optimization** (caching, connection pooling)

**Deliverables:**
- Multi-vendor template ecosystem
- **Optimized for 10,000+ node topologies**
- Advanced configuration management
- Analytics dashboard

---

## Technical Considerations

### Jinja2 Configuration

**Key Settings for Network Configs:**
```
Environment Configuration:
├─ trim_l_blocks=True       # Remove block left whitespace
├─ trim_r_blocks=True       # Remove block right whitespace
├─ lstrip_blocks=True       # Strip leading whitespace
├─ autoescape=False         # Don't escape config commands
└─ Custom Filters
   ├─ to_cidr: Convert IP+mask to CIDR
   ├─ ip_network: Parse IP network
   └─ Wildcard to CIDR conversion
```

**Supported Template Features:**
- Variables: `{{ hostname }}`
- Loops: `{% for interface in interfaces %}...{% endfor %}`
- Conditionals: `{% if ospf_enabled %}...{% endif %}`
- Filters: `{{ ip | to_cidr }}`
- Comments: `{# This is a comment #}`

### Security Considerations

**Template Validation:**
```
┌─────────────────────────────────────────────────────────────┐
│ Template Security Checks                                    │
├─────────────────────────────────────────────────────────────┤
│ 1. Syntax Validation                                        │
│    ├─ Parse Jinja2 syntax                                   │
│    ├─ Check for undefined variables                         │
│    └─ Validate template structure                           │
│                                                              │
│ 2. Sandbox Enforcement                                      │
│    ├─ Disable dangerous built-ins (eval, exec, import)      │
│    ├─ Limit template complexity (max loops, recursion)      │
│    └─ Restrict available filters                            │
│                                                              │
│ 3. Content Security                                         │
│    ├─ Scan for command injection attempts                   │
│    ├─ Validate against forbidden commands list              │
│    └─ Audit logging for all templates                       │
└─────────────────────────────────────────────────────────────┘
```

**Parameter Validation:**
```
Validation Layers:
├─ Type Checking
│  └─ int, str, List[Dict], etc.
├─ Range Validation
│  ├─ IP addresses (valid format)
│  ├─ VLAN IDs (1-4094)
│  └─ Port numbers (1-65535)
├─ Device-Specific Validation
│  └─ Check device capabilities
└─ Business Logic Validation
   └─ Network-specific rules
```

### Error Handling Strategy

**Error Categories:**
```
┌─────────────────────────────────────────────────────────────┐
│ Error Types & Recovery Strategies                           │
├─────────────────────────────────────────────────────────────┤
│ 1. TemplateSyntaxError                                      │
│    ├─ Cause: Invalid Jinja2 syntax                          │
│    ├─ Detection: Pre-rendering validation                   │
│    └─ Recovery: [Show error] → [User fixes] → [Retry]      │
│                                                              │
│ 2. ParameterValidationError                                 │
│    ├─ Cause: Wrong type/value/range                         │
│    ├─ Detection: Pre-execution validation                   │
│    └─ Recovery: [Highlight errors] → [User corrects]        │
│                                                              │
│ 3. RenderingError                                           │
│    ├─ Cause: Runtime rendering failure                      │
│    ├─ Detection: During template render                     │
│    └─ Recovery: [Show context] → [User modifies params]     │
│                                                              │
│ 4. ExecutionError                                           │
│    ├─ Cause: Device connection/command failure              │
│    ├─ Detection: During config execution                    │
│    └─ Recovery: [Retry] → [Skip] → [Continue others]        │
└─────────────────────────────────────────────────────────────┘
```

**Error Response Format:**
```json
{
  "error": "ParameterValidationError",
  "message": "Invalid IP address format for device R1",
  "details": {
    "device": "R1",
    "parameter": "interface.ip",
    "value": "999.999.999.999",
    "expected": "Valid IPv4 address (e.g., 192.168.1.1)"
  },
  "suggestions": [
    "Verify IP address format",
    "Check for typos in address",
    "Ensure address is in correct range"
  ]
}
```

---

## Testing Strategy

### Unit Tests

**Template Rendering Tests:**
```
Test Cases:
├─ Simple Variables
│  └─ Input: "hostname {{ name }}" + {name: "R1"}
│     Output: ["hostname R1"]
│
├─ Loops
│  └─ Input: "{% for n in nets %}network {{ n }}\n{% endfor %}"
│          + {nets: ["192.168.1.0", "192.168.2.0"]}
│     Output: ["network 192.168.1.0", "network 192.168.2.0"]
│
├─ Conditionals
│  └─ Input: "{% if ospf %}router ospf 1\n{% endif %}"
│          + {ospf: true}
│     Output: ["router ospf 1"]
│
└─ Nested Structures
   └─ Input: Complex multi-level config
      Output: Properly indented commands
```

**Rule Engine Tests:**
```
Test Cases:
├─ Device Number Extraction
│  ├─ "R1" → 1
│  ├─ "Router-100" → 100
│  └─ "DeviceX" → fallback to index
│
├─ IP Address Generation
│  ├─ Sequential: 192.168.1.0, 192.168.2.0, ...
│  ├─ VLAN-based: 10.0.100.0, 10.0.101.0, ...
│  └─ Hierarchical: Correct prefix assignment
│
└─ Parameter Validation
   ├─ Type checking
   ├─ Range validation
   └─ Device-specific constraints
```

### Integration Tests

**Full HITL Workflow:**
```
Test Scenario:
┌─────────────────────────────────────────────────────────────┐
│ 1. Template Generation                                      │
│    ├─ Input: "Configure OSPF on 10 routers"                │
│    ├─ Expected: Valid Jinja2 template with schema          │
│    └─ Verify: Template syntax, parameter completeness      │
│                                                              │
│ 2. Parameter Generation (AI mode)                          │
│    ├─ Input: Template + topology context                   │
│    ├─ Expected: 10 device parameter sets                   │
│    └─ Verify: Correct IP assignment, device mapping        │
│                                                              │
│ 3. Parameter Generation (Direct mode)                      │
│    ├─ Input: Template + topology (100 devices)             │
│    ├─ Expected: 100 parameter sets (0 tokens)              │
│    └─ Verify: Rule engine logic, addressing schemes        │
│                                                              │
│ 4. Execution                                                │
│    ├─ Input: Template + parameters                         │
│    ├─ Expected: Successful configuration on all devices    │
│    └─ Verify: Config applied, execution results            │
└─────────────────────────────────────────────────────────────┘
```

### End-to-End Tests

**Large-Scale Topology Test:**
```
Scenario: 1000 Router OSPF Configuration

Setup:
├─ Create GNS3 project with 1000 routers
├─ Deploy in test environment
└─ Verify connectivity

Execution:
├─ Generate template (~150 tokens)
├─ Generate params (rule engine, 0 tokens)
├─ Execute in batches of 100
└─ Monitor progress via SSE

Validation:
├─ Verify all 1000 devices configured
├─ Check OSPF process running on each
├─ Verify IP addressing correctness
├─ Measure execution time (< 8 minutes)
└─ Verify token consumption (~400 total)

Cleanup:
└─ Remove test project
```

**Performance Tests:**
```
Benchmarks:
├─ 10 devices: < 30 seconds
├─ 50 devices: < 1 minute
├─ 100 devices: 1-2 minutes
├─ 500 devices: 2-5 minutes
└─ 1000 devices: 3-8 minutes

Metrics:
├─ Token usage (target: 99%+ reduction)
├─ Execution time (vs. baseline)
├─ Memory usage
└─ Concurrent connection handling
```

---

## Success Metrics

### Token Savings

- **Target:** 70%+ reduction in token usage for multi-device configurations
- **Measurement:** Compare token usage before/after for same tasks

### User Adoption

- **Target:** 60%+ of configuration tasks use template workflow
- **Measurement:** Track tool usage statistics

### Error Reduction

- **Target:** 50%+ reduction in configuration errors
- **Measurement:** Compare error rates before/after HITL

### User Satisfaction

- **Target:** 4.5+ star rating (5-star scale)
- **Measurement:** Post-task user surveys

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| AI generates invalid Jinja2 syntax | High | Add template validation, provide syntax feedback |
| Users find HITL workflow too slow | Medium | Add "quick confirm" option, template reuse |
| Template reuse causes stale configs | Medium | Template versioning, checksum validation |
| Multi-vendor complexity | High | Phase 1: Cisco only, Phase 4: expand |
| Session state management bugs | Medium | Comprehensive testing, state cleanup |

---

## Open Questions

1. **Template Storage:** Should templates be stored per-user or shared globally?
2. **Template Validation:** How strict should template validation be?
3. **Backward Compatibility:** Should existing direct-config tools remain available?
4. **Template Sharing:** Should users be able to share templates in a marketplace?
5. **Performance:** How to handle template rendering for 100+ devices?

---

## Dependencies

### Required Python Packages

```txt
jinja2>=3.1.0
langchain>=0.1.0
langgraph>=0.0.20
```

### Integration Points

- `gns3server/agent/gns3_copilot/tools_v2/config_tools_nornir.py` (existing)
- `gns3server/agent/gns3_copilot/prompts/lab_automation_assistant_prompt.py` (update)
- `gns3server/agent/gns3_copilot/gns3_client/gns3_topology_reader.py` (existing)
- `gns3server/agent/gns3_copilot/utils/command_filter.py` (existing)

---

## Timeline

### Sprint 1: Foundation (Week 1-2)
- Core rendering engine
- Three LangChain tools
- Basic session management
- System prompt updates

### Sprint 2: User Experience (Week 3)
- Review interfaces
- Preview functionality
- Error handling
- Documentation

### Sprint 3: Enhancement (Week 4-5)
- Template library
- Caching mechanisms
- Multi-vendor support
- Testing and QA

### Sprint 4: Polish (Week 6)
- Performance optimization
- Bug fixes
- User feedback integration
- Release preparation

---

## References

- [Jinja2 Documentation](https://jinja.palletsprojects.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Existing Config Tools](../implemented/multi-vendor-device-support.md)
- [Command Security](../implemented/command-security.md)

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-20 | 0.6 | Clarified system scope and positioning - focuses on baseline configuration (0→1), with handoff to production tools (Terraform/REST API/NETCONF) for advanced configuration (1→N) |
| 2026-03-20 | 0.5 | **Major documentation refactor** - Reduced code content by ~60%, added comprehensive diagrams: System architecture, HITL state transitions, API design, data flow, error handling, template lifecycle; Enhanced section on testing strategy; Improved visual documentation |
| 2026-03-20 | 0.4 | Added link creation templates section with topology patterns (Spine-Leaf, Ring, Mesh, Star), intelligent port allocation, performance benchmarks for large-scale connectivity |
| 2026-03-20 | 0.3 | Added node creation templates section with batch topology provisioning, auto-linking, automatic positioning; Combined node creation + configuration workflows for rapid 1000+ node data center deployment |
| 2026-03-20 | 0.2 | Added large-scale topology support section (1000+ nodes), direct execution mode, batch parallel execution, rule engine optimizations |
| 2026-03-20 | 0.1 | Initial roadmap document created |

---

**Document Status:** 💡 Proposed - Awaiting Implementation
**Next Review:** After Phase 1 completion

---

*For questions or feedback about this roadmap, please open an issue or contact the AI Copilot team.*
