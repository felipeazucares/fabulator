# Fabulator — Constitution
## Spec-Driven Development Reference

**Version:** 1.0
**Date:** 2026-06-06
**Authority:** This document overrides all other guidance where conflicts exist.
**Scope:** Backend (`server/`), frontend (`client/`), infrastructure (Docker/Colima), and AI-assisted development workflow.

---

## How to Use This Document

This is the authoritative rulebook for all changes to Fabulator. Every pull request, spec, and feature must comply with the contracts defined here. Rules are written in normative language:

- **MUST** — non-negotiable; a violation is a defect
- **MUST NOT** — prohibited; doing this is a defect
- **SHOULD** — strongly recommended; deviation requires explicit justification in the PR
- **MAY** — permitted but not required

---

## Part I — Architectural Invariants

These rules define what Fabulator fundamentally *is*. They MUST NOT be changed without a full architectural review.

### I.1 — Stateless Per-Request Tree Loading

The system MUST load tree data fresh from MongoDB on every request. There MUST be no in-memory global tree state shared between requests or users.

**Rationale:** Eliminates entire classes of concurrency bugs. Intentional trade-off against performance — acceptable at current scale.

### I.2 — Append-Only Save Model

Every write operation (create node, update node, delete node, prune, graft) MUST insert a brand-new MongoDB document. In-place updates of existing save documents are PROHIBITED.

**Consequence:** The `tree_collection` grows linearly with edits. This is a known, accepted trade-off. Full revision history is a free side-effect.

**Corollary:** There is no explicit "save" endpoint. Saves are implicit on every write.

### I.3 — Single Shared Motor Client

There MUST be exactly one `AsyncIOMotorClient` per server process. It MUST be created in the FastAPI lifespan context manager, stored on `app.state.motor_client`, and injected into all storage classes via `Depends()`.

Creating new `AsyncIOMotorClient` instances per-request or per-method is PROHIBITED.

### I.4 — Account Isolation via account_id

Every MongoDB document that belongs to a user MUST be keyed by `account_id` (a bcrypt hash of the username set at registration). All database queries MUST filter by `account_id`. Cross-user data access MUST return HTTP 404, not HTTP 403.

**Rationale:** 404 reveals nothing about whether the resource exists for another user.

### I.5 — Tree Depth Enforcement

Tree reconstruction MUST enforce `MAX_TREE_DEPTH` (default 100, env-configurable). Exceeding the limit MUST raise `TreeDepthLimitExceeded` and return HTTP 422 to the client. This check MUST occur during `add_a_node()` recursion, not as a post-hoc guard.

---

## Part II — Security Contract

All rules in this section MUST be satisfied before any code is merged to `main`.

### II.1 — CORS

CORS allowed origins MUST be read from the `CORS_ORIGINS` environment variable. The server MUST raise `RuntimeError` at startup if this variable is absent. Hardcoding origins in source code is PROHIBITED.

Allowed methods MUST be restricted to: `GET`, `POST`, `PUT`, `DELETE`.
Allowed headers MUST be restricted to: `Authorization`, `Content-Type`.

### II.2 — Authentication

- All protected routes MUST use `Security(get_current_active_user_account, scopes=[...])`.
- Passwords MUST be hashed with bcrypt. Plaintext passwords MUST NOT be stored or logged.
- JWT tokens MUST be blacklisted in Redis on logout.
- Token expiry (default 30 minutes) MUST be enforced server-side.

### II.3 — Rate Limiting

`POST /get_token` MUST be rate-limited per IP. The limit MUST be configurable via `LOGIN_RATE_LIMIT` env var (default `5/minute`). Test environments SHOULD set `LOGIN_RATE_LIMIT=1000/minute` to avoid false 429s.

### II.4 — Input Validation

All user-supplied path parameters that accept node/save identifiers MUST be validated as UUIDs via `Path(pattern=UUID_PATTERN)`. All user-supplied string fields MUST have explicit length limits enforced via Pydantic `Annotated` types. Tag lists MUST be capped at 50 items, each tag at 100 characters, with empty/whitespace strings rejected.

### II.5 — Exception Exposure

HTTP error response `detail` fields MUST NOT embed raw exception messages, internal identifiers (`account_id`, document IDs), or stack traces. Full exception details MUST be written to `logger.error(..., exc_info=True)` for internal observability only.

### II.6 — Password Field in Responses

The `password` field (bcrypt hash) MUST NOT appear in any API response. Routes returning user data MUST use a response model that excludes the password field.

---

## Part III — API Contract

### III.1 — Route Pattern

All route handlers MUST follow this pattern:

```python
@app.METHOD("/path", response_model=ResponseSchema, summary="...", description="...", tags=["Group"])
async def handler_name(
    account_id: str = Security(get_current_active_user_account, scopes=["scope:required"]),
    db_storage: TreeStorage = Depends(get_tree_storage),
    user_storage: UserStorage = Depends(get_user_storage),
) -> dict:
    routes_helper = RoutesHelper(db_storage=db_storage, user_storage=user_storage)
    # ... operations
    return ResponseModel(data=result, message="Success")
```

### III.2 — Response Models

Every route MUST declare a `response_model`. Routes MUST NOT omit this — doing so prevents FastAPI from validating output shape and produces incomplete OpenAPI schemas.

### III.3 — OpenAPI Annotations

Every route MUST have `summary`, `description`, and `tags`. Routes MUST be grouped into one of: `Authentication`, `Meta`, `Trees`, `Nodes`, `Saves`, `Users`.

### III.4 — Mutating GET Prohibition

`GET /trees/{id}` (prune) is a known legacy quirk where a GET is destructive. This pattern MUST NOT be replicated in new endpoints. New endpoints that mutate state MUST use `POST`, `PUT`, or `DELETE`.

### III.5 — HTTP Status Codes

| Condition | Status |
|-----------|--------|
| Success | 200 |
| Created | 201 |
| Validation error (bad input, depth exceeded) | 422 |
| Unauthenticated | 401 |
| Insufficient scope | 403 |
| Resource not found (or cross-user isolation) | 404 |
| Rate limited | 429 |
| Server error | 500 |

---

## Part IV — Data Model Contract

### IV.1 — Node Identifier Format

All node identifiers MUST be UUIDs (UUID4 format). The `_identifier` field is set by treelib and MUST NOT be overridden with non-UUID values.

### IV.2 — NodePayload Fields

The `data` field of every tree node MUST conform to the `NodePayload` schema: `description`, `text`, `previous`, `next`, `tags`. The `previous` and `next` fields are application-level narrative ordering hints — they are NOT enforced by treelib and MUST be treated as free-text references, not foreign keys.

### IV.3 — Serialization Format

Trees MUST be serialized and deserialized via treelib's native dict format. Custom serialization formats MUST NOT be introduced without updating `build_tree_from_dict()` and all associated unit tests.

### IV.4 — Timestamp Convention

All timestamps MUST use `datetime.now(timezone.utc)` (not `datetime.utcnow()`, not `pytz`). The `zoneinfo` standard library module MUST be used for timezone handling.

---

## Part V — Code Quality Gates

These rules apply to all new and modified code.

### V.1 — Exception Handling

Bare `except Exception` and `except:` are PROHIBITED. Exceptions MUST be caught by specific type (`pymongo.errors.PyMongoError`, `KeyError`, `ValueError`, treelib-specific exceptions, etc.). Every `except` block at error level MUST call `logger.error(..., exc_info=True)`.

### V.2 — Async I/O

All database, Redis, and network operations MUST use `async/await`. Synchronous blocking calls in async route handlers are PROHIBITED.

### V.3 — Type Syntax

Python 3.9+ built-in generics MUST be used: `list[str]` not `List[str]`, `dict[str, Any]` not `Dict[str, Any]`, `Optional[str]` is acceptable but `str | None` is preferred.

### V.4 — Null Checks

`is None` MUST be used for null comparisons. `== None` is PROHIBITED.

### V.5 — Parameter Assignment Pattern

Methods MUST NOT assign method parameters to instance variables (`self.x = param`) for use within the same method. Local variables MUST be used instead. This eliminates hidden concurrency risk in recursive methods.

### V.6 — Logging

All diagnostic output MUST use the Python `logging` module via `get_logger(__name__)`. `print()` statements are PROHIBITED in production code paths. Debug information MUST use `logger.debug()`, errors MUST use `logger.error(exc_info=True)`.

### V.7 — Dead Code

Unused classes, methods, and module-level statements MUST NOT be left in the codebase. Before adding a class or function, verify it will be used. Before removing one, verify it is not imported elsewhere.

### V.8 — Environment Variables

All configuration MUST be read from environment variables. Hardcoded secrets, hostnames, credentials, or environment-specific values in source code are PROHIBITED. All required env vars MUST be documented in `.env.example`.

---

## Part VI — Testing Contract

### VI.1 — Test Suite Requirements

All changes to routes, database methods, or authentication MUST include corresponding tests. A PR that introduces new behavior without tests MUST NOT be merged.

### VI.2 — Test Categories

| Category | Location | DB Required | What it proves |
|----------|----------|-------------|----------------|
| Unit | `server/tests/test_unit.py` | No | Models, auth helpers, tree logic in isolation |
| Integration | `server/test_api_integration.py` | Yes | End-to-end HTTP behavior against real MongoDB + Redis |
| Isolation | `test_isolation_*` tests | Yes | User B cannot access User A's data (expect 404) |
| Scope | `test_scope_*` tests | Yes | Insufficient-scope tokens get 403 on their own data |

### VI.3 — Isolation Tests

Every endpoint that reads or mutates user-owned resources MUST have a corresponding `test_isolation_*` test that verifies a second user's token receives 404.

### VI.4 — Scope Tests

Every endpoint protected by a specific scope MUST have a corresponding `test_scope_*` test that verifies a token without that scope receives 403. The test MUST call `pytest.skip()` when the parameterized token does have the required scope (only the insufficient-permission case is tested).

### VI.5 — Unit Test Independence

Unit tests MUST NOT require a running MongoDB or Redis instance. Business logic that depends on the database MUST be testable by passing mock or in-memory data directly to the function under test.

### VI.6 — Test Configuration

`asyncio_mode = auto` is set in `pytest.ini`. `@pytest.mark.asyncio` decorators MUST NOT be added. Set `LOGIN_RATE_LIMIT=1000/minute` in the test `.env` to prevent 429s during integration test runs.

---

## Part VII — Git and Workflow Contract

### VII.1 — Branch Policy

All changes MUST be made on a feature branch. Direct commits to `main` are PROHIBITED.

Branch naming MUST follow:
- `feature/` — new functionality
- `fix/` — bug corrections
- `refactor/` — structural changes with no behavior change
- `docs/` — documentation only

### VII.2 — Pull Request Requirements

A PR MUST NOT be merged unless:
- All tests pass (163 pass, 10 expected skips, 0 failures)
- All security contract rules (Part II) are satisfied
- All code quality gates (Part V) are satisfied
- New endpoints have response models and OpenAPI annotations
- No bare `except Exception` blocks remain

### VII.3 — Commit Style

```
<action> <subject>

<optional body explaining why, not what>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

Commit messages MUST describe intent, not mechanics. "Fix" means a bug was corrected. "Add" means new capability. "Update" means an enhancement to existing capability. "Refactor" means behavior-preserving restructuring.

---

## Part VIII — Frontend Contract

This section applies to the React web client (`client/`) and any future React Native client.

### VIII.1 — D3/React DOM Boundary

D3 MUST have exclusive ownership of the SVG element inside `TreeVisualiser`. React MUST NOT render or manipulate any DOM nodes inside that SVG. `TreeVisualiser` is the hard boundary — everything inside is D3's; everything outside is React's.

**Rationale:** D3 and React both mutate the DOM. Mixing them in the same DOM subtree causes unpredictable behavior.

### VIII.2 — JWT Storage

JWT tokens MUST be stored in memory (Zustand `authStore`) only. Tokens MUST NOT be written to `localStorage`, `sessionStorage`, or cookies unless the token is in an httpOnly cookie set by the server.

On logout, the token MUST be cleared from both the Zustand store AND any persistent storage before redirecting.

### VIII.3 — 401 Handling

All HTTP clients MUST intercept 401 responses globally. On 401, the client MUST clear the auth store and redirect to the login page with a user-visible message. Silent 401s (requests that fail without user feedback) are PROHIBITED.

### VIII.4 — Permission Gating

UI actions that require specific JWT scopes (create, update, delete) MUST be gated by the `usePermissions()` hook, which derives allowed actions from the decoded JWT. Actions MUST NOT be hidden or disabled based on hardcoded logic — they MUST consult the token's scopes.

### VIII.5 — React Native Migration Path

All business logic, API calls, and state management MUST be kept separate from rendering components. `TreeVisualiser` is the only component with a web-native implementation — all other components MUST be portable to React Native without modification. CSS Modules MUST be used for web styles (not inline styles or CSS-in-JS) to make the eventual swap to `StyleSheet` straightforward.

---

## Part IX — Infrastructure Contract

### IX.1 — Container Runtime

The project MUST run in Docker containers managed by Docker Compose. The API service is `fabulator-api` (`python:3.12-slim-bookworm`). The Claude Code service is `claude-code` (`node:20-slim`) and MUST be behind the `dev` profile so it does not start in production.

Alpine Linux MUST NOT be used for the Claude Code container — musl libc crashes Claude Code on first run.

### IX.2 — Database and Cache

MongoDB Atlas and Redis Cloud are the canonical external dependencies. Local containerised MongoDB/Redis SHOULD NOT be added to `docker-compose.yml` unless there is a documented offline-first requirement.

### IX.3 — Secrets Management

`.env` is the sole secrets file. It MUST be in `.gitignore` and MUST NOT be committed. `.env.example` MUST document every variable without real values. `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_API_KEY` MUST be kept in separate containers — they MUST NOT both be set in the same container.

---

## Part X — Roadmap Prioritization Contract

When deciding what to build next, work MUST proceed in this order unless there is explicit written justification for deviation:

| Tier | Category | Principle |
|------|----------|-----------|
| 0 | Security defects and data loss bugs | Fix immediately, no exceptions |
| 1 | Core CRUD gaps (missing fundamental operations) | Block Tier 2+ |
| 2 | Tree navigation (children, parent, siblings, ancestors, leaves, stats) | Block frontend visualization |
| 3 | Search and query | After navigation is complete |
| 4 | Enhanced features (relationships, comments, export, bulk) | After search |
| 5 | Advanced features (characters, timeline, templates, analytics, sharing) | After Tier 4 is stable |

Current Tier 1 backlog (MUST be completed before Tier 2 work begins):
- `DELETE /saves/{save_id}` — delete a specific save
- `GET /saves/{save_id}` — save metadata without loading tree
- `POST /nodes/{id}/duplicate` — copy node with optional children
- `PUT /nodes/{id}/reorder` — change position among siblings

---

## Part XI — Known Accepted Exceptions

These are rule violations that are known, documented, and accepted until explicitly resolved. They MUST NOT be used as precedent for introducing new violations of the same type.

| Ref | Violation | Location | Resolution Target |
|-----|-----------|----------|-------------------|
| M7 | 20 of 22 routes missing `response_model` | `api.py` | Phase 5.6 |
| M6 | `GET /users/me` response includes password hash | `api.py:391` | Phase 5.7 |
| L6 | `self.x = param` pattern in `RoutesHelper` | `api.py:199,212,227` | Phase 5.2 |
| L7 | `print()` statement in `update_password` | `api.py:1030` | Phase 5.1 |
| L8 | Unused `ResponseModel2`, `UserAccount` in models.py | `models.py:103,205` | Phase 5.3 |
| L9 | No-op line in `authentication.py` | `authentication.py:15` | Phase 5.4 |
| L10 | Unused `self._redis_conn = None` | `authentication.py:31` | Phase 5.5 |
| L11 | No `None` guard inside `saves_helper()` callers | `database.py:109,134` | Phase 5.8 |
| 4.3 | No performance/load tests | — | Future sprint |
| — | Mutating `GET /trees/{id}` prune endpoint | `api.py` | Not to be replicated |

---

## Appendix A — Quick Reference: Required Env Vars

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `MONGO_DETAILS` | Yes | — | MongoDB Atlas connection string |
| `REDISHOST` | Yes | — | Redis connection URL |
| `SECRET_KEY` | Yes | — | JWT signing secret |
| `ALGORITHM` | Yes | — | JWT algorithm (e.g. `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | — | Token lifetime |
| `CORS_ORIGINS` | Yes | — | Comma-separated allowed origins |
| `LOGIN_RATE_LIMIT` | No | `5/minute` | Login rate limit per IP |
| `MAX_TREE_DEPTH` | No | `100` | Max tree reconstruction depth |
| `MONGO_MAX_POOL_SIZE` | No | `100` | Motor connection pool size |
| `DEBUG` | No | `False` | Enables pool event logging |

---

## Appendix B — Tech Stack Versions (Pinned 2026-03-16)

| Package | Version |
|---------|---------|
| fastapi | 0.128.1 |
| pydantic | 2.12.5 |
| motor | 3.7.1 |
| pymongo | 4.16.0 |
| uvicorn | 0.39.0 |
| redis | 7.0.1 |
| httpx | 0.28.1 |
| pytest | 8.4.2 |
| pytest-asyncio | 1.2.0 |
| slowapi | 0.1.9 |

---

*Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>*
