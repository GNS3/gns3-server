---
name: gns3-api-test-writing
description: Use this skill when writing pytest tests for gns3-server API routes — the conftest fixture model, auth token variants, config isolation, and the shared-client order-dependency trap.
version: 1.0.0
---

# Writing pytest API Route Tests

## Test Environment

- Run tests with the repo venv: `venv/bin/python -m pytest tests/api/routes/controller/test_xxx.py` (there is no system python/pytest).
- The app runs in-process (httpx `ASGIWebSocketTransport`); the database is in-memory sqlite; superadmin `admin` is seeded when the users table is created.
- `pytestmark = pytest.mark.asyncio`. Tests run on function-scoped event loops while class-scoped fixtures bind to the class loop — this works, but don't move class fixtures to function scope casually.

## The Fixture Model (tests/conftest.py)

Class-scoped: `app`, `db_session`, `base_client` (**one** shared httpx `AsyncClient`), `test_user` (idempotent `user1` in the "Users" group).

`client` (admin), `authorized_client` (user1), `unauthorized_client`, `compute_client` are class-scoped wrappers that each **rewrite the shared `base_client.headers` at instantiation time**. They are instantiated lazily — by the first test that requests them.

### The order-dependency trap

- `unauthorized_client` is a passthrough: it sets no header and only behaves as "unauthorized" if nothing set a token on `base_client` before it.
- Mixing auth variants in one test class makes the default `Authorization` header depend on fixture instantiation order → tests pass alone but fail in a class run (or the reverse).
- Symptom signature: a 401/403 assertion receives 200. That is fixture pollution, **not** an RBAC/auth bug in the product.

### Rule: per-request headers for auth variants

Never rely on the client's default header for 401/403/specific-user tests. Send the token explicitly (request-level headers override client defaults — the `test_users.py` idiom):

```python
from gns3server.services import auth_service
from gns3server.services.authentication import DEFAULT_JWT_SECRET_KEY

token = auth_service.create_access_token(test_user.username, secret_key=DEFAULT_JWT_SECRET_KEY)
response = await client.get(url, headers={"Authorization": f"Bearer {token}"})      # specific user
response = await client.get(url, headers={"Authorization": "Bearer invalid_token"})  # 401
```

Note the import: `auth_service` lives in `gns3server.services`, NOT `gns3server.services.authentication` (which only exports `DEFAULT_JWT_SECRET_KEY` and the class).

Always pass `secret_key=DEFAULT_JWT_SECRET_KEY`: the autouse `run_around_tests` resets `Config` per test and forces the default secret, so a token minted with the config-of-the-moment dies in the next test.

## Config-Isolated Tests

- Request the function-scoped `config` fixture whenever the test reads/writes configuration or the endpoint under test reloads it. It points `Config` at `tmpdir/server.conf` (accessible as `config._main_config_file`).
- Any endpoint that triggers a config reload re-reads `<secrets_dir>/gns3_jwt_secret_key`, which invalidates class-scoped bearer tokens. Fix: write `DEFAULT_JWT_SECRET_KEY` to that file first — see the `stable_jwt_secret` fixture in `tests/api/routes/controller/test_settings.py`.

## Misc Gotchas

- Build URLs with `app.url_path_for("route_function_name")`. Router introspection is unreliable (lazy `_IncludedRouter` wrapper) — check `GET /openapi.json` instead.
- pydantic v2: an empty `SecretStr('')` serializes as `""`, **not** the mask — assert `in ("", SECRET_MASK)` for secrets that may be unset in tests.
- New privileges are seeded only at table creation (`gns3server/db/models/privileges.py`); the fresh in-memory test DB always has them, but existing deployments need manual grants.
- Error mapping: `ControllerBadRequestError` → 400, `ControllerError`/`HTTPException(409)` → 409, request schema violations → 422.

## Failure-Diagnosis Heuristic

**Passes in isolation, fails in a class run → suspect shared fixture state first** (`base_client.headers`, the `Config` singleton, class-scoped DB rows) — never the product code. Reproduce with `-k "test_a or test_b"` pairs to find the polluting test. Do not add debug prints to product code to chase test-order issues; make the test order-independent with explicit per-request headers instead.
