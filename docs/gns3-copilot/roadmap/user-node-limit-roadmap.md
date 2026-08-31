# User Node Limit Roadmap

## Overview

Implement a user-level node startup limit feature for GNS3 server to prevent single users from consuming excessive system resources. This feature is **disabled by default** and can be enabled through configuration files, supporting a three-tier configuration priority system.

## Problem Statement

Currently, GNS3 server has no mechanism to limit the number of nodes a user can start across all their projects. This can lead to:

- **Resource exhaustion**: A single user can consume all available system resources
- **Unfair usage**: Some users may prevent others from using the system
- **System instability**: Too many running nodes can degrade overall performance
- **Cost issues**: In cloud environments, this can lead to unexpected costs

## Solution Design

### Core Principles

1. **Default to no limits**: System maintains backward compatibility by defaulting to unrestricted usage
2. **Configuration-driven**: All limits can be controlled through configuration files
3. **Multi-tier priority**: User-specific > User group-specific > Global configuration
4. **Intelligent filtering**: Only count nodes that actually consume resources
5. **Clear error messages**: Users receive actionable feedback when limits are reached

### Technical Architecture

#### 1. Database Layer Extension

**Files**: `gns3server/db/models/users.py`

Add `max_nodes` field to both `User` and `UserGroup` models:

```python
# In User model
max_nodes = Column(Integer, nullable=True)  # NULL = no limit

# In UserGroup model  
max_nodes = Column(Integer, nullable=True)  # NULL = no limit
```

#### 2. Configuration System Extension

**File**: `gns3server/schemas/config.py`

Add node limit configuration to `ControllerSettings`:

```python
class NodeLimitSettings(BaseModel):
    enabled: bool = False  # Feature toggle (default disabled)
    default_max_nodes: int = 5  # Default limit when enabled
    excluded_node_types: List[str] = Field(default_factory=lambda: [
        "ethernet_switch", "ethernet_hub", "cloud", "nat"
    ])
```

#### 3. Core Service Implementation

**New File**: `gns3server/services/node_limit_service.py`

Implement the `NodeLimitService` class with key methods:

```python
class NodeLimitService:
    async def get_user_active_node_count(self, username: str, excluded_types: List[str]) -> int:
        """Count user's active nodes across all projects"""
        
    async def get_user_node_limit(self, user: User) -> Optional[int]:
        """Get user's node limit with priority logic"""
        
    async def check_user_node_limit(self, user: User, project: Project) -> Tuple[bool, str]:
        """Check if user can start more nodes"""
```

#### 4. API Integration

**File**: `gns3server/api/routes/controller/nodes.py`

Add limit checking to node startup endpoint:

```python
@router.post("/{node_id}/start")
async def start_node(
    node: Node = Depends(dep_node),
    current_user: User = Depends(get_current_active_user),
    node_limit_service: NodeLimitService = Depends(get_node_limit_service)
):
    # Node limit check
    can_start, error_msg = await node_limit_service.check_user_node_limit(
        current_user, node.project
    )
    if not can_start:
        raise HTTPException(status_code=403, detail=error_msg)
    
    # Original startup logic
    await node.start()
```

### Node Counting Logic

#### What Counts Toward the Limit

- **Status**: Only nodes in `started` or `suspended` state
- **Ownership**: Only projects where `project.created_by == current_user.username`
- **Node types**: All node types except those explicitly excluded

#### What's Excluded from the Limit

- **Always-running nodes**: Ethernet switches, hubs (nodes where `is_always_running()` returns true)
- **Infrastructure nodes**: Cloud nodes and NAT nodes
- **Stopped nodes**: Nodes in `stopped` state
- **Other users' projects**: Nodes in projects created by other users

#### Configuration Priority

```
User-specific limit (highest priority)
    ↓ not set
User group limit
    ↓ not set  
Global configuration (if enabled)
    ↓ disabled
No limit (default)
```

### Configuration Examples

#### Scenario 1: Default No Limits (System Default)

```ini
[Controller]
node_limits_enabled = false
```

**Result**: All users have no node limits

#### Scenario 2: Enable Global Limits

```ini
[Controller]
node_limits_enabled = true
node_limits_default_max_nodes = 5
node_limits_excluded_types = ethernet_switch,ethernet_hub,cloud,nat
```

**Result**: All users limited to 5 active nodes (excluding infrastructure nodes)

#### Scenario 3: User-Specific Limits

Configuration file: `node_limits_enabled = false`

Database:
- User A: `max_nodes = 10` (limited to 10 nodes)
- User B: `max_nodes = NULL` (no limit)
- Other users: no limit

#### Scenario 4: User Group Limits

Configuration file: `node_limits_enabled = false`

Database:
- "Users" group: `max_nodes = 5`
- "Premium Users" group: `max_nodes = 20`
- "Administrators" group: `max_nodes = NULL`

**Result**: Members inherit limits from their groups

## Implementation Files

| File Path | Type | Description |
|-----------|------|-------------|
| `gns3server/db/models/users.py` | Modify | Add `max_nodes` field to User and UserGroup |
| `gns3server/db_migrations/versions/xxx_add_node_limits.py` | New | Database migration script |
| `gns3server/schemas/config.py` | Modify | Add NodeLimitSettings configuration class |
| `gns3server/schemas/controller/users.py` | Modify | Add `max_nodes` to API schemas |
| `gns3server/services/node_limit_service.py` | New | Core node limit service |
| `gns3server/api/routes/controller/nodes.py` | Modify | Add limit check to node startup |
| `gns3server/api/routes/controller/users.py` | Modify | Add user limit configuration API |
| `gns3server/api/routes/controller/groups.py` | Modify | Add group limit configuration API |

## Implementation Steps

### Phase 1: Database Layer
1. Add `max_nodes` field to `User` and `UserGroup` models
2. Create database migration file
3. Test database migration and rollback

### Phase 2: Configuration System
1. Add `NodeLimitSettings` to configuration schema
2. Update configuration file loading logic
3. Test configuration parsing and validation

### Phase 3: Core Service
1. Implement `NodeLimitService` class
2. Implement node counting logic
3. Implement limit checking logic
4. Add unit tests for service methods

### Phase 4: API Integration
1. Modify node startup endpoint to add limit check
2. Add user limit configuration endpoints
3. Add group limit configuration endpoints
4. Add user node usage statistics endpoint

### Phase 5: Testing
1. Unit tests for all core functions
2. Integration tests for API endpoints
3. End-to-end tests for complete workflows
4. Performance tests for node counting operations

## Testing Strategy

### Functional Tests
- [ ] Default state verification (no limits)
- [ ] Global limit enablement
- [ ] User-specific limits
- [ ] User group limits
- [ ] Configuration priority verification

### Boundary Tests
- [ ] Exactly at limit (can start last node)
- [ ] One over limit (startup rejected)
- [ ] Stop node then restart (should work)
- [ ] Special node type exclusion

### Integration Tests
- [ ] Multi-user concurrent startups
- [ ] Node state transitions
- [ ] Dynamic configuration changes
- [ ] Project ownership filtering

### Performance Tests
- [ ] Node counting performance with many projects
- [ ] Concurrent startup request handling
- [ ] Memory usage monitoring

## Error Messages

### User-Friendly Error Response

When a user hits their node limit:

```json
{
  "detail": "节点启动限制：您当前有 5 个活跃节点，限制为 5 个。请停止一些节点后再试，或联系管理员调整限制。"
}
```

Alternative formats:
- Show current usage vs limit
- Provide action suggestions
- Include contact information for administrators

## Migration Path

### For Existing Systems

1. **Database migration**: Add new nullable fields (safe, no data loss)
2. **Configuration update**: Add new optional settings (backward compatible)
3. **API changes**: Add new optional dependency injection (no breaking changes)
4. **Behavior**: No changes to existing functionality when disabled

### Rollback Plan

If issues occur:
1. Set `node_limits_enabled = false` in configuration
2. Service automatically disables limit checking
3. System returns to pre-feature behavior

## Benefits

1. **Resource Management**: Prevent resource exhaustion
2. **Fair Usage**: Ensure equitable resource distribution
3. **Cost Control**: Manage cloud resource costs
4. **System Stability**: Maintain performance under load
5. **Flexibility**: Support different usage patterns and tiers
6. **Backward Compatible**: No impact on existing deployments

## Future Enhancements

- Per-project limits (in addition to global user limits)
- Time-based limits (different limits for different times)
- Burst limits (temporary allowance for peak usage)
- Usage quotas with reset periods (daily/weekly/monthly)
- Monitoring and alerting for limit approaching
- Administrative override capabilities
- Usage history and analytics

## Documentation Updates

- [ ] Update API documentation with new endpoints
- [ ] Add configuration guide to admin documentation
- [ ] Update user guide with limit information
- [ ] Add troubleshooting section for limit issues
- [ ] Provide migration guide for existing deployments

## Status

**Current Status**: Design Phase

**Next Steps**:
1. Review and approve this roadmap
2. Begin Phase 1 implementation (Database Layer)
3. Create detailed technical specification
4. Set up development and testing environment

---

**Document Version**: 1.0  
**Last Updated**: 2026-05-27  
**Author**: GNS3 Development Team