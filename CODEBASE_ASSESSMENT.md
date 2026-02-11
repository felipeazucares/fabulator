# Codebase Assessment: Fabulator

**Generated:** 2026-02-04
**Last Updated:** 2026-02-09
**Status:** Active

## Overview

FastAPI backend for a collaborative tree-editing/narrative application using MongoDB, Redis for token blacklisting, and JWT authentication with role-based access control.

### Architecture
```
/server/app/
├── api.py              (924 lines - main FastAPI app & routes)
├── database.py         (629 lines - MongoDB operations)
├── authentication.py   (89 lines - JWT & password handling)
├── models.py           (242 lines - Pydantic schemas)
├── helpers.py          (52 lines - logging utilities)
├── config.py           (9 lines - env loading)
└── __init__.py
```

---

## Strengths

| Area | Details |
|------|---------|
| **Architecture** | Async-first design with FastAPI, recent refactor removed global state (per-request tree loading) |
| **Security Foundation** | OAuth2 with JWT tokens, scope-based RBAC, token blacklisting via Redis |
| **Testing** | Comprehensive integration tests (1,700+ lines), covers auth, CRUD, permissions |
| **Dependencies** | Recently modernized (Pydantic v2, modern pytest-asyncio, zoneinfo) |

---

## Issues by Severity

### Critical

| # | Issue | File | Line(s) | Status |
|---|-------|------|---------|--------|
| C1 | Duplicate `delete_user_details()` method definition | database.py | 554, 598 | [x] Fixed 2026-02-09 (PR #4) |
| C2 | CORS allows all methods/headers with credentials | api.py | 67-78 | [ ] Open |

### High

| # | Issue | File | Line(s) | Status |
|---|-------|------|---------|--------|
| H1 | 63x overly broad `except Exception` catches | database.py | Throughout | [ ] Open |
| H2 | `ConsoleDisplay()` instantiated 50+ times unnecessarily | database.py | Throughout | [ ] Open |
| H3 | No rate limiting on `/get_token` login endpoint | api.py | 271 | [ ] Open |
| H4 | New DB connections created per-request (no pooling) | database.py | 36, 341 | [ ] Open |
| H5 | Missing input validation for tree operations | api.py | 522-538 | [ ] Open |

### Medium

| # | Issue | File | Line(s) | Status |
|---|-------|------|---------|--------|
| M1 | Deprecated `pytz` replaced with zoneinfo | api.py | 12, 234 | [x] Fixed 2026-02-05 |
| M2 | Tree recursion has no depth limit | database.py | 237-335 | [ ] Open |
| M3 | Redis connection never explicitly closed | authentication.py | 29-31 | [x] Fixed 2026-02-09 — lazy connection via `_get_redis_connection()`, closed with `aclose()` |
| M4 | Null checks missing before `saves_helper()` | database.py | 131 | [x] Fixed 2026-02-09 — `get_tree_for_account()` checks save count before loading |
| M5 | Exception messages could leak internal details | api.py | Multiple | [ ] Open |

### Low

| # | Issue | File | Line(s) | Status |
|---|-------|------|---------|--------|
| L1 | Inconsistent `== None` vs `is None` | api.py | 541 | [ ] Open |
| L2 | Missing README & API documentation | N/A | N/A | [ ] Open |
| L3 | No structured logging (only console) | helpers.py | 8 | [ ] Open |
| L4 | Test coverage gaps (no unit tests) | test_api_integration.py | N/A | [ ] Open |

---

## Work Areas (Prioritized by Impact)

### Phase 1: Critical Security & Bugs
**Estimated Effort:** 1-2 days

- [x] **1.1** Fix duplicate `delete_user_details()` method ✅ **Completed 2026-02-09 (PR #4)**
- [ ] **1.2** Fix CORS configuration - Use env var for origins, explicitly list methods/headers
- [ ] **1.3** Add rate limiting - Protect login endpoint from brute force (use SlowAPI or similar)
- [x] **1.4** Replaced pytz with zoneinfo in `api.py` ✅ **Completed 2026-02-05**

### Phase 2: Code Quality & Reliability
**Estimated Effort:** 2-3 days

- [ ] **2.1** Consolidate DB connections - Use singleton client or dependency injection
- [ ] **2.2** Replace broad exception catching - Use specific exceptions (63 instances)
- [ ] **2.3** Add tree depth validation - Prevent stack overflow on deep trees
- [ ] **2.4** Fix ConsoleDisplay instantiation - Make it an instance variable, not per-method
- [x] **2.5** Add null checks before `saves_helper()` calls ✅ **Completed 2026-02-09** — `get_tree_for_account()` checks `number_of_saves_for_account() > 0`

### Phase 3: Testing & Documentation
**Estimated Effort:** 3-5 days

- [x] **3.1** Fix and run test suite ✅ **Completed 2026-02-09** — 103 passed, 10 skipped, 0 failed. Both blockers resolved (Database None handling, Redis event loop).
- [ ] **3.2** Add unit tests - Currently only integration tests exist
- [ ] **3.3** Create README.md - Document setup, architecture, API endpoints
- [ ] **3.4** Add structured logging - Replace console output with Python logging module
- [ ] **3.5** Document tree depth limits and constraints
- [ ] **3.6** Add security-focused tests (attack scenarios, edge cases)

### Phase 4: Performance & Polish
**Estimated Effort:** 2-3 days

- [ ] **4.1** Verify Motor connection pooling is working correctly
- [x] **4.2** Implement Redis connection cleanup ✅ **Completed 2026-02-09** — lazy connection + `aclose()` after each operation
- [ ] **4.3** Add performance/load tests
- [ ] **4.4** Generate comprehensive API documentation
- [ ] **4.5** Remove code duplication in database.py (query patterns, update patterns)

---

## Detailed Findings

### Security Issues

#### CORS Configuration (Critical)
**File:** `server/app/api.py:67-78`
```python
origins = [
    "http://localhost:8000",
    "localhost:8000"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,  # DANGEROUS with open CORS
    allow_methods=["*"],     # Should explicitly list methods
    allow_headers=["*"]      # Should explicitly list headers
)
```

**Recommendation:**
- Use environment variable for allowed origins
- Explicitly list: `allow_methods=["GET", "POST", "PUT", "DELETE"]`
- Explicitly list headers needed

#### No Rate Limiting (High)
- Login endpoint `/get_token` has no protection against brute force
- Recommendation: Add SlowAPI middleware with limits like 5 attempts/minute

### Code Quality Issues

#### Duplicate Method (Critical)
**File:** `server/app/database.py`
- Lines 554 and 598 both define `delete_user_details(self, id: str)`
- Second definition shadows the first

#### Excessive State Assignment
**File:** `server/app/database.py`
- ~110 lines of `self.variable_name = parameter_name` assignments
- Methods should use local variables instead
- Example pattern that repeats:
```python
self.account_id = account_id
self.tree = tree
self.console_display = ConsoleDisplay()
```

#### Overly Broad Exception Handling
**File:** `server/app/database.py`
- 63 instances of `except Exception as e`
- Should catch specific exceptions (ValueError, TypeError, pymongo errors)
- Current pattern loses error context

### Performance Concerns

#### Database Connections
- New `AsyncIOMotorClient` created in every `TreeStorage`/`UserStorage` instance
- Routes create new storage instances per request
- Should use singleton or dependency injection

#### Tree Recursion
**File:** `server/app/database.py:237-335`
- `add_a_node()` is recursive with no depth limit
- Could hit Python's recursion limit (~1000) on deeply nested trees

---

## Testing Status & Gaps

### Current Test Suite Status (2026-02-09)
- **Environment:** Fresh venv, MongoDB Atlas and Redis Cloud verified accessible
- **Collection:** 113 tests collected (pytest-asyncio auto mode)
- **Results:** 103 passed, 10 skipped, 0 failed
- **Blockers resolved:**
  - Database None handling: `get_tree_for_account()` checks save count before loading
  - Redis event loop: Lazy connection via `_get_redis_connection()`, closed with `aclose()`

### Test Architecture (2026-02-09)
- **Isolation tests** (`test_isolation_*`): 7 tests verify User B cannot access User A's data (expect 404)
- **Scope tests** (`test_scope_*`): 10 tests verify insufficient scopes get 403; `pytest.skip()` when token has sufficient scope
- **Security fix:** `/loads/{save_id}` now verifies account ownership via `check_if_document_exists(save_id, account_id)`

### What Exists
- 1,700+ lines of integration tests
- Covers: user CRUD, authentication, tree operations, saves
- Tests 401/403 unauthorized scenarios and cross-user data isolation
- Updated for httpx 0.28.1 API compatibility

### What's Missing
- Unit tests (all tests are integration)
- Database mocking (requires live MongoDB)
- Edge cases: deep trees, large payloads, concurrent requests
- Error scenarios: MongoDB down, Redis failures
- Performance/load tests
- Security attack scenario tests

---

## Change Log

| Date | Changes |
|------|---------|
| 2026-02-04 | Initial assessment created |
| 2026-02-04 | Dependencies modernized: List->list type hints in models.py |
| 2026-02-05 | **Environment:** Fresh venv with Python 3.9.6, all dependencies updated to 2024/2025 versions (FastAPI 0.128.1, Pydantic 2.12.5, Motor 3.7.1, pytest 8.4.2, httpx 0.28.1, redis 7.0.1) |
| 2026-02-05 | **Fixed M1:** Replaced pytz with zoneinfo in api.py (lines 12, 234). Removed unused tzname import and orphaned timezone line. |
| 2026-02-05 | **Test suite:** Updated test_api_integration.py for httpx 0.28.1 API (AsyncClient now requires ASGITransport). 148 tests collected successfully. |
| 2026-02-05 | **Test blockers identified:** (1) Database None handling for new users without saves, (2) Redis event loop lifecycle issue. See TODO_DEPENDENCY_UPDATES.md for details. |
| 2026-02-09 | **Fixed C1:** Removed duplicate `delete_user_details()` method (PR #4) |
| 2026-02-09 | **Fixed M3:** Redis connections now use lazy init + `aclose()` cleanup |
| 2026-02-09 | **Fixed M4:** `get_tree_for_account()` checks save count before loading, returns empty `Tree()` for new users |
| 2026-02-09 | **Fixed 4.2:** Redis connection cleanup implemented |
| 2026-02-09 | **Test suite green:** 103 passed, 10 skipped, 0 failed. Isolation tests renamed, scope tests refactored to 403-only (PR #3) |
| 2026-02-09 | **Security fix:** `/loads/{save_id}` now verifies account ownership |
| 2026-02-09 | **Docs:** Added `quickread.md` tree model guide (PR #5), updated CLAUDE.md (PR #4) |
