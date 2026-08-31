# Python Import Validation

## Background

When checking if modified Python code is correct, `py_compile` only validates syntax (e.g., balanced parentheses, valid keywords). It does **not** catch missing imports or other runtime errors (e.g., using `UUID()` without importing `UUID`).

## Decision/Implementation

Use actual module imports to verify code correctness:

```bash
# ✅ This catches missing imports and runtime errors
venv/bin/python -c "
from gns3server.api.routes.controller.dependencies.authentication import get_user_from_token
from gns3server.api.routes.mcp.__init__ import _resolve_token
print('All imports OK')
"

# ❌ This only checks syntax, not references
venv/bin/python -c "import py_compile; py_compile.compile('file.py', doraise=True)"
```

## Related Files

`gns3server/api/routes/controller/dependencies/authentication.py` — missed `from uuid import UUID`
`gns3server/api/routes/mcp/__init__.py` — missed `from uuid import UUID`

## Why

A `NameError` at runtime is far more expensive than a failed import check. Real import testing catches the full dependency chain.
