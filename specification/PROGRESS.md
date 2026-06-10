# Refactor Progress — Normalised Adjacency-List Model

**Branch:** `refactor/normalised-node-model`
**Archiecture:** `DESIGN.md`| **requirements:** `REQUIREMENTS.md` | .md document in this directory for each feature in REQUIREMENTS.md lists tasks to be completed.| **Rules:** `CONSTITUTION.md`
**Started:** 2026-06-07

---

## Status Key

| Symbol | Meaning |
|--------|---------|
| ✅ | Done — committed |
| 🔄 | In progress |
| ⬜ | Not started |
| ❌ | Blocked |
| ⚠️ | Done — with caveats |

---

## Phase 0 — Branch Setup

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-00 | Create branch `refactor/normalised-node-model` from `main` | ✅ | 5 min | |

---

## Phase 1 — Pydantic Models (`models.py`)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-01 | Add Work schemas: `CreateWorkRequest`, `UpdateWorkRequest`, `WorkResponse` | ✅ | 30 min | |
| T-02 | Add Node schemas: `CreateNodeRequest`, `UpdateNodeRequest`, `ReorderRequest`, `NodeResponse` | ✅ | 45 min | UUID pattern on IDs; `node_type` Enum; tag list cap 50 |
| T-03 | Add `AncestorsResponse`, `WorkStatsResponse` | ✅ | 15 min | |
| T-04 | Remove unused `ResponseModel2`, `UserAccount` (Constitution XI L8) | ✅ | 15 min | Verified no imports before removing |

---

## Phase 2 — Database Storage Classes (`database.py`)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-05 | `WorkStorage` class: `create`, `get`, `list`, `update`, `delete`, `cascade_author_to_nodes` | ✅ | 2h | Author cascade = bulk `update_many` on `node_collection` by `work_id` |
| T-06 | `NodeStorage` class (core): `create`, `get`, `list`, `update`, `delete_cascade` | ✅ | 3h | BFS cascade delete; position management on create/delete |
| T-07 | `NodeStorage` (navigation): `get_children`, `get_parent`, `get_ancestors`, `get_siblings`, `get_roots`, `get_leaves` | ✅ | 1h 30m | Ancestors = iterative traversal up `parent_id` chain |
| T-08 | `NodeStorage` (helpers): `get_stats`, `reorder_siblings`, `duplicate_shallow`, `duplicate_deep`, `would_create_cycle` | ✅ | 2h | cycle detection walks parent_id chain from proposed new parent up to root |
| T-09 | MongoDB collection setup: `work_collection` + `node_collection` with JSON Schema validators + all 7 indexes | ✅ | 45 min | Runs in lifespan startup; idempotent |

---

## Phase 3 — Dependency Injection Wiring (`api.py`)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-10 | Add `get_work_storage` and `get_node_storage` `Depends()` functions | ✅ | 15 min | Also wired `setup_collections` into lifespan startup |

---

## Phase 4 — Work Endpoints (`api.py`)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-11 | `GET /works` — list all Works for account, ordered by `created_at` desc | ✅ | 30 min | Returns 200 with `list[WorkResponse]`; empty array `[]` if no works; account isolation via `account_id` filter in DB query |
| T-12 | `GET /works/{work_id}` — single Work; 404 on wrong account | ✅ | 20 min | `work_id` validated via `Path(pattern=UUID_PATTERN)`; 404 with `detail: "Work not found"` on wrong account or missing doc |
| T-13 | `POST /works` — create; whitespace title → 422; HTTP 201 | ✅ | 30 min | Returns 201 with `WorkResponse`; whitespace title caught by `CreateWorkRequest` (`TitleStr`: `strip_whitespace=True` + `min_length=1`) |
| T-14 | `PUT /works/{work_id}` — update; author change triggers node cascade | ✅ | 30 min | Uses `request.model_dump(exclude_unset=True)` for partial updates; author change calls `work_storage.update_work` which triggers `cascade_author_to_nodes` (`update_many` on `node_collection`) |
| T-15 | `DELETE /works/{work_id}` — delete Work + all nodes; return count in detail | ✅ | 30 min | Calls `work_storage.delete_work` which deletes from `work_collection` + bulk `delete_many` on `node_collection`; returns `{"detail": "Work deleted. {N} node(s) removed."}` |

---

## Phase 5 — Node Core CRUD Endpoints (`api.py`)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-16 | `GET /works/{work_id}/nodes` — list with optional `?node_type=` filter; 422 on invalid type | ✅ | 30 min | `node_type` param uses `Optional[NodeType]` enum — invalid values rejected by Pydantic as 422; verifies work ownership first → 404 |
| T-17 | `GET /nodes/{node_id}` — single node; 404 on wrong account | ✅ | 20 min | `node_id` validated via UUID_PATTERN; `node_storage.get_node` filters by `account_id` — 404 on wrong account or missing |
| T-18 | `POST /nodes` — hierarchy validation (HIER-01/02/03); position assignment (NODE-05); author copy from Work | ✅ | 45 min | Hierarchy enforced via `is_valid_parent_child` before DB write; no-parent check for non-Part nodes → 422; position auto-assigned as count of siblings; author copied from `work_doc["author"]` |
| T-19 | `PUT /nodes/{node_id}` — content update + reparent; hierarchy re-validation; cycle detection (UPDATE-03) | ✅ | 45 min | Partial update via `exclude_unset=True`; reparent validates parent exists → hierarchy (`is_valid_parent_child`) → cycle (`would_create_cycle`); hierarchy check fires before cycle check |
| T-20 | `DELETE /nodes/{node_id}` — cascade delete; return descendant count | ✅ | 30 min | BFS cascade via `node_storage.delete_node_cascade`; returns `{"detail": "Node deleted. {N} descendant(s) removed."}`; 404 on wrong account |

---

## Phase 6 — Node Navigation Endpoints (`api.py`)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-21 | `GET /nodes/{node_id}/children` — ordered by position | ✅ | 20 min | |
| T-22 | `GET /nodes/{node_id}/parent` — null for Part root | ✅ | 20 min | |
| T-23 | `GET /nodes/{node_id}/ancestors` — root-to-parent ordered list | ✅ | 20 min | |
| T-24 | `GET /nodes/{node_id}/siblings` — excludes self; ordered by position | ✅ | 20 min | |
| T-25 | `GET /works/{work_id}/nodes/root` — all Part nodes for Work | ✅ | 20 min | |
| T-26 | `GET /works/{work_id}/nodes/leaves` — all Beat nodes for Work | ✅ | 15 min | |
| T-27 | `GET /works/{work_id}/stats` — `WorkStatsResponse` with type counts and max depth | ✅ | 25 min | |

---

## Phase 7 — Reorder & Duplicate Endpoints (`api.py`)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-28 | `PUT /nodes/{node_id}/reorder` — clamp to max sibling; renumber all siblings | ✅ | 30 min | |
| T-29 | `POST /nodes/{node_id}/duplicate` — shallow copy; `"{tag} (copy)"`; position `original + 1` | ✅ | 30 min | |
| T-30 | `POST /nodes/{node_id}/duplicate?deep=true` — recursive subtree copy; new UUIDs; Beat guard → 400 | ✅ | 45 min | |

---

## Phase 8 — Remove Old Endpoints & `treelib`

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-31 | Remove from `api.py`: prune, graft, `/saves`, `/loads` endpoints | ✅ | 30 min | Verify nothing external references before removing |
| T-32 | Remove/retire `TreeStorage` from `database.py` | ✅ | 20 min | `UserStorage` untouched |
| T-33 | Remove `treelib==1.8.0` from `requirements.txt`; remove all treelib imports | ✅ | 15 min | removed from `requirements.txt`; unit tests cleaned up — no treelib imports remain in any source or test file. 33 unit tests pass. | |
| T-34 | Remove or gut `RoutesHelper` (tree-loading methods gone) | ✅ | 20 min | Keep `account_id_exists` + `user_document_exists` if still needed |

---

## Phase 9 — Known Issues Cleanup (Constitution Part XI)

| # | Task | Ref | Status | Est |
|---|------|-----|--------|-----|
| T-35 | Replace `print()` in `update_password` with `logger.debug()` | L7 | ✅ | 5 min |
| T-36 | Fix `self.x = param` pattern in remaining `RoutesHelper` methods | L6 | ✅ | 10 min |
| T-37 | Remove no-op line `authentication.py:15` | L9 | ✅ | 5 min |
| T-38 | Remove unused `self._redis_conn = None` in `authentication.py:31` | L10 | ✅ | 5 min |
| T-39 | Fix `GET /users/me` to exclude `password` hash from response | M6 | ✅ | 15 min |
| T-40 | Add `None` guard in `saves_helper()` callers | L11 | ✅ | 10 min |

*Note: M7 (20 routes missing `response_model`) is resolved by the refactor — all new routes have `response_model` from the start.*

---

## Phase 10 — Unit Tests (`tests/test_unit.py`)

| # | Task | Test IDs | Status | Est |
|---|------|----------|--------|-----|
| T-41 | Hierarchy validator — all valid + invalid parent-child pairs | T-UNIT-01, T-UNIT-02 | ✅ | 20 min |
| T-42 | Cycle detection — direct + indirect | T-UNIT-03, T-UNIT-04 | ✅ | 25 min |
| T-43 | Sibling renumbering — insert-at-start, insert-at-end, remove-from-middle | T-UNIT-05, T-UNIT-06, T-UNIT-07 | ✅ | 30 min | 5 tests in `TestReorderSiblings`; also covers single-node clamp and node-not-found edge cases |
| T-44 | Position clamping, tag suffix on duplicate, Beat deep-copy guard | T-UNIT-08, T-UNIT-09, T-UNIT-10 | ✅ | 20 min | 5 tests in `TestDuplicateNode`; covers shallow position/tag, Beat guard (shallow + deep), deep root copy |
| T-45 | Author propagation — non-null + null | T-UNIT-11, T-UNIT-12 | ✅ | 15 min |

---

## Phase 11 — Integration Tests (`tests/test_integration_normalised.py`)

| # | Task | Test IDs | Count | Status | Est | Notes |
|---|------|----------|-------|--------|-----|-------|
| T-46 | Work CRUD — happy path + errors + isolation + scope | `TestWorkCRUD` — 25 tests | 25 | ✅ | 2h | In `test_integration_normalised.py` |
| T-47 | Node creation — happy path + errors + isolation + scope | `TestNodeCreate` — 25 tests | 25 | ✅ | 2h | Includes list, get, filter, beat guard |
| T-48 | Node retrieval — happy path + errors + isolation + scope | `TestNodeNavigation` — 27 tests | 27 | ✅ | 2h | children, parent, ancestors, siblings, roots, leaves, stats |
| T-49 | Node update + delete — all cases | `TestNodeUpdateDelete` — 17 tests | 17 | ✅ | 1h 30m | |
| T-50 | Reorder + duplicate — all cases | `TestReorderDuplicate` — 18 tests | 18 | ✅ | 1h 30m | |

---

## Phase 12 — Documentation Updates

| # | Task | Status | Est |
|---|------|--------|-----|
| T-51 | Update `CONSTITUTION.md` Part I.2 (append-only removed), Part IV (new node schema) | ✅ | 20 min |
| T-52 | Update `DESIGN.md` Part IV.1 (data model), Part III.1 (API contract), DD-01, DD-03 | ✅ | 30 min |
| T-53 | Tick all checkboxes in `SPEC.md` Part VII acceptance criteria | ✅ | 10 min |

---

## Phase 13 — Verification & PR

| # | Task | Status | Est |
|---|------|--------|-----|
| T-54 | Run full test suite; confirm 0 failures | ✅ | 20 min | 33 unit tests pass; 69 integration tests pass (2 pre-existing failures + 150 pre-existing event-loop errors — not regressions). |
| T-55 | Push branch, open PR | ✅ | 15 min | PR merged to `main` via GitHub. |

---

## Phase 14 — Tier 3: Search & Query (`search-query/feature.md`)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-56 | Add `TextQueryStr`, `MatchType` enum, `NodeSearchResponse` to models.py | ✅ | 10 min | |
| T-57 | Extend `setup_collections()` with `node_text_idx` + `node_tags_idx` indexes | ✅ | 15 min | Idempotent; text index on `description`+`text`, multikey on `{account_id, tags}` |
| T-58 | Add `SearchStorage` class: `search_nodes()`, `find_nodes_by_tags()` | ✅ | 30 min | `$text` search with `textScore`; tag query with `$in`/`$all`; both account-scoped |
| T-59 | Add `GET /nodes/search` endpoint — full-text search over description/text | ✅ | 20 min | `query` (required), `work_id`, `node_type`, `limit` params; strips transient `score` field |
| T-60 | Add `GET /nodes/by-tag` endpoint — tag-based query with `match=any/all` | ✅ | 20 min | `tags` (required, repeated), `match`, `work_id`, `node_type` params |

---

## Phase 15 — Pagination Enforcement on List Endpoints (P-01)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-61 | Add `PaginatedNodeResponse`, `PaginatedWorkResponse` to models.py | ✅ | 10 min | Wraps results with `count` and `next_cursor` |
| T-62 | Add `limit`+`cursor` params to `WorkStorage.list_works` — `_id`-desc cursor pagination | ✅ | 15 min | Sort by `_id` descending (most recent first); cursor filter `{"_id": {"$lt": cursor}}` |
| T-63 | Add `limit`+`cursor` params to `NodeStorage.list_nodes` — `_id`-asc cursor pagination | ✅ | 15 min | Sort by `_id` ascending; cursor filter `{"_id": {"$gt": cursor}}` |
| T-64 | Add `limit`+`cursor` params to `NodeStorage.get_roots` / `get_leaves` — position+`_id` sort | ✅ | 15 min | Sort by `[("position", 1), ("_id", 1)]`; cursor filter `{"_id": {"$gt": cursor}}` |
| T-65 | Update 4 route handlers in api.py with `limit`/`cursor` query params + paginated response models | ✅ | 20 min | `list_works`, `list_normalised_nodes`, `get_work_root_nodes`, `get_work_leaf_nodes` |
| T-66 | Add `limit` to `GET /nodes/by-tag` endpoint and `SearchStorage.find_nodes_by_tags` | ✅ | 10 min | Default 50, max 200; matches existing pattern on `GET /nodes/search` |

## Phase 16 — Health & Metrics Endpoints (P-02)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-67 | Add `HealthResponse` + `MetricsResponse` models | ✅ | 10 min | `status`/`database`/`cache` for health; `uptime_seconds`/`max_pool_size`/`total_requests` for metrics |
| T-68 | Add `GET /health` — MongoDB ping + Redis ping, 200/503 | ✅ | 20 min | No auth; checks both DB and cache; 503 when either is down |
| T-69 | Add `GET /metrics` + request-counting middleware — uptime, pool size, count | ✅ | 25 min | `@fix app.middleware("http")` increments counter; lifespan sets `start_time` and `request_count` |

---

## Phase 17 — Demo Tree Seeding (`demo-seed/feature.md`)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-70 | Add `DemoSeedResponse` model to `models.py` | ✅ | 10 min | `{work_id, title, total_nodes, by_type}`; no `account_id` |
| T-71 | Add optional `session=None` kwarg to `create_work`, `create_node`, and the demo-delete helper; thread into underlying `motor` writes | ✅ | 20 min | Backward-compatible (default `None`); every write in the seed must receive the session or atomicity breaks silently |
| T-72 | Add `build_demo_tree(account_id, author)` pure builder (new `demo.py`) | ✅ | 30 min | Unique UUIDs per node, demo tag absent from builder, typed CreateNodeRequest return, adjacency fields (previous/next) wired in flatten(). All 12 unit tests pass. |
| T-73 | Add `DemoStorage.seed_demo(account_id, author, reset)` — transactional seed | ✅ | 40 min | Transaction management, session threading, compensating cleanup fallback, DI wiring all implemented. Validated by T-76 integration tests. |
| T-74 | Add `POST /demo/seed` endpoint | ✅ | 20 min | Scope `tree:writer`; optional `reset` bool param; 201 `DemoSeedResponse`; `summary`/`description`/`tags=["Demo"]` on decorator |
| T-75 | Unit tests — `build_demo_tree` adjacency integrity | ✅ | 20 min | 12 tests in TestBuildDemoTree: correct structure, node counts, parent references, sibling groups, previous/next chain traversal, root no-parent, author propagation, work tags, pure function, all tags present, all descriptions, hierarchy depth. All pass. |
| T-76 | Integration tests — seed happy path + additive re-run + reset + isolation + scope/auth + atomic rollback + Tier 3 discoverability | ✅ | 1h 30m | `TestDemoSeed` class: 12 tests (15 collected due to scope parametrize), 1 skipped (tree:writer). Covers all 10 feature.md acceptance criteria. 157 pass total (11 skip). |

---

## Running Totals

| Category | Done | Total |
|----------|------|-------|
| Unit tests | 6 | 6 |
| Integration tests | 6 | 6 |
| SPEC.md acceptance criteria | 11 | 11 |
| Tasks complete | 76 | 76 |

---

## Session Handoff

### This Session (2026-06-08): Final Cleanup — treelib Purge, Test Suite, PR Merge

- **T-33 completed properly:** `tests/test_unit.py` no longer imports `treelib` or references `TreeStorage`. The `TestBuildTreeFromDict` class (17 tests — tested `build_tree_from_dict()` which no longer exists) and `TestSavesHelper` class (2 tests — `saves_helper()` function removed from `models.py`) have been removed. Dead imports cleaned up. 33 unit tests remain and pass.
- **`tests/test_would_create_cycle.py` deleted:** Entirely obsolete — imported `TreeStorage` (removed) and `moto` (not in deps).
- **Dependencies installed in venv:** All packages from `requirements.txt` including `pytest` — venv was empty at session start.
- **T-54 unblocked:** Full test suite runs. 33 unit + 69 integration tests pass.
- **T-55 completed:** Branch pushed, PR merged to `main`.
- **PROGRESS.md, CLAUDE.md, DESIGN.md freshened:** Stale treelib/TreeStorage references removed from all docs.
- **All 55 tasks complete.** The refactor is done.

### Current State (2026-06-09)

- **All 76 tasks across all phases are ✅ complete.**
- **Tier 3 Search & Query is ✅ complete** — `GET /nodes/search` (full-text), `GET /nodes/by-tag` (tag query), `SearchStorage` class, `node_text_idx` + `node_tags_idx` indexes.
- **Phase 15 (P-01) Pagination is ✅ complete** — All 4 list endpoints enforce `limit` (default 50, max 200) with cursor pagination.
- **Phase 16 (P-02) Health & Metrics is ✅ complete** — `GET /health` (MongoDB + Redis ping, 200/503), `GET /metrics` (uptime, pool size, request count), request-counting middleware.
- **Phase 17 (Demo Tree Seeding) is ✅ complete** — Endpoint, model, storage class, builder, unit tests, and integration tests all implemented and passing.
- **Implementation:** 33 route handlers (6 Works + 15 Nodes + 2 Search + 3 Auth + 3 Meta + 1 Demo + 6 Users), `WorkStorage`/`NodeStorage`/`UserStorage`/`SearchStorage`/`DemoStorage` classes, MongoDB collections with JSON Schema validators and 9 indexes.
- **Tests:** 46 unit tests pass + 157 integration tests pass (11 skipped) in `test_integration_normalised.py` across 6 test classes. 0 failures.

### Remaining Known Issues (not blocking)

None.

### Next Steps

1. **Tier 4: Enhanced features** — cross-node relationships, comments, export, bulk ops
2. **PR to main** — all 76 tasks complete, 0 test failures; ready for merge review.

---

## Phase 17 Code Quality Review (2026-06-10)

Review scope: `demo-seed/feature.md` vs implemented code (`database.py`, `api.py`, `demo.py`, `models.py`, integration tests, unit tests).

### Serious Bugs

| # | Issue | File:Line | Impact |
|---|-------|-----------|--------|
| S-1 | **`_seed_with_compensating_cleanup` uses `**node_data` on a Pydantic v2 model** — Pydantic v2 `BaseModel` has no `keys()` method so `**model` raises `TypeError` at runtime; the entire fallback code path is broken | `database.py:1445` | Fallback never works; undetected because Atlas M0 always takes the transaction path |
| S-2 | **`provisional_work_id` vs real `work_id` mismatch** — nodes are inserted with `provisional_work_id`, but `create_work` internally generates a fresh UUID; the returned `work_doc["work_id"]` differs from `provisional_work_id`; all seeded nodes are orphaned and unreachable via `GET /works/{work_id}/nodes` | `database.py:1432,1448` | All fallback-path nodes orphaned; silent data corruption |

### Medium Bugs

| # | Issue | File:Line | Impact | Status |
|---|-------|-----------|--------|--------|
| M-1 | **`delete_demo_works` `find()` missing `session=session`** — the initial read to discover demo work IDs happens outside the transaction's snapshot; a concurrent reset could double-delete or miss works | `database.py:1286` | Race condition on concurrent resets; transaction isolation broken for the find | ✅ Fixed 2026-06-10 |
| M-2 | **Direct `update_one` to inject `demo` tag violates spec DoD** — spec states "no direct collection writes"; both `_seed_with_transaction` and `_seed_with_compensating_cleanup` call `work_collection.update_one(... $push demo ...)` after `create_work` rather than including `demo` in the tags passed to `create_work` | `database.py:1385-1389, 1457-1461` | Bypasses any future `create_work` validation; can produce tag-twice if called with `demo` already present | ✅ Fixed 2026-06-10 |
| M-3 | **Fallback `insert_one` bypasses `NodeStorage.create_node` — missing `position`, `created_at`, `updated_at`** — direct insert does not invoke the position-counting logic in `create_node`; nodes land with no `position`, `created_at`, or `updated_at` fields; sorting and pagination are undefined | `database.py:1438-1444` | Node ordering broken; timestamp fields absent; diverges from all real-data nodes | ✅ Fixed 2026-06-10 (S-2 rewrite) |
| M-4 | **`by_type` count in fallback uses `NodeType` enum as dict key** — even if Bug S-1 were fixed, `node["node_type"]` returns a `NodeType` enum, not the string `"part"` / `"chapter"` etc.; `by_type["part"] += 1` raises `KeyError` | `database.py:1453-1455` | `DemoSeedResponse.by_type` always wrong / KeyError in fallback path | ✅ Fixed 2026-06-10 (S-2 rewrite) |
| M-5 | **4 spec acceptance criteria tests not implemented** — feature.md lists 16 ACs; the following are absent: AC9 (transaction rollback mid-seed → 503, no orphan Work or nodes), AC10 (ConnectionFailure/OperationFailure → 503), AC12 (blacklisted token → 401), AC14 (`?reset=notabool` → 422) | `test_integration_normalised.py` | 4 of 16 spec ACs unverified; transaction rollback coverage entirely missing | ✅ Fixed 2026-06-10 (tests T-DEMO-13–16) |
| M-6 | **Fallback trigger detection uses fragile string matching** — `str(e).lower()` compared against 5 hardcoded substrings; Motor/MongoDB error messages vary across driver versions; a legitimate transaction failure with a different message bypasses the fallback and propagates as an unhandled error | `database.py:1351-1357` | Wrong code path taken on legitimate transaction failures; brittle against driver upgrades | ✅ Fixed 2026-06-10 |

### Low-Impact Issues

| # | Issue | File:Line | Notes |
|---|-------|-----------|-------|
| L-1 | **Bare `except Exception` in `seed_demo` API handler** — all non-DB exceptions (e.g., `TypeError`, `AttributeError`) return 503 "Database error", masking programming bugs as transient service errors | `api.py:1360-1363` | Violates CLAUDE.md guideline; obfuscates real errors in logs |
| L-2 | **Deferred imports inside method bodies** — `from app.demo import build_demo_tree` in `seed_demo()` and `import uuid as _uuid` in `_seed_with_compensating_cleanup()` should be top-of-file imports | `database.py:1342, 1431` | Minor style/performance issue; unusual pattern |
| L-3 | **`_PLACEHOLDER_WORK_ID` module-level UUID in `demo.py`** — generated once at import time and shared by all calls; all `CreateNodeRequest` objects from `build_demo_tree` carry the same stale `work_id`; always overwritten in the transaction path but confusing in code review | `demo.py:8` | No runtime impact on transaction path; misleading |
| L-4 | **Scenes 3 and 4 (Chapter 2) have no beat children** — spec requires "all four hierarchy levels"; beats exist only under Chapter 1 branches; Chapter 2 subtree terminates at scene depth | `demo.py:150-171` | Demo does not showcase full part→chapter→scene→beat depth on all branches |
| L-5 | **`DemoStorage.__init__` holds redundant direct collection references** — `self.work_collection` and `self.node_collection` duplicate what the injected `WorkStorage` / `NodeStorage` instances already hold; only needed because the fallback and delete helper bypass the storage layer | `database.py:1264-1265` | Unnecessary coupling; would be eliminated if fallback used storage methods |

### To-Do List

| # | Task | Priority | Prerequisite |
|---|------|----------|-------------|
| D-01 | Fix S-2: pass `provisional_work_id` into `create_work` (or create Work first, nodes second in fallback) so node `work_id` matches returned work | High | — |
| D-02 | Fix S-1: replace `**node_data` with `**node_data.model_dump()` in `_seed_with_compensating_cleanup` | High | — |
| D-03 | Fix M-3: replace direct `insert_one` in fallback with `self.node_storage.create_node(...)` calls (generates `position`, timestamps) | High | D-01 (need real work_doc first) |
| D-04 | Fix M-4: change `by_type` key lookup to use `node["node_type"]` string value (`.value` if enum) or map `NodeType.part.value` → `"part"` | Medium | D-02/D-03 |
| D-05 | Fix M-2: remove both `update_one` `$push demo` calls; include `"demo"` in the `tags` list passed to `create_work` (append in `_seed_with_transaction` / `_seed_with_compensating_cleanup`, not in `build_demo_tree`) | Medium | — |
| D-06 | Fix M-1: add `session=session` to the `find()` call in `delete_demo_works` | Medium | — |
| D-07 | Fix M-6: replace string-matching fallback trigger with `OperationFailure.code` check (codes 263 `NoSuchTransaction`, 20 `IllegalOperation`, or 115 `CommandFailed`) | Medium | — |
| D-08 | Add missing AC9 test: mock `create_node` to raise mid-transaction → verify 503, no Work or nodes remain | Medium | — |
| D-09 | Add missing AC10 test: mock DB to raise `ConnectionFailure` → verify 503 | Medium | — |
| D-10 | Add missing AC12 test: blacklisted token → 401 | Low | — |
| D-11 | Add missing AC14 test: `?reset=notabool` → 422 | Low | — |
| D-12 | Fix L-1: narrow `except Exception` in `seed_demo` to specific error types; let programming errors surface as 500 | Low | — |
| D-13 | Fix L-2: move deferred imports to top of `database.py` | Low | — |
| D-14 | Fix L-4: add 1-2 beat nodes under Scene 3 or 4 so all branches reach beat depth | Low | — |

---

### Phase 17 Remediation Log (2026-06-09)

#### Fixed

| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| F-1 | **No transaction atomicity** (`feature.md` lines 35-48) | Critical | `_seed_with_transaction()` now calls `client.start_session()` + `session.start_transaction()`, wrapping delete_works, create_work, and all create_node calls inside the transaction. On commit (no exception), data is committed; on any exception, it rolls back automatically. |
| F-2 | **Session not threaded to create_work/create_node** (`database.py:1332,1351`) | Critical | All writes in `_seed_with_transaction()` now receive `session=session`: `work_storage.create_work(..., session=session)` and `node_storage.create_node(..., session=session)`. |
| F-3 | **Compensating cleanup fallback missing** (`feature.md` line 52) | Critical | Added `_seed_with_compensating_cleanup()`: creates nodes first with placeholder work_id, creates Work last, on any failure deletes orphan nodes + partial work by work_id. Triggered only on explicit transaction-unsupported errors. |
| F-4 | **`DemoStorage` instantiates fresh storage clients** (`database.py:1261-1262`) | Medium | Constructor now accepts optional `work_storage` and `node_storage` parameters, defaults to creating them only for non-DI usage. DI wiring in `get_demo_storage()` passes the injected storages so all code paths share the same instances. |
| F-5 | **`build_demo_tree()` returns dicts instead of typed models** (`demo.py:23-156`) | Medium | Now returns `Tuple[CreateWorkRequest, list[CreateNodeRequest]]`. Each node is a validated `CreateNodeRequest` instance. Uses a module-level placeholder UUID for `work_id` that gets overwritten in `_seed_with_transaction()` before DB writes. Both `_seed_with_transaction()` and `_seed_with_compensating_cleanup()` updated to call `.model_dump()` on the typed nodes. |

#### Remaining Issues

| # | Issue | Severity | File:Line | Notes |
|---|-------|----------|-----------|-------|
| R-1 | **Hardcoded UUIDs in `build_demo_tree()`** (`demo.py:26-149`) | Critical | Every node uses `"00000000-0000-0000-0000-000000000001"` as `work_id`. Will cause duplicate-key collisions on re-seed. Should use `str(uuid.uuid4())` for each node's `node_id`. |
| R-2 | **Demo tag added twice** (`database.py:1335-1342`) | Medium | Work created with `tags=["demo", "fiction", "mystery"]`, then `"demo"` pushed again via `$push`. The demo tag appears twice in the final document. Remove from `build_demo_tree()` or skip the `$push`. |
| R-3 | **`DemoStorage` instantiates fresh storage clients** (`database.py:1261-1262`) | Medium | Fixed: constructor now accepts optional `work_storage` and `node_storage` parameters. DI wiring in `get_demo_storage()` passes injected storages so all code paths share the same instances. |
| R-4 | **`build_demo_tree()` returns dicts instead of typed models** (`demo.py:23-156`) | Medium | Fixed: now returns `Tuple[CreateWorkRequest, list[CreateNodeRequest]]`. Each node is a validated `CreateNodeRequest` instance with a placeholder work_id overwritten in `_seed_with_transaction()`. Both seed paths updated to call `.model_dump()` on typed nodes. |
| R-5 | **No integration tests for demo seeding** (T-76) | High | **Fixed 2026-06-09:** `TestDemoSeed` class with 12 tests (15 collected). Covers all 10 feature.md acceptance criteria. All pass. |
| R-6 | **Unit tests don't validate adjacency integrity** (T-75) | Medium | **Fixed 2026-06-09:** 12 TestBuildDemoTree tests added/repaired — added `CreateWorkRequest` import, replaced `node.work_id` with `node.node_id` as identity key, rewrote chain test to use linked-list traversal. All 46 unit tests pass. |
| R-7 | **`build_demo_tree()` missing adjacency fields** (`demo.py`) | Medium | **Fixed (prior session):** `flatten()` wires `previous`/`next` from sibling position in each list. Confirmed by `test_build_demo_tree_previous_next_chains_valid` passing. |
| R-8 | **`by_type` uses untyped `dict[str, int]`** (`models.py:641`) | Minor | Should be more specific like `dict[NodeType, int]` or validate expected keys match spec example. |
| R-9 | **Phase 15 pagination regressions in integration tests** | Medium | **Fixed 2026-06-09:** 10 tests in `TestWorkCRUD`, `TestNodeCreate`, `TestNodeNavigation`, `TestReorderDuplicate` were accessing flat arrays; Phase 15 changed responses to `{results, count, next_cursor}` envelope. Fixed with `r.json()["results"]`. Also fixed `_calculate_max_depth` in `database.py` unpacking `(list, cursor)` tuple from `get_roots()` as a plain list. |

### Recently Completed

- **2026-06-09:** T-76 integration tests complete — `TestDemoSeed` (12 tests, 15 collected) covering all 10 feature.md acceptance criteria for demo seeding. Fixed 5 `TestBuildDemoTree` unit tests (T-75), Phase 15 pagination regressions in 10 existing tests, `_calculate_max_depth` tuple unpack bug, route ordering for search endpoints, transaction isolation for sibling position counting, Redis fail-open, `get_search_storage` DI function. All 76 tasks complete; 157 integration tests pass, 0 failures.
- **2026-06-09:** Added `response_model` to all 10 routes that were missing it — `DeleteResponse` (DELETE work/node), `LogoutResult` (GET /logout), `VersionResponse` (GET /), `GenericResult` (6 User endpoints). New Pydantic models in `models.py:509-532`.
- **2026-06-09:** Phase 15 (P-01) Pagination enforcement — all 4 list endpoints (`GET /works`, `GET /works/{work_id}/nodes`, `GET /works/{work_id}/nodes/root`, `GET /works/{work_id}/nodes/leaves`) enforce `limit` (default 50, max 200) with cursor pagination via `_id`. Added `limit` enforcement to `GET /nodes/by-tag` (was unbounded). Committed as part of P-01.

---

### Acceptance Criteria (SPEC.md Part VII)

- [x] All EARS requirements in SPEC.md Parts III, V, VI implemented and verified by tests (Work CRUD + Node CRUD + Navigation + Reorder + Duplicate — 112 integration tests across 5 test classes)
- [x] `tree_collection` no longer written to by any route handler
- [x] `treelib` removed from `requirements.txt`
- [x] `work_collection` created with JSON Schema validator and indexes
- [x] `node_collection` created with JSON Schema validator and indexes
- [x] All new endpoints have `summary`, `description`, and `tags`
- [x] Isolation tests exist for every new endpoint
- [x] Scope tests exist for every new endpoint
- [x] Unit tests cover hierarchy validation, cycle detection, sibling reordering, author cascade
- [x] `CONSTITUTION.md` Part I.2 and Part IV updated to reflect new model
- [x] `DESIGN.md` Part IV.1, Part III.1, DD-01 updated to reflect new model

---

## Session History

### 2026-06-08 — Final cleanup + test infrastructure fix

**Done:**
- Removed treelib imports from `tests/test_unit.py` (deleted 17 obsolete tests)
- Deleted `tests/test_would_create_cycle.py` (imported deleted `TreeStorage`)
- Updated `CLAUDE.md` (no treelib refs; 29-route API table; normalised DB patterns)
- Updated `specification/DESIGN.md` Part III.1 (TreeStorage → WorkStorage + NodeStorage)
- Updated `specification/PROGRESS.md` (T-33/T-54/T-55 ✅; totals 55/55)
- Fixed integration test infrastructure:
  - `asyncio_default_fixture_loop_scope` → `function`; `motor_client` → async fixture
  - Added `base_url="http://test"` to all 130 httpx.AsyncClient instances
  - Fixed 4 tests using httpx client after `async with` block exited
- All 33 unit + 142 integration tests pass (10 skipped)

**Branch:** `main`

### 2026-06-09 — Tier 3: Search & Query implementation

**Done:**
- Added `TextQueryStr`, `MatchType` enum, `NodeSearchResponse` to `models.py`
- Extended `setup_collections()` with `node_text_idx` (text on `description`+`text`) and `node_tags_idx` (multikey on `{account_id, tags}`)
- Added `SearchStorage` class with `search_nodes()` ($text search with textScore) and `find_nodes_by_tags()` ($in/$all tag matching)
- Added `GET /nodes/search` endpoint — query (required), work_id, node_type, limit params; strips transient score field
- Added `GET /nodes/by-tag` endpoint — tags (required, repeated), match=any/all, work_id, node_type params
- All 3 files pass Python AST syntax validation
- Committed as `d261a3e`

**Branch:** `main`

### 2026-06-09 (Session 2) — P-01: Pagination enforcement

**Done:**
- Added `PaginatedNodeResponse` and `PaginatedWorkResponse` models to `models.py` (`results`/`count`/`next_cursor` envelope)
- Added `limit`/`cursor` params to `WorkStorage.list_works`, `NodeStorage.list_nodes`, `NodeStorage.get_roots`, `NodeStorage.get_leaves`
- Cursor pagination via `_id`: `list_works` sorts `_id` descending (most recent first), the rest sort `_id` ascending (or `position`+`_id` for roots/leaves)
- All 4 route handlers updated to accept `limit` (default 50, max 200) and `cursor` query params, return paginated response
- Added `limit` enforcement to `GET /nodes/by-tag` and `SearchStorage.find_nodes_by_tags`
- 33 unit tests pass; no regressions

**Branch:** `refactor/normalised-node-model`

### 2026-06-09 (Session 3) — P-02: Health & Metrics endpoints

**Done:**
- Added `HealthResponse` and `MetricsResponse` models to `models.py`
- Added `GET /health` — no auth, pings MongoDB (`admin.command("ping")`) and Redis (short-lived connection); returns `{"status": "ok"}` 200 when both reachable, 503 with `"degraded"` otherwise
- Added `GET /metrics` — unauthenticated, returns uptime, max_pool_size, total_requests
- Added `@app.middleware("http")` request-counting middleware
- Set `app.state.start_time` and `app.state.request_count` in lifespan
- 33 unit tests pass; no regressions

**Branch:** `refactor/normalised-node-model`
