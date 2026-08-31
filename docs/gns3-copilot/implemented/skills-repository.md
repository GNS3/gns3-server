<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is organized by AI with reference to actual code. AI can make mistakes — please verify against the source code when in doubt.


# External Skills Repository

## Overview

GNS3 Copilot loads all skills, prompts, and security configurations from an external Git repository at [github.com/gns3/gns3-skills](https://github.com/gns3/gns3-skills). This enables dynamic updates without server redeployment.

The repository provides:
- **Injection skills** (39 categories): Network fault scenarios for troubleshooting practice
- **Device skills**: Device-specific command knowledge (VPCS, etc.) — large devices split into per-protocol **topics**
- **Feature skills**: Topology planning, network design
- **System prompts**: Agent personality and behavior definitions
- **Forbidden commands**: Security rules for command filtering

## Architecture

```mermaid
graph TD
    subgraph "GNS3-Skills Repository"
        YAML[injection/*.yaml<br/>device/*.yaml + device/*/*.yaml<br/>feature/*.yaml]
        MD[prompts/*.md]
        CFG[config/forbidden_commands.txt]
    end

    subgraph "GNS3 Server"
        SM[SkillsManager]
        SL[SkillsLoader]
        REG[Registry<br/>SKILLS_REGISTRY<br/>INJECTION_SKILLS_REGISTRY]
        PROMPT[PROMPTS_CACHE]
        FC[command_filter]
    end

    YAML --> SL
    MD --> SL
    CFG --> FC
    SL --> REG
    SL --> PROMPT
    SM --> SL
    SM -->|git pull| YAML
```

## Repository Structure

```
GNS3-Skills/
├── injection/          # 39 YAML files, one per protocol/category
│   ├── ospf_issues.yaml
│   ├── bgp_issues.yaml
│   ├── vlan_issues.yaml
│   └── ...
├── device/             # Device-specific skills
│   ├── vpcs.yaml           # small devices: one single file
│   └── frr/                # large devices: split per protocol topic
│       ├── _base.yaml      # device-level skill (console model, notes, aliases)
│       ├── ospf.yaml       # topic file (merged under "topics" at load time)
│       └── bgp.yaml
├── feature/            # Feature skills
│   └── topology_planner.yaml
├── prompts/            # System prompts (Markdown)
│   ├── teaching_assistant.md
│   ├── lab_automation_assistant.md
│   ├── troubleshooting_injection.md
│   └── title.md
└── config/             # Security configuration
    └── forbidden_commands.txt
```

## Device Topics

A device with knowledge for many protocols would grow one YAML file indefinitely. Such devices use a split layout instead: `device/<device>/_base.yaml` holds the device-level skill, and one file per protocol topic (`ospf.yaml`, `bgp.yaml`, ...) holds its commands and troubleshooting entries. The loader merges them into a single `SKILLS_REGISTRY` entry:

```
SKILLS_REGISTRY["frr_vtysh"] = { ..._base.yaml..., "topics": { "ospf": {...}, "bgp": {...} } }
```

Topic files must declare `device_type` (matching their `_base.yaml`), `topic` and `name`; the CI validator in the skills repository enforces this.

The `device_skills` tool exposes a three-step drill-down (mirroring `injection_skills`'s list → index → issue pattern):

```json
{"action": "list"}
{"device_type": "frr_vtysh", "detail": "index"}
{"device_type": "frr_vtysh", "topic": "bgp"}
```

Topic bodies are only served on an explicit `topic` request — every other detail level returns a topic index — so adding topics to a device does not grow the token cost of device-level lookups.

## Configuration

Skills repository settings are configured in `gns3_server.conf` under the `[Server]` section:

```ini
[Server]
skills_repo_url = https://github.com/gns3/gns3-skills.git
skills_repo_branch = main
skills_auto_update = true
```

| Setting | Default | Description |
|---------|---------|-------------|
| `skills_repo_url` | `https://github.com/gns3/gns3-skills.git` | Git repository URL |
| `skills_repo_branch` | `main` | Git branch to track |
| `skills_auto_update` | `true` | Automatically pull on reload |

## Initialization Flow

```mermaid
sequenceDiagram
    participant Server
    participant agent/__init__.py
    participant SkillsManager
    participant Git

    Server->>agent/__init__.py: Import module
    agent/__init__.py->>SkillsManager: Start background init thread
    Note over SkillsManager: Thread.join(5s timeout)

    SkillsManager->>Git: Check local repo exists?
    alt No local repo
        Git->>SkillsManager: git clone (with timeout env)
    else Local repo exists
        SkillsManager->>Git: Check uncommitted changes?
        alt Has uncommitted changes
            Git-->>SkillsManager: Warn, skip pull
        else No changes
            SkillsManager->>Git: git fetch (timeout 10s)
            SkillsManager->>Git: Behind remote?
            alt Behind
                Git->>SkillsManager: git pull
            else Up to date
                Git-->>SkillsManager: Nothing to do
            end
        end
    end

    SkillsManager->>SkillsManager: reload_skills() - load YAML files
    SkillsManager->>SkillsManager: reload_prompts() - load Markdown files
```

### Git Timeout Configuration

Git operations use per-command environment variables to prevent hanging:

```python
_GIT_TIMEOUT_ENV = {
    'GIT_HTTP_TIMEOUT': '10',           # Connection timeout (default: 120s)
    'GIT_HTTP_LOW_SPEED_TIME': '5',     # Slow speed threshold window
    'GIT_HTTP_LOW_SPEED_LIMIT': '1000', # < 1 KB/s = slow → abort
}
```

These apply only to the specific `clone`/`fetch`/`pull` subprocess, not to the global environment.

## API Endpoint

### POST /copilot/reload/skills

Triggers a full reload of the skills repository. Performs one git update check, then reloads all skills, prompts, and forbidden commands from local files.

**Response:**

```json
{
  "success": true,
  "skills": true,
  "skill_count": 39,
  "prompts": true,
  "prompt_count": 4,
  "forbidden_commands": 6,
  "version": "abc123def456..."
}
```

| Field | Description |
|-------|-------------|
| `success` | Overall success (true if skills or prompts loaded) |
| `skills` | Skills reload result |
| `skill_count` | Number of injection skills loaded |
| `prompts` | Prompts reload result |
| `prompt_count` | Number of prompts loaded |
| `forbidden_commands` | Number of forbidden command patterns |
| `version` | Git commit hash of the repository |

## Related Documentation

- [Fault Injection](fault-injection.md)
- [Command Security](command-security.md)
- [Chat API](chat-api.md)
