# Dependency Update Tasks

Last Updated: 2026-02-09

## Status Summary

✅ **Environment:** Fresh venv with Python 3.9.6, all dependencies updated to 2024/2025 versions
✅ **Critical Fixes:** pytz→zoneinfo (api.py), httpx API update (test file)
✅ **Issue 1 (Database None Handling):** Fixed — `get_tree_for_account()` now checks `number_of_saves_for_account() > 0` before loading; returns empty `Tree()` for new users
✅ **Issue 2 (Redis Event Loop):** Fixed — lazy connection via `_get_redis_connection()`, connections properly closed with `await conn.aclose()`
✅ **Test Suite:** 113 tests collected, 103 passed, 10 skipped, 0 failed
✅ **Scope Tests:** Refactored — only test insufficient permissions (403), skip when token has sufficient scope
✅ **Isolation Tests:** 7 tests renamed from `test_scope_*` to `test_isolation_*`, verify cross-user data isolation (404)
✅ **Security Fix:** `/loads/{save_id}` now verifies account ownership via `check_if_document_exists(save_id, account_id)`

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

## Remaining Work

### Optional: Unit Test Suite for api.py
**Priority:** Low (deferred — may refactor api.py first)
**Scope:** ~74 tests across 21 route handlers, mocking DB and auth layers
**Estimated cost:** ~$1.45 (full suite) or ~$0.50 (nodes-only)

### Optional: Happy-Path Scope Tests
**Priority:** Low
**Scope:** Dedicated tests confirming users WITH correct scopes CAN perform operations
**Notes:** Now that scope tests only test 403, these would complement them

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
