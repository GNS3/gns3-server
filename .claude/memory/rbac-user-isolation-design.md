---
name: rbac-user-isolation-design
description: GNS3 RBAC user isolation design and implementation thought process
metadata:
  type: project
---

## RBAC User Isolation Design Summary

### Core Problem
GNS3 3.0 has a complete RBAC framework (ACE + Role + Privilege), but lacks user isolation implementation, causing users to see resources they shouldn't have access to.

### Design Conflict
Traditional RBAC's **path permission model** fundamentally conflicts with **user data isolation**:
- **Path permission model**: Controls which paths users can access (e.g., `/projects`)
- **User data isolation**: Controls which specific resources users can access (e.g., alice's project vs bob's project)

### Final Implementation Approach

#### Three-Step Permission Check Logic

```python
# Step 1: Batch ACE + resource pool check (3 DB queries regardless of project count)
direct_ace_ids, pool_accessible_ids = await rbac_repo.get_accessible_project_ids(
    current_user.user_id, "Project.Audit", all_project_ids
)

# Step 2: Filter direct ACE projects by created_by (user's own projects)
# Direct project sharing is only available through resource pools
for p in controller.projects.values():
    if p.id in direct_ace_ids and p.created_by == current_user.username:
        projects.append(p.asdict())

# Step 3: Resource pool projects (no created_by filter)
for p in controller.projects.values():
    if p.id in pool_accessible_ids:
        projects.append(p.asdict())
```

##### Super Admin Bypass
```python
if current_user.is_superadmin:
    return [p.asdict() for p in controller.projects.values()]
```
Super admins skip all three steps and see every project.

##### seen_project_ids Deduplication
A simple `seen_project_ids` set prevents the same project from appearing twice when it exists in both direct ACE and pool results. This is a lightweight dedup, not the complex blocking mechanism from earlier rejected designs.

### Key Design Decisions

#### 1. ACE vs created_by Relationship
- **ACE for basic access control**: Whether user can access the system
- **created_by for user isolation**: Which specific resources user can access
- **Step 2 filtering is critical**: Even with broad ACE, created_by filtering ensures user isolation

#### 2. Project Sharing Mechanism
- **Project sharing only through resource pools**: Cannot configure ACE directly for specific projects
- **Avoids complexity of direct ACE sharing**: Prevents permission configuration chaos

#### 3. Broad ACE Fault Tolerance
```
Even with configuration: ACE: Users group + User role + "/" + propagate: True
Result: Users still only see projects they created
Reason: Step 2 created_by filtering removes other users' projects
```

### RbacRepository.get_accessible_project_ids()

The core batch-check method in `gns3server/db/repositories/rbac.py` uses 3 DB queries:

1. **User ACEs**: Direct ACE entries matching user + privilege
2. **Group ACEs**: Group-level ACE entries via `UserGroup` membership
3. **All resources with pool memberships**: Preloads all resources and their pool relationships

Then it computes two sets:
- **`direct_ace_ids`**: Project paths matching user or group ACEs (path-based check)
- **`pool_accessible_ids`**: Projects in pools the user/group can access (pool-based check)

Pool IDs are precomputed into a `pool_id -> set(project_ids)` map for O(1) lookup.

### Problems Solved

#### Problem 1: Missing User Isolation
- **Issue**: All users can see all projects
- **Solution**: Filter by created_by to implement user isolation

#### Problem 2: Broad ACE Breaking Isolation
- **Issue**: `path: "/" + propagate: true` breaks user isolation
- **Solution**: Step 2 created_by filtering ensures user isolation even with broad ACE

#### Problem 3: Permission Check Order Conflicts
- **Issue**: seen mechanism blocks subsequent checks (from earlier design phases)
- **Solution**: Simple pipeline-style filtering with lightweight dedup set

### Technical Details

#### API Layer Permission Check
```python
@router.get("/projects")  # Note: no has_privilege decorator
async def get_projects(current_user=..., rbac_repo=...):
    # Permission checks in business logic
```

#### Duplicate Prevention
- Simple `seen_project_ids` set for deduplication between direct ACE and pool results
- Not the complex blocking mechanism from earlier phases

#### Performance Considerations
- Super admin path: O(1) — returns all projects directly
- Regular user path: 3 fixed DB queries regardless of project count
- Path-based ACE check: O(n * m) in worst case, where n = projects, m = ACE entries
- Pool lookup: O(1) via precomputed pool->project map

### Use Cases

#### Scenario 1: Personal Use
```
alice creates project → alice only sees alice's projects ✅
bob creates project → bob only sees bob's projects ✅
No extra configuration needed, automatic user isolation
```

#### Scenario 2: Team Collaboration
```
Admin creates resource pool → adds projects → team members can access
alice creates project → alice still sees her own projects ✅
Team sharing + user isolation coexist
```

#### Scenario 3: Broad ACE Configuration
```
ACE: Users group + "/" + propagate: True
alice still only sees alice's projects ✅
User isolation unaffected by ACE configuration
```

### Design Principles

#### 1. Separation of Concerns
- **Basic access permission**: Controlled by ACE
- **Data ownership**: Controlled by created_by
- **Team sharing**: Controlled by resource pools

#### 2. Defensive Design
- User isolation remains effective even with improper ACE configuration
- Secure by default: users only see their own resources

#### 3. Simplicity
- Avoid complex seen mechanisms and mutual exclusion logic
- Clear pipeline-style check order

### Relationship with Original ACE System

#### Preserved Components
- ✅ ACE framework (permission check mechanism)
- ✅ Role and privilege definitions
- ✅ Resource pool functionality

#### Improved Components
- ✅ Added user isolation (created_by filtering)
- ✅ Clarified project sharing mechanism (only through resource pools)
- ✅ Simplified permission check logic

#### Removed Components
- ❌ Removed `/projects` path privilege check on `get_projects` route
- ❌ Removed the old complex `seen_project_ids` blocking mechanism
- ❌ Avoided "can see all non-pool projects" privilege leak

### Implementation Details
- **Main modification**: `gns3server/api/routes/controller/projects.py`
- **Function**: `get_projects()`
- **Batch check method**: `gns3server/db/repositories/rbac.py::RbacRepository.get_accessible_project_ids()`
- **Privilege dependency**: `gns3server/api/routes/controller/dependencies/rbac.py::has_privilege()`
- **Branch**: `feature/simple-user-isolation`
- **Base branch**: `master`

### Key Commits
1. Implemented basic created_by filtering
2. Implemented three-layer permission check (with logic issues)
3. Fixed to correct three-step check logic

### Design Evolution Process

#### Phase 1: Simple created_by Filtering
```python
user_projects = [p for p in all_projects() if p.created_by == user.username]
```
**Issue**: Didn't integrate with ACE system

#### Phase 2: Three-Layer Check (Wrong Version)
```python
# Used complex seen_project_ids blocking mechanism
# Issue: Broad ACE breaks user isolation
```

#### Phase 3: Three-Step Check (Correct Version)
```python
# Step 1: Batch ACE check via get_accessible_project_ids()
# Step 2: Filter direct_ace_ids by created_by
# Step 3: Resource pool projects (no created_by filter)
```
**Solution**: User isolation works even with broad ACE

### Relationship with RBAC Roadmap
This implementation addresses items mentioned in the roadmap:
- **Phase 1 (MVP)**: Basic project isolation implementation
- **Auto-ACE on create**: Still needs to be implemented separately
- **Template isolation**: Can use same design pattern

### Unsolved Issues

1. **Auto-ACE on project creation**: Part of roadmap Phase 1 — `create_project()` sets `created_by` but doesn't create ACE entries
2. **Template and image isolation**: Can apply same design pattern
3. **Default ACE configuration**: Need reasonable default permissions for Users group

### Design Limitations

1. **Project sharing only through resource pools**: No direct ACE configuration for sharing
2. **ACE configuration required**: Users need basic ACE to access system
3. **Performance considerations**: ACE check queries database for each project path

### Future Improvement Directions

1. **Auto-create ACE**: Automatically add ACE for creator when creating projects
2. **Default ACE strategy**: Configure reasonable default permissions for Users group
3. **Performance optimization**: Cache ACE check results to reduce database queries

This design achieves effective user isolation while maintaining RBAC system integrity, and solves the problem of broad ACE configurations breaking isolation.

**Key insight**: The Step 2 created_by filtering is the critical innovation that allows ACE and user isolation to coexist properly.
