---
name: memory
description: This skill should be used when the user asks to "record memory", "save to memory", "remember this", "create a memory", "add to memory", or discusses documenting technical decisions, architectural choices, or important case studies for the project. Use this skill to record project knowledge to the .claude/memory/ directory.
version: 1.0.0
---

# Memory Skill

## Overview

Record project-related technical decisions, important case studies, and lessons learned to the project memory directory, ensuring critical knowledge is managed with the code repository.

## When This Skill Activates

Activate this skill when user requests involve:
- "Record to memory", "save to memory", "add to memory"
- "Remember this", "create a memory"
- Documenting technical decisions, architectural choices
- Recording problem solutions and lessons learned
- Discussing API design, performance optimization, security implementations

## Memory Location

Project memory is stored in: `.claude/memory/`

## Memory Structure

```
.claude/
├── memory/
│   ├── MEMORY.md          # Main index file
│   └── <topic>.md         # Detailed records for specific topics
└── skills/
    └── memory/
        └── SKILL.md       # This file
```

## What to Record

### ✅ Should Record

- Important architectural decisions and rationale
- Solutions to complex problems
- Key considerations for API design
- Performance optimization experiences
- Security-related implementation details
- Integration approaches with other systems
- Common errors and solutions
- Design changes based on user feedback

### ❌ Should Not Record

- Temporary debugging information
- Session-specific state
- Obvious code implementation details (code is documentation)
- Content already documented elsewhere

## Memory Template

```markdown
# <Topic Title>

## Background
<Why this record exists>

## Decision/Implementation
<What was done or how it was implemented>

## Rationale
<Why this approach was chosen, what alternatives were considered>

## Related Files
<Code files involved, use file_path:line_number format>

## Examples
<If there are code examples or other examples>
```

## Recording Process

1. **Identify content to record**
2. **Determine topic title** (concise, descriptive)
3. **Create record using template**
4. **Update MEMORY.md index**
5. **Save to .claude/memory/<topic>.md**

## Examples

- `web-wireshark-jwt-token-flow.md` - JWT token flow in Web Wireshark integration
- `docker-api-version-detection.md` - Docker API version dynamic detection implementation

## Best Practices

- Use clear, descriptive filenames
- Include references to related code files (with line numbers)
- Document "why" not just "what"
- Keep records updated, remove outdated ones
- Link to related memory files
