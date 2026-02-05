# Dependency Update Tasks

Last Updated: 2026-02-05

## Status Summary

✅ **Environment:** Fresh venv with Python 3.9.6, all dependencies updated to 2024/2025 versions
✅ **Critical Fixes:** pytz→zoneinfo (api.py), httpx API update (test file)
⚠️ **Test Suite:** 148 tests collected, 2 passing, integration tests blocked by issues below

---

## Outstanding Tasks

### Fix Test Suite Integration Issues
**Priority:** High
**Status:** Blocked by 2 issues

---

#### Issue 1: Database None Handling
**Error:** `'NoneType' object is not subscriptable`

**Root Cause Analysis:**
- Tests create new users, then immediately try to fetch root node/tree data
- New users have no saved trees in MongoDB
- Database retrieval methods return None when no data exists
- Code tries to subscript/index into None value → crash

**Error Trace:**
```
test_api_integration.py:297: AssertionError (500 response instead of 200)
Logged: "Exception occured retrieving latest save from the database"
Logged: "Error loading tree for account <account_id>: 'NoneType' object is not subscriptable"
```

**Affected Tests:**
- `test_nodes_add_another_root_node`
- `test_nodes_update_node`

**Hypothesis for Fix:**
The issue is likely in database.py or api.py when loading trees. Need to:
1. Find where `get_latest_save()` or similar method is called
2. Add None checking before trying to access properties/indices
3. Either return default empty tree for new users OR handle 404 gracefully in tests

**Investigation Starting Points:**
- `app/database.py`: Search for methods that retrieve saves/trees
- `app/api.py`: `/trees/root` endpoint implementation (returns 500)
- `test_api_integration.py:297`: The `test_get_root_node` fixture

---

#### Issue 2: Redis Event Loop Lifecycle

**Error:** `RuntimeError: Event loop is closed`

**Root Cause Analysis:**
- Occurs during token blacklist check: `oauth.is_token_blacklisted(token)`
- Redis async connection trying to execute after event loop closed
- pytest-asyncio fixture cleanup timing issue

**Error Trace:**
```
app/api.py:237: if await oauth.is_token_blacklisted(token):
app/authentication.py:85: if(await self.conn.get(token)):
...eventually...
asyncio/base_events.py:510: RuntimeError: Event loop is closed
```

**Affected Tests:**
- `test_nodes_remove_node` (possibly others)

**Hypothesis for Fix:**
The Authentication class creates Redis connections but may not close them properly. Options:
1. Ensure Redis connections are properly closed in async context managers
2. Use fixtures to manage Redis connection lifecycle
3. Check if `authentication.py` needs async context manager support
4. May need to adjust pytest-asyncio fixture scopes

**Investigation Starting Points:**
- `app/authentication.py:85`: How Redis connection is created/managed
- `app/authentication.py`: Check if `__aenter__`/`__aexit__` needed
- Test fixtures: May need session-scoped Redis connection

---

## Next Session Action Plan

1. **Start with Issue 1 (Database None):**
   - Read `app/database.py` methods for retrieving saves/trees
   - Read `/trees/root` endpoint in `app/api.py`
   - Add None checks and handle missing data case
   - Re-run affected tests to verify fix

2. **Then tackle Issue 2 (Redis Event Loop):**
   - Read `app/authentication.py` Redis connection management
   - Check if proper async cleanup is implemented
   - Consider adding context manager support if missing
   - Re-run affected tests

3. **Full Test Run:**
   - Once both issues fixed, run: `pytest -v`
   - Monitor for additional failures
   - Address any remaining issues

4. **Documentation:**
   - Update this file with final results
   - Mark task as complete

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
