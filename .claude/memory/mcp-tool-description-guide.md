---
name: mcp-tool-description-location
description: Where to define MCP tool descriptions so AI can see them
metadata:
  type: reference
---

# MCP Tool Description Location

## Key Point
MCP tool descriptions are defined in `@mcp.tool()` decorator functions in `__init__.py`, NOT in the `*_TOOLS` arrays in individual module files.

## Correct Location
**File**: `gns3server/api/routes/mcp/__init__.py`

**Example**:
```python
@mcp.tool()
async def update_link(
    project_id: Annotated[str, Field(description="UUID of the project")],
    link_id: Annotated[str, Field(description="UUID of the link to update")],
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Update a link's properties.
    
    Put detailed descriptions here, especially for complex parameters.
    Include format requirements, ranges, and examples.
    """
    # implementation
```

## Wrong Location
- ❌ `LINK_TOOLS` in `gns3server/api/routes/mcp/links.py`
- ❌ `TEMPLATE_TOOLS` in `gns3server/api/routes/mcp/templates.py`

## Activation
**Must restart GNS3 server** for description updates to take effect.

## Description Requirements
- Be explicit about data formats (arrays vs single values)
- Include parameter ranges and constraints
- Provide usage examples
- Prevent common errors in the description itself
