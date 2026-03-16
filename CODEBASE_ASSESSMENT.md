# Codebase Assessment: Fabulator

**Generated:** 2026-02-04
**Last Updated:** 2026-03-16
**Status:** Active

## Overview

FastAPI backend for a collaborative tree-editing/narrative application using MongoDB, Redis for token blacklisting, and JWT authentication with role-based access control.

### Architecture

```
/server/app/
├── api.py              (1,102 lines — main FastAPI app, all routes)
├── database.py         (438 lines — MongoDB operations, tree reconstruction)
├── authentication.py   (103 lines — JWT, password hashing, Redis blacklist)
├── models.py           (284 lines — Pydantic schemas, validation constants)
├── helpers.py          (21 lines — get_logger() factory)
└── config.py           (4 lines — load_dotenv only)

/server/
├── test_api_integration.py  (2,073 lines — 87 integration tests)
└── tests/
    └── test_unit.py         (363 lines — 43 unit tests, no live DB)
```

---

## Strengths

| Area | Details |
|------|---------|
| **Architecture** | Async-first design; per-request tree loading eliminates global state; single shared `AsyncIOMotorClient` via FastAPI lifespan + `Depends()` |
| **Security** | OAuth2 JWT with scope-based RBAC; token blacklisting via Redis; bcrypt password hashing; rate limiting on login; CORS restricted by env var; no raw exception details in HTTP responses |
| **Input Validation** | UUID pattern enforcement on all `id` path params; field length limits via Pydantic `Annotated` types; tag count/length/whitespace validation; tree depth limit with HTTP 422 on breach |
| **Observability** | Python `logging` module throughout; `_PoolEventLogger` for MongoDB connection pool events when `DEBUG=True`; structured log format with timestamps and module names |
| **Testing** | 173 tests (130 integration + 43 unit); isolation tests verify cross-user data separation; scope tests verify 403 on insufficient permissions; concurrent-request pool test |
| **API Docs** | All 22 routes annotated with `summary`, `description`, and `tags` — visible at `/docs` |
| **Dependencies** | Pydantic v2, Motor 3.7.1, FastAPI 0.128.1, modern pytest-asyncio, zoneinfo |

---

## Issues by Severity

### Critical

| # | Issue | File | Line(s) | Status |
|---|-------|------|---------|--------|
| C1 | Duplicate `delete_user_details()` method definition | database.py | 554, 598 | ✅ Fixed 2026-02-09 (PR #4) |
| C2 | CORS allows all methods/headers with credentials | api.py | 67-78 | ✅ Fixed 2026-03-15 (PR #6) |

### High

| # | Issue | File | Line(s) | Status |
|---|-------|------|---------|--------|
| H1a | Overly broad `except Exception` catches | database.py | Throughout | ✅ Fixed — 0 remaining |
| H1b | Overly broad `except Exception` catches | api.py | Throughout | ✅ Fixed 2026-03-15 — 0 remaining |
| H2 | `ConsoleDisplay()` instantiated 50+ times unnecessarily | database.py | Throughout | ✅ Fixed 2026-03-15 — replaced with `logging` |
| H3 | No rate limiting on `/get_token` login endpoint | api.py | 341 | ✅ Fixed 2026-03-15 (PR #6) |
| H4 | New DB connections created per-request (no pooling) | database.py | 36, 341 | ✅ Fixed 2026-03-16 (PR #12) — single shared client via lifespan |
| H5 | Missing input validation for tree operations | api.py, models.py | Throughout | ✅ Fixed 2026-03-16 (PR #13) |

### Medium

| # | Issue | File | Line(s) | Status |
|---|-------|------|---------|--------|
| M1 | Deprecated `pytz` replaced with zoneinfo | api.py | 12, 234 | ✅ Fixed 2026-02-05 |
| M2 | Tree recursion has no depth limit | database.py | 237-335 | ✅ Fixed 2026-03-16 (PR #14) — `MAX_TREE_DEPTH` + `TreeDepthLimitExceeded` |
| M3 | Redis connection never explicitly closed | authentication.py | 29-31 | ✅ Fixed 2026-02-09 — lazy connection via `_get_redis_connection()`, closed with `aclose()` |
| M4 | Null checks missing before `saves_helper()` | database.py | 131 | ✅ Fixed 2026-02-09 — `get_tree_for_account()` checks save count before loading |
| M5 | Exception messages could leak internal details | api.py | Multiple | ✅ Fixed 2026-03-16 (PR #16) — generic user-facing messages; details in `logger.error()` |
| M6 | `UserDetails` response model exposes hashed password | api.py, models.py | api.py:391, models.py:157 | ⚠️ Open — `GET /users/me` has `response_model=UserDetails` which includes `password: str`; bcrypt hash is non-reversible but leaking it is not best practice |
| M7 | No `response_model` on 20 of 22 routes | api.py | Throughout | ⚠️ Open — only `/get_token` and `/users/me` declare `response_model`; FastAPI cannot validate output shape or generate accurate response schemas for the rest |

### Low

| # | Issue | File | Line(s) | Status |
|---|-------|------|---------|--------|
| L1 | Inconsistent `== None` vs `is None` | api.py | 541 | ✅ Fixed 2026-03-16 (PR #16) — 0 remaining |
| L2 | Missing README & API documentation | N/A | N/A | ✅ Fixed 2026-03-16 (PR #16) — README.md added at repo root |
| L3 | No structured logging (only console) | helpers.py | 8 | ✅ Fixed 2026-03-16 (PR #16) — Python `logging` via `get_logger()` factory |
| L4 | Test coverage gaps (no unit tests) | test_api_integration.py | N/A | ✅ Fixed 2026-03-16 (PR #16) — 43 unit tests, no live DB required |
| L5 | `self.x = param` pattern in database.py methods | database.py | Throughout | ✅ Fixed 2026-03-16 (PR #17) — 71 assignments removed from 22 methods |
| L6 | `self.x = param` pattern remains in `RoutesHelper` | api.py | 199, 212, 227 | ⚠️ Open — `account_id_exists`, `save_document_exists`, `user_document_exists` still assign params to instance variables |
| L7 | Debug `print()` statement in `update_password` | api.py | 1030 | ⚠️ Open — `print(f"request:{request}")` logs password-change request data to stdout; should use `logger.debug()` |
| L8 | Unused classes in models.py | models.py | 103, 205 | ⚠️ Open — `ResponseModel2` and `UserAccount` are defined but never imported or used anywhere |
| L9 | No-op statement in authentication.py | authentication.py | 15 | ⚠️ Open — `datetime.now(ZoneInfo(tzname[0]))` result is not assigned; appears to be leftover initialisation code |
| L10 | Unused `self._redis_conn = None` in Authentication | authentication.py | 31 | ⚠️ Open — attribute is set in `__init__` but never read; `_get_redis_connection()` always creates a fresh connection |
| L11 | `saves_helper()` called without None guard in `return_latest_save` / `return_save` | database.py | 109, 134 | ⚠️ Open — `find_one()` returns `None` if no document found; `saves_helper(None)` would raise `TypeError`; callers do check save count before reaching these paths, but the guard is not in the methods themselves |

---

## Work Areas Status

### Phase 1: Critical Security & Bugs — ✅ Complete
- [x] **1.1** Fix duplicate `delete_user_details()` method — PR #4
- [x] **1.2** Fix CORS configuration — PR #6
- [x] **1.3** Add rate limiting on login endpoint — PR #6
- [x] **1.4** Replace pytz with zoneinfo — 2026-02-05

### Phase 2: Code Quality & Reliability — ✅ Complete
- [x] **2.1** Consolidate DB connections — single shared client via lifespan + `Depends()` — PR #12
- [x] **2.2** Replace broad exception catching — 0 remaining in both files
- [x] **2.3** Add tree depth validation — `MAX_TREE_DEPTH` env var, `TreeDepthLimitExceeded`, HTTP 422 — PR #14
- [x] **2.4** Fix ConsoleDisplay instantiation — replaced with Python `logging` — PR #16
- [x] **2.5** Add null checks before `saves_helper()` — `get_tree_for_account()` guards via save count check

### Phase 3: Testing & Documentation — ✅ Complete
- [x] **3.1** Fix and run test suite — 163 passed, 10 skipped, 0 failed
- [x] **3.2** Add unit tests — 43 tests, no live DB required — PR #16
- [x] **3.3** Create README.md — PR #16
- [x] **3.4** Add structured logging — Python `logging` via `get_logger()` — PR #16
- [x] **3.5** Input validation and tree depth constraints — PR #13, PR #14
- [x] **3.6** Security-focused tests — isolation tests (404), scope tests (403)

### Phase 4: Performance & Polish — Mostly Complete
- [x] **4.1** Verify Motor connection pooling — `MONGO_MAX_POOL_SIZE` env var, `_PoolEventLogger`, concurrent tests — PR #18
- [x] **4.2** Redis connection cleanup — lazy `_get_redis_connection()` + `aclose()` — 2026-02-09
- [ ] **4.3** Performance/load tests — Locust or pytest-benchmark against staging; not yet implemented
- [x] **4.4** OpenAPI documentation — all 22 routes annotated with `summary`, `description`, `tags` — PR #19
- [x] **4.5** Remove `self.x = param` pattern — 71 assignments removed from `database.py` — PR #17

### Phase 5: Remaining Polish (New)

| # | Issue | Effort | Notes |
|---|-------|--------|-------|
| **5.1** | Remove `print()` in `update_password` | Trivial | Replace with `logger.debug()` |
| **5.2** | Fix `self.x = param` in `RoutesHelper` | Small | 3 methods, same pattern as PR #17 |
| **5.3** | Remove unused `ResponseModel2`, `UserAccount` from models.py | Trivial | Dead code |
| **5.4** | Remove no-op line in authentication.py | Trivial | Line 15 |
| **5.5** | Remove unused `self._redis_conn = None` | Trivial | Line 31 |
| **5.6** | Add `response_model` to remaining 20 routes | Medium | Requires defining response schemas |
| **5.7** | Exclude `password` from `GET /users/me` response | Small | Add `response_model_exclude` or create `UserDetailsPublic` schema |
| **5.8** | Add None guard in `saves_helper()` callers | Small | `return_latest_save` and `return_save` should handle `None` from `find_one()` |

---

## Detailed Findings

### Security

#### CORS Configuration — ✅ Fixed 2026-03-15
Origins read from `CORS_ORIGINS` env var (raises `RuntimeError` at startup if missing). Methods restricted to GET/POST/PUT/DELETE; headers to Authorization/Content-Type.

#### Rate Limiting — ✅ Fixed 2026-03-15
SlowAPI + Redis on `POST /get_token`. `LOGIN_RATE_LIMIT` env var (default `5/minute` per IP). Set `LOGIN_RATE_LIMIT=1000/minute` in test `.env` to avoid 429s during test runs.

#### Password Field in Response (M6 — Open)
**File:** `server/app/api.py:391`, `server/app/models.py:157`

`GET /users/me` declares `response_model=UserDetails`. The `UserDetails` model includes `password: str`, which holds the bcrypt hash. bcrypt is non-reversible, but returning hashes in API responses is not best practice — it unnecessarily exposes data that has no client-side use. Fix: create a `UserDetailsPublic` schema that excludes `password`, or use `response_model_exclude={"password"}`.

#### No Exception Handling in authentication.py
`add_blacklist_token()` and `is_token_blacklisted()` have no try/except around Redis operations. A Redis outage would propagate an unhandled exception rather than a clean HTTP 500. (Lower priority: Redis is already guarded at the middleware level in many paths.)

### Code Quality

#### Debug print() in update_password (L7 — Open)
**File:** `server/app/api.py:1030`
```python
print(f"request:{request}")   # ← should be logger.debug() or removed
```
Logs the password-change request object (including the hashed new password) to stdout on every call. Should use `logger.debug()` or be removed entirely.

#### self.x = param in RoutesHelper (L6 — Open)
**File:** `server/app/api.py:199, 212, 227`

Three `RoutesHelper` helper methods still assign parameters to instance variables. The 4.5 refactor (PR #17) covered `database.py` but not `api.py`:
```python
async def account_id_exists(self, account_id: str):
    self.account_id = account_id      # ← should be local

async def save_document_exists(self, document_id, account_id=None):
    self.document_id = document_id    # ← should be local

async def user_document_exists(self, user_id):
    self.user_id = user_id            # ← should be local
```

#### Unused Code in models.py (L8 — Open)
**File:** `server/app/models.py:103, 205`
- `ResponseModel2` (Pydantic class) — never imported or used. The actual response helper is `ResponseModel` (a plain function). `ResponseModel2` was likely a leftover from an earlier refactor attempt.
- `UserAccount` — never imported or used.

#### Dead Code in authentication.py (L9, L10 — Open)
**File:** `server/app/authentication.py:15, 31`
- Line 15: `datetime.now(ZoneInfo(tzname[0]))` — result discarded; no-op statement, likely a leftover from testing timezone initialisation.
- Line 31: `self._redis_conn = None` — set in `__init__` but never read. `_get_redis_connection()` always constructs a fresh connection; this attribute serves no purpose.

### Architecture

#### Append-Only Save Model
Every tree write (create node, update node, delete node, prune, graft) appends a complete new MongoDB document. There is no in-place update and no automatic pruning of old snapshots. The `tree_collection` grows linearly with edits. This is an intentional design choice (full revision history is a free side-effect) but will require periodic cleanup or pagination strategy at scale.

#### Motor Connection Pooling
Single `AsyncIOMotorClient` created in FastAPI lifespan, stored on `app.state`, injected via `Depends()`. Pool size configurable via `MONGO_MAX_POOL_SIZE` env var (default 100). Enable `DEBUG=True` to see pool checkout/checkin events in logs confirming connection reuse.

#### Missing response_model Declarations (M7 — Open)
Only 2 of 22 routes declare `response_model`. Without it:
- FastAPI cannot validate output shape at serialisation time
- OpenAPI schema shows generic responses
- Clients get no schema-driven type hints

---

## Testing Status

### Current Test Suite (2026-03-16)

| Suite | Tests | Pass | Skip | Fail |
|-------|-------|------|------|------|
| Integration (`test_api_integration.py`) | 130 | 120 | 10 | 0 |
| Unit (`tests/test_unit.py`) | 43 | 43 | 0 | 0 |
| **Total** | **173** | **163** | **10** | **0** |

10 skips are expected: scope tests call `pytest.skip()` when the token has the required scope (only insufficient-permission cases run).

### Test Coverage

| Area | Covered | Notes |
|------|---------|-------|
| User CRUD | ✅ | Create, read, update, delete |
| Authentication | ✅ | Login, logout, token blacklist |
| Tree operations | ✅ | Nodes, prune, graft, saves |
| Cross-user isolation | ✅ | `test_isolation_*` — expects 404 |
| Scope enforcement | ✅ | `test_scope_*` — expects 403 |
| Input validation | ✅ | UUID, length limits, tag constraints |
| Tree depth limit | ✅ | Boundary tests in both unit and integration suites |
| Concurrent requests | ✅ | `test_shared_pool_handles_concurrent_requests` — 10 parallel GET /nodes |
| Pool singleton | ✅ | `test_shared_pool_client_is_singleton` |
| Performance/load | ❌ | No Locust or sustained-load tests |
| Redis failure | ❌ | No tests for Redis outage handling |
| MongoDB failure | ❌ | No tests for MongoDB outage handling |

---

## Change Log

| Date | Changes |
|------|---------|
| 2026-02-04 | Initial assessment created |
| 2026-02-05 | Dependencies modernized; pytz→zoneinfo; httpx 0.28.1 ASGITransport |
| 2026-02-09 | Fixed C1 (duplicate method), M3 (Redis cleanup), M4 (None guard). Test suite green: 103 passed, 10 skipped |
| 2026-03-15 | Fixed C2 (CORS), H1b (exception handling), H2 (ConsoleDisplay), H3 (rate limiting) |
| 2026-03-16 | Fixed H4 (DB pooling PR #12), H5 (input validation PR #13), M2 (tree depth PR #14) |
| 2026-03-16 | Fixed L1/L3/L4/M5 (cleanup + logging + unit tests + exception leaking — PR #16) |
| 2026-03-16 | Fixed L5 (self.x = param in database.py — PR #17); 161 tests pass |
| 2026-03-16 | Fixed 4.1 (Motor pool observability — PR #18); MONGO_MAX_POOL_SIZE env var; _PoolEventLogger; 2 new tests |
| 2026-03-16 | Fixed 4.4 (OpenAPI annotations — PR #19); all 22 routes annotated; 6 tag groups |
| 2026-03-16 | **Re-assessment:** fresh scan identified M6/M7 (response model gaps), L6–L11 (minor dead code and remaining self.x patterns in RoutesHelper). All critical, high, and original medium/low issues resolved. |
