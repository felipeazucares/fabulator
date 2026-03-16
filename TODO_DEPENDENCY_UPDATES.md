# Dependency Update Tasks

Last Updated: 2026-03-16

## Status Summary

✅ **Environment:** Fresh venv with Python 3.9.6, all dependencies updated to 2024/2025 versions
✅ **Critical Fixes:** pytz→zoneinfo (api.py), httpx API update (test file)
✅ **Issue 1 (Database None Handling):** Fixed — `get_tree_for_account()` now checks `number_of_saves_for_account() > 0` before loading; returns empty `Tree()` for new users
✅ **Issue 2 (Redis Event Loop):** Fixed — lazy connection via `_get_redis_connection()`, connections properly closed with `await conn.aclose()`
✅ **Test Suite:** 113 tests collected, 103 passed, 10 skipped, 0 failed
✅ **Scope Tests:** Refactored — only test insufficient permissions (403), skip when token has sufficient scope
✅ **Isolation Tests:** 7 tests renamed from `test_scope_*` to `test_isolation_*`, verify cross-user data isolation (404)
✅ **Security Fix:** `/loads/{save_id}` now verifies account ownership via `check_if_document_exists(save_id, account_id)`
✅ **CORS Fix (2026-03-15):** Origins now read from `CORS_ORIGINS` env var; methods restricted to GET/POST/PUT/DELETE; headers restricted to Authorization/Content-Type
✅ **Exception Handling (2026-03-15):** All `except Exception` catches replaced — 0 remaining in both `database.py` and `api.py`
✅ **ConsoleDisplay (2026-03-15):** 23 per-method instantiations removed in `database.py`; module-level instance used throughout
✅ **Rate Limiting (2026-03-15):** SlowAPI on `/get_token`; `LOGIN_RATE_LIMIT` env var (default `5/minute`); set higher in test env
✅ **DB Connection Pooling (2026-03-16):** Single `AsyncIOMotorClient` created in FastAPI lifespan, stored on `app.state`, injected via `Depends()` — PR #12
✅ **Input Validation (2026-03-16):** UUID pattern on all `id` path params and `parent` body fields; length/tag constraints via Pydantic `Annotated` types — PR #13
✅ **Tree Depth Limit (2026-03-16):** `MAX_TREE_DEPTH` env var (default 100); `TreeDepthLimitExceeded` exception; depth tracked through `add_a_node()` recursion — PR #14
✅ **Structured Logging (2026-03-16):** `ConsoleDisplay` replaced with Python `logging` module via `get_logger()` factory in `helpers.py`; `config.py` simplified — PR #16
✅ **Exception Leaking (2026-03-16):** All `HTTPException` detail strings that embedded `{e}` replaced with generic user-facing messages; full details in `logger.error(..., exc_info=True)` — PR #16
✅ **Unit Tests (2026-03-16):** `server/tests/test_unit.py` — 43 tests covering model validation, auth helpers, tree operations; no live DB required — PR #16
✅ **README (2026-03-16):** Added `README.md` at repo root with setup, env vars, run/test instructions, API reference — PR #16
✅ **Self-Assignment Refactor 4.5 (2026-03-16):** 71 `self.x = param` assignments removed from 22 methods in `database.py`; local variables throughout; eliminates concurrency risk in recursive `add_a_node()` — PR #17

---

## Resolved Issues

### Issue 1: Database None Handling (Fixed 2026-02-09)
**Error:** `'NoneType' object is not subscriptable`

**Root Cause:** New users had no saved trees. `load_latest_into_working_tree()` returned None, and code tried to subscript it.

**Fix:** `get_tree_for_account()` in `api.py:167` now checks `number_of_saves_for_account() > 0` before loading. Returns empty `Tree()` for accounts with no saves.

---

### Issue 2: Redis Event Loop Lifecycle (Fixed 2026-02-09)
**Error:** `RuntimeError: Event loop is closed`

**Root Cause:** Redis connection created eagerly in `Authentication.__init__`, became stale across async contexts.

**Fix:** Lazy connection via `_get_redis_connection()` in `authentication.py`. Each operation gets a fresh connection and closes it with `await conn.aclose()`.

---

## Completed Work (2026-02-09)

### Isolation Test Refactor
- Renamed 7 tests from `test_scope_*` to `test_isolation_*` (they tested cross-user data access, not scope permissions)
- Created `return_isolation_token` fixture (full permissions, separate user)
- Fixed security bug: `/loads/{save_id}` now checks account ownership
- PR #3 merged

### Scope Test Refactor
- All 10 scope tests now only test insufficient permissions (403)
- Added `pytest.skip()` when token has the required scope
- Removed fragile happy-path `if` branches
- PR #3 merged

### Documentation
- Added `quickread.md` — concise guide to tree data model and CRUD operations (PR #5 merged)
- Updated `CLAUDE.md` with current project state (PR #4 merged)

---

## Completed Work (2026-03-15)

### Security & Code Quality Sprint
- **CORS:** `CORS_ORIGINS` env var required at startup; explicit methods/headers list
- **Exception handling:** Replaced all 29 `except Exception` in `api.py` with `pymongo.errors.PyMongoError`, treelib-specific exceptions, `KeyError`/`ValueError` as appropriate. `database.py` was already clean.
- **ConsoleDisplay:** Removed 23 per-method `ConsoleDisplay()` instantiations in `database.py`. Fixed latent `AttributeError` in `update_user_details/password/type` else branches. Eliminated per-recursive-call instantiation in `add_a_node()`.
- **Rate limiting:** SlowAPI + existing Redis backend on `/get_token`. `LOGIN_RATE_LIMIT` env var (default `5/minute`). Add `LOGIN_RATE_LIMIT=1000/minute` to test `.env`.
- **New deps:** `slowapi==0.1.9`, `limits[redis]>=3.6.0` added to `requirements.txt`

---

## Completed Work (2026-03-16)

### DB Connection Pooling (H4) — PR #12
- Single `AsyncIOMotorClient` created once in FastAPI lifespan context manager
- Client stored on `app.state.motor_client`, injected into `TreeStorage`/`UserStorage` via `Depends()`
- `Authentication.set_client()` called from lifespan to wire the shared client
- Test infrastructure: `autouse=True` `setup_app_state` fixture manually sets `app.state` since `ASGITransport` does not trigger the FastAPI lifespan

### Input Validation (H5) — PR #13
- `UUID_PATTERN`, `NODE_NAME_MAX_LEN`, and field length constants added to `models.py`
- `Annotated` type aliases (`UuidStr`, `NodeNameStr`, `DescriptionStr`, `TextStr`, `LinkStr`) used throughout request schemas
- `Path(pattern=UUID_PATTERN)` on all `id` path params; `Path(min_length=1, max_length=NODE_NAME_MAX_LEN)` on `POST /nodes/{name}`
- `parent` body field validated as UUID; `previous`/`next` validated as `LinkStr` (free-text, not UUID)
- Tags validated: max 50 items, max 100 chars each, no empty/whitespace strings

### Tree Depth Limit (M2) — PR #14
- `MAX_TREE_DEPTH = int(os.getenv("MAX_TREE_DEPTH", "100"))` in `database.py`
- `TreeDepthLimitExceeded(depth, limit)` custom exception
- `add_a_node()` takes `depth: int = 0` parameter; raises at `depth > MAX_TREE_DEPTH`; passes `depth + 1` on recursive calls
- Three call sites in `api.py` catch `TreeDepthLimitExceeded` and return HTTP 422
- `MAX_TREE_DEPTH` documented in `.env.example`

### Cleanup & Docs Sprint (L1/L2/L3/L4/M5) — PR #16
- **L1:** Three `== None` → `is None` fixes in `api.py`
- **L3:** `ConsoleDisplay` replaced with Python `logging` module. `helpers.py` rewritten as `get_logger()` factory (stream + file handlers, level from `DEBUG` env var). `config.py` reduced to `load_dotenv()` only. All 146 call sites updated across `database.py` and `api.py`. `exc_info=True` added on all error-level except blocks.
- **M5:** 9 `HTTPException` detail strings no longer embed `{e}`; 5 more 404 messages stripped of internal `account_id`. Full exception details retained in `logger.error()`.
- **L4:** `server/tests/test_unit.py` — 43 unit tests (no live DB required): Pydantic model validation, `saves_helper`/`users_saves_helper`, auth helpers (hash/verify, token creation), tree depth boundary tests.
- **L2:** `README.md` added at repo root.

### Self-Assignment Refactor (4.5) — PR #17
- 71 `self.x = param` assignments removed across 22 methods (11 `TreeStorage` + 11 `UserStorage`)
- All parameters, intermediates and return values now use local variables
- `add_a_node()` recursive method: `self.name`, `self.id`, `self.children`, `self.child_id` etc. all local — eliminates the hidden concurrency risk where recursive frames overwrote shared instance state
- `save_user_details()`: 9-field unpack block replaced with direct `UserDetails(...)` construction from `user` param
- Net: -50 lines in `database.py`

### Test Suite Status (2026-03-16)
- **171 tests collected** (128 integration + 43 unit)
- **161 passed, 10 skipped, 0 failed** (161 after PR #17)
- 10 skips are expected scope tests (pytest.skip when token has sufficient scope)

---

## Remaining Work

### 4.1 — Verify Motor Connection Pooling
**Priority:** Medium
**Scope:** Load-test or profile the app to confirm the single shared `AsyncIOMotorClient` is actually reusing connections rather than creating new TCP sockets per request. Motor's default pool size is 100; verify this is appropriate for expected concurrency.

### 4.3 — Performance / Load Tests
**Priority:** Low
**Scope:** Locust or pytest-benchmark tests against a staging environment; focus on tree load/save cycle under concurrent users.

### 4.4 — Comprehensive API Documentation
**Priority:** Low
**Scope:** Add OpenAPI `summary`, `description`, `response_model`, and example schemas to all route handlers. FastAPI auto-generates docs at `/docs` but they currently lack descriptive text.

### Optional: Happy-Path Scope Tests
**Priority:** Low
**Scope:** Dedicated tests confirming users WITH correct scopes CAN perform operations.
**Notes:** Now that scope tests only test 403, these would complement them.

### Pre-commit Hook: `sudo` Not Found
**Priority:** Low
**Issue:** The `.git/hooks/pre-commit` script calls `sudo`, which is not available in all environments (e.g. CI, Dev Containers). The hook silently fails (`sudo: not found`) rather than blocking the commit.
**Action:** Inspect `.git/hooks/pre-commit`, determine if `sudo` is necessary, and either remove it or replace with a non-privileged equivalent.

### Architectural Consideration: Tree Storage Model
**Priority:** Awareness (not blocking)
**Issue:** Every read/write reconstructs the full tree from MongoDB and every write appends a new complete snapshot. Works fine at current scale but will hit performance/concurrency issues with larger trees or multiple concurrent users. See `quickread.md` for details.

---

---

## Environment Context (for next session)

### Completed Fixes (2026-02-05)

**pytz → zoneinfo (api.py):**
```python
# Was blocking test imports (pytz not in requirements)
from zoneinfo import ZoneInfo  # line 12
datetime.now(ZoneInfo("GMT"))  # line 234
```

**httpx AsyncClient API (test_api_integration.py):**
```python
# httpx 0.28.1 requires transport parameter
from httpx import ASGITransport
httpx.AsyncClient(transport=ASGITransport(app=api.app), base_url="...")
# All occurrences updated via replace_all
```

**Environment:**
- Fresh venv at `/server/venv/`
- Python 3.9.6
- MongoDB Atlas: Accessible (tested with ping)
- Redis Cloud: Accessible (tested with ping)
- 148 tests collected successfully

### Dependency Versions

| Package | Version |
|---------|---------|
| fastapi | 0.128.1 |
| pydantic | 2.12.5 |
| motor | 3.7.1 |
| pymongo | 4.16.0 |
| pytest | 8.4.2 |
| pytest-asyncio | 1.2.0 |
| httpx | 0.28.1 |
| redis | 7.0.1 |
| uvicorn | 0.39.0 |
| starlette | 0.49.3 |
