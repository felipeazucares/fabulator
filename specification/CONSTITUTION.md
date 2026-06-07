# Fabulator — Constitution
## Spec-Driven Development Reference

**Version:** 1.2
**Date:** 2026-06-07
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

## Coding Guidelines

### Do
- Use async/await for all I/O operations
- Use Pydantic models for request/response validation

### Don't
- Don't use global state for tree data (load per-request)
- Don't catch bare `Exception` - use specific exceptions
- Don't create new DB clients per-method (use instance variable)
- Don't hardcode CORS origins (use environment variables)

## Testing Guidelines

- Tests are integration tests requiring live MongoDB/Redis
- Use fixtures for test data setup
- Clean up created data after tests
- Test both success and failure (401/403) scenarios
- No `@pytest.mark.asyncio` needed (auto mode enabled)

### Test Types

**Isolation Tests (`test_isolation_*`):**
- Verify User B cannot access User A's data
- Expected response: 404 (data not found)
- Use `return_isolation_token` fixture (full permissions, separate user)

**Scope Tests (`test_scope_*`):**
- Verify user with limited scopes cannot perform restricted operations on their OWN data
- Expected response: 403 (insufficient permissions)
- Use `return_scoped_token` fixture (parameterized with 6 scope values)
- Tests `pytest.skip()` when the token has the required scope — only insufficient-permission cases run
- 10 tests, each with ~5 passing parametrizations and ~1 skipped (the sufficient-scope case)

## Git Workflow

**IMPORTANT: Always use feature branches. Never commit directly to `main`.**

Workflow for all changes:
1. Create a feature branch: `git checkout -b feature/description` or `fix/issue-name`
2. Make changes and commit to the feature branch
3. Push the feature branch: `git push -u origin feature/description`
4. Create a pull request for review

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `refactor/` - Code refactoring
- `docs/` - Documentation updates

## Commit Style

```
<action> <subject>

<optional body>

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

Examples:
- `Fix duplicate method definition in database.py`
- `Add rate limiting to login endpoint`
- `Update dependencies to latest versions (2024/2025)`

## Part I — Architectural Invariants

These rules define what Fabulator fundamentally *is*. They MUST NOT be changed without a full architectural review.

### I.1 — Normalised Adjacency-List Storage

The system MUST store each node as an independent MongoDB document in `node_collection` with a `parent_id` pointer to its parent. Works are stored in a separate `work_collection`. There MUST be no single-document tree snapshots. The `tree_collection` is retired and MUST NOT be written to.

**Rationale:** Individual node documents allow single-document lookups, targeted updates, and cascade deletes without loading the full tree. treelib is removed entirely.

### I.2 — In-Place Node Updates

Node write operations (create, update, delete, reorder, duplicate) MUST operate directly on individual node documents. There is no append-only snapshot model. `updated_at` MUST be set to `datetime.now(timezone.utc)` on every write.

**Corollary:** There are no save/load endpoints. The node documents ARE the persistent state.

### I.3 — Single Shared Motor Client

There MUST be exactly one `AsyncIOMotorClient` per server process. It MUST be created in the FastAPI lifespan context manager, stored on `app.state.motor_client`, and injected into all storage classes via `Depends()`.

Creating new `AsyncIOMotorClient` instances per-request or per-method is PROHIBITED.

### I.4 — Account Isolation via account_id

Every MongoDB document (Work or node) MUST carry `account_id` (a bcrypt hash of the username set at registration). All database queries MUST filter by `account_id`. Cross-user data access MUST return HTTP 404, not HTTP 403.

**Rationale:** 404 reveals nothing about whether the resource exists for another user.

### I.5 — Hierarchy Enforcement

The node type hierarchy is fixed: `Work → Part → Chapter → Scene → Beat`. This MUST be enforced at application level on every create and reparent operation. Violations MUST return HTTP 422. The hierarchy MUST also be enforced at MongoDB schema level via a JSON Schema validator on `node_collection`.

### I.6 — Work Scoping

Every node MUST carry a `work_id` foreign key linking it to a `work_collection` document. All node queries MUST be scoped to a `work_id`. Nodes from different Works MUST NOT be mixed in any operation.

### I.7 — Author Denormalisation

The `author` field from the Work MUST be copied onto every child node at creation time. When `author` is updated on a Work, the system MUST cascade the update to ALL nodes belonging to that Work in a single operation.

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

All user-supplied path parameters that accept node or work identifiers MUST be validated as UUID4 via `Path(pattern=UUID_PATTERN)`. All user-supplied string fields MUST have explicit length limits enforced via Pydantic `Annotated` types. Tag lists MUST be capped at 50 items, each tag at 100 characters, with empty/whitespace strings rejected.

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
    work_storage: WorkStorage = Depends(get_work_storage),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> dict:
    # ... operations directly on storage classes
    return result
```

`RoutesHelper` is retired and MUST NOT be used. Storage classes are injected directly.

### III.2 — Response Models

Every route MUST declare a `response_model`. Routes MUST NOT omit this — doing so prevents FastAPI from validating output shape and produces incomplete OpenAPI schemas.

### III.3 — OpenAPI Annotations

Every route MUST have `summary`, `description`, and `tags`. Routes MUST be grouped into one of: `Authentication`, `Meta`, `Works`, `Nodes`, `Users`.

### III.4 — Mutating GET Prohibition

New endpoints that mutate state MUST use `POST`, `PUT`, or `DELETE`. GET endpoints MUST be read-only.

### III.5 — HTTP Status Codes

| Condition | Status |
|-----------|--------|
| Success | 200 |
| Created | 201 |
| Validation error | 422 |
| Unauthenticated | 401 |
| Insufficient scope | 403 |
| Resource not found (or cross-user isolation) | 404 |
| Rate limited | 429 |
| Server error | 500 |

### III.6 — Standardised Error Responses

All 4xx and 5xx responses MUST return:

```json
{
  "detail": "human-readable, sanitised error message"
}
```

`detail` MUST NEVER contain stack traces, internal IDs, or raw exceptions. Specific required error message strings are defined in `SPEC.md`.

---

## Part IV — Data Model Contract

### IV.1 — Work Document

Every Work document in `work_collection` MUST carry: `work_id` (UUID4), `account_id`, `title`, `description`, `author`, `tags`, `created_at`, `updated_at`.

### IV.2 — Node Document

Every node document in `node_collection` MUST carry: `node_id` (UUID4), `work_id` (UUID4), `account_id`, `author`, `node_type`, `parent_id`, `position`, `tag`, `description`, `text`, `previous`, `next`, `tags`, `created_at`, `updated_at`.

### IV.3 — Node Type Enum

`node_type` MUST be one of: `"part"`, `"chapter"`, `"scene"`, `"beat"`. No other values are permitted. This MUST be enforced by both the application and the MongoDB JSON Schema validator on `node_collection`.

### IV.4 — Identifier Format

All `node_id` and `work_id` values MUST be UUID4. Identifiers MUST NOT be MongoDB `_id` ObjectIds. Application code MUST use `node_id` / `work_id` for all lookups — never `_id`.

### IV.5 — Position Field

The `position` field represents zero-based ordering among siblings. After any create, delete, or reorder operation, sibling positions MUST form a contiguous zero-based sequence with no gaps.

### IV.6 — Timestamp Convention

All timestamps MUST use `datetime.now(timezone.utc)`. `datetime.utcnow()` and `pytz` are PROHIBITED. The `zoneinfo` standard library module MUST be used for timezone handling.

### IV.7 — MongoDB Schema Validation and Indexes

`work_collection` and `node_collection` MUST be created with JSON Schema validators enforcing field types and enums as defined in `SPEC.md`. Required indexes are defined in `SPEC.md Part II.4` and MUST be created at application startup if not present.

---

## Part V — Code Quality & Tooling Contract

### V.1 — Automated Linting & Formatting

All syntax, style, and type rules are enforced via automated tooling. The following MUST be configured and run in CI/pre-commit:

- `ruff` for linting, formatting, and import sorting
- `mypy` or `pyright` for static type checking
- `commitlint` for commit message structure

Manual enforcement of style rules in PR reviews is PROHIBITED. Tooling failures MUST block merges.

### V.2 — Exception Handling

Bare `except Exception` and `except:` are PROHIBITED. Exceptions MUST be caught by specific type (`pymongo.errors.PyMongoError`, `KeyError`, `ValueError`, etc.). Every `except` block at error level MUST call `logger.error(..., exc_info=True)`.

### V.3 — Async I/O

All database, Redis, and network operations MUST use `async/await`. Synchronous blocking calls in async route handlers are PROHIBITED.

### V.4 — Parameter Assignment Pattern

Methods MUST NOT assign method parameters to instance variables (`self.x = param`) for use within the same method. Local variables MUST be used instead.

### V.5 — Dead Code

Unused classes, methods, and module-level statements MUST NOT be left in the codebase. Before adding a class or function, verify it will be used. Before removing one, verify it is not imported elsewhere.

### V.6 — Logging

All diagnostic output MUST use the Python `logging` module via `get_logger(__name__)`. `print()` statements are PROHIBITED in production code paths. Debug information MUST use `logger.debug()`, errors MUST use `logger.error(exc_info=True)`.

---

## Part VI — Testing Contract

### VI.1 — Test Suite Requirements

All changes to routes, database methods, or authentication MUST include corresponding tests. A PR that introduces new behavior without tests MUST NOT be merged.

### VI.2 — Test Categories

| Category | Location | DB Required | What it proves |
|----------|----------|-------------|----------------|
| Unit | `server/tests/test_unit.py` | No | Models, auth helpers, hierarchy validation, sibling reordering, cycle detection |
| Integration | `server/test_api_integration.py` | Yes | End-to-end HTTP behavior against real MongoDB + Redis |
| Isolation | `test_isolation_*` tests | Yes | User B cannot access User A's data (expect 404) |
| Scope | `test_scope_*` tests | Yes | Insufficient-scope tokens get 403 on their own data |

### VI.3 — Isolation Tests

Every endpoint that reads or mutates user-owned resources MUST have a corresponding `test_isolation_*` test verifying a second user's token receives 404. This applies to both Work and Node endpoints.

### VI.4 — Scope Tests

Every endpoint protected by a specific scope MUST have a corresponding `test_scope_*` test verifying a token without that scope receives 403.

### VI.5 — Unit Test Independence

Unit tests MUST NOT require a running MongoDB or Redis instance. Business logic (hierarchy validation, cycle detection, sibling renumbering, author propagation) MUST be testable by passing data directly to the function under test.

### VI.6 — Test Configuration

`asyncio_mode = auto` is set in `pytest.ini`. `@pytest.mark.asyncio` decorators MUST NOT be added. Set `LOGIN_RATE_LIMIT=1000/minute` in the test `.env` to prevent 429s.

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
- All tests pass
- All security contract rules (Part II) are satisfied
- All code quality gates (Part V) are satisfied
- New endpoints have response models and OpenAPI annotations
- No bare `except Exception` blocks remain
- Linting/formatting checks pass via pre-commit/CI

### VII.3 — Commit Style

```
<action> <subject>

<optional body explaining why, not what>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

Actions are limited to: `Fix`, `Add`, `Update`, `Refactor`. Body MUST explain intent, not mechanics.

---

## Part VIII — Frontend Contract

### VIII.1 — D3/React DOM Boundary

D3 MUST have exclusive ownership of the SVG element inside `TreeVisualiser`. React MUST NOT render or manipulate any DOM nodes inside that SVG.

### VIII.2 — JWT Storage

JWT tokens MUST be stored in memory (Zustand `authStore`) only. Tokens MUST NOT be written to `localStorage`, `sessionStorage`, or cookies unless the token is in an httpOnly cookie set by the server.

### VIII.3 — 401 Handling

All HTTP clients MUST intercept 401 responses globally. On 401, the client MUST clear the auth store and redirect to the login page with a user-visible message.

### VIII.4 — Permission Gating

UI actions that require specific JWT scopes MUST be gated by the `usePermissions()` hook. Actions MUST NOT be hidden or disabled based on hardcoded logic — they MUST consult the token's scopes.

### VIII.5 — React Native Migration Path

All business logic, API calls, and state management MUST be kept separate from rendering components. `TreeVisualiser` is the only component with a web-native implementation. CSS Modules MUST be used for web styles.

---

## Part IX — Infrastructure Contract

### IX.1 — Container Runtime

The project MUST run in Docker containers managed by Docker Compose. The API service is `fabulator-api` (`python:3.12-slim-bookworm`). Dev containers (`dev-claude`, `dev-qwen`) MUST be defined in `.devcontainer/claude/` and `.devcontainer/qwen/` respectively and MUST NOT start in production.

Alpine Linux MUST NOT be used for dev containers — musl libc crashes Claude Code on first run.

### IX.2 — Database and Cache

MongoDB Atlas and Redis Cloud are the canonical external dependencies. Local containerised MongoDB/Redis SHOULD NOT be added to `docker-compose.yml` unless there is a documented offline-first requirement.

### IX.3 — Secrets Management

`.env` is the sole secrets file. It MUST be in `.gitignore` and MUST NOT be committed. `.env.example` MUST document every variable without real values. `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_API_KEY` MUST be kept in separate containers — they MUST NOT both be set in the same container.

### IX.4 — Performance & Scaling Contract

- All list endpoints MUST enforce `limit` (default 50, max 200) and cursor pagination. Unbounded queries are PROHIBITED.
- The server MUST expose `/health` and `/metrics` endpoints.
- Any feature that increases average request latency by >20% MUST include a baseline load test before merge.

---

## Part X — Roadmap Prioritization Contract

When deciding what to build next, work MUST proceed in this order:

| Tier | Category | Principle |
|------|----------|-----------|
| 0 | Security defects and data loss bugs | Fix immediately, no exceptions |
| 1 | Work CRUD + Core Node CRUD | Block all other tiers |
| 2 | Node navigation (children, parent, siblings, ancestors, leaves, stats) | Block frontend visualization |
| 3 | Search and query | After navigation is complete |
| 4 | Enhanced features (relationships, comments, export, bulk) | After search |
| 5 | Advanced features (characters, timeline, templates, analytics, sharing) | After Tier 4 is stable |

---

## Part XI — Technical Debt Registry & Governance

### XI.1 — Registry Schema

All accepted exceptions MUST be logged in `docs/DEBT_REGISTRY.md` with: ID, Description, Severity, Owner, Target Version, Status, Resolution Criteria.

### XI.2 — Governance Rules

- **Quarterly Audit:** Every 4th release, all Open debt items MUST be reviewed.
- **New Exceptions:** Require a PR updating `DEBT_REGISTRY.md` with trade-off and mitigation plan.
- **Security Debt:** Critical severity items MUST be resolved within 1 minor version.

### XI.3 — Current Registry Snapshot

All pre-refactor debt items (M7, M6, L6, L7, L8, L9, L10, L11) from the treelib era are resolved by the adjacency-list refactor. The following carry forward:

| Ref | Violation | Severity | Target Version | Status |
|-----|-----------|----------|----------------|--------|
| 4.3 | No performance/load tests | High | v1.3 | Open |
| P-01 | Pagination not yet enforced on list endpoints | High | v1.2 | Open |
| P-02 | `/metrics` endpoint not yet implemented | Medium | v1.3 | Open |

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

*Co-Authored-By: Millie Kovacs / Claude Sonnet 4.6 <noreply@anthropic.com>*
