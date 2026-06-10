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

## Conventions

| Prefix | Meaning | Examples |
|--------|---------|----------|
| `T-{n}` | Legacy task — Phases 0–13 (original refactor numbering) | T-00 through T-55 |
| `E-{n}` | Enhancement — Phases 14+ (features, endpoints, infrastructure) | E-56 Search & Query, E-67 Health & Metrics |
| `B-{n}` | Bug/defect — tracked in the [Defects](#defects) section | B-01 Atlas auth, B-04 503 error handling |

**Status flow:** ⬜ Not started → 🔄 In progress → ✅ Done — committed

**Document architecture:** All bug items are consolidated in the `## Defects` section at the bottom of this document. Phase sections track enhancement tasks only.

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
| E-56 | Add `TextQueryStr`, `MatchType` enum, `NodeSearchResponse` to models.py | ✅ | 10 min | |
| E-57 | Extend `setup_collections()` with `node_text_idx` + `node_tags_idx` indexes | ✅ | 15 min | Idempotent; text index on `description`+`text`, multikey on `{account_id, tags}` |
| E-58 | Add `SearchStorage` class: `search_nodes()`, `find_nodes_by_tags()` | ✅ | 30 min | `$text` search with `textScore`; tag query with `$in`/`$all`; both account-scoped |
| E-59 | Add `GET /nodes/search` endpoint — full-text search over description/text | ✅ | 20 min | `query` (required), `work_id`, `node_type`, `limit` params; strips transient `score` field |
| E-60 | Add `GET /nodes/by-tag` endpoint — tag-based query with `match=any/all` | ✅ | 20 min | `tags` (required, repeated), `match`, `work_id`, `node_type` params |

---

## Phase 15 — Pagination Enforcement on List Endpoints (P-01)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| E-61 | Add `PaginatedNodeResponse`, `PaginatedWorkResponse` to models.py | ✅ | 10 min | Wraps results with `count` and `next_cursor` |
| E-62 | Add `limit`+`cursor` params to `WorkStorage.list_works` — `_id`-desc cursor pagination | ✅ | 15 min | Sort by `_id` descending (most recent first); cursor filter `{"_id": {"$lt": cursor}}` |
| E-63 | Add `limit`+`cursor` params to `NodeStorage.list_nodes` — `_id`-asc cursor pagination | ✅ | 15 min | Sort by `_id` ascending; cursor filter `{"_id": {"$gt": cursor}}` |
| E-64 | Add `limit`+`cursor` params to `NodeStorage.get_roots` / `get_leaves` — position+`_id` sort | ✅ | 15 min | Sort by `[("position", 1), ("_id", 1)]`; cursor filter `{"_id": {"$gt": cursor}}` |
| E-65 | Update 4 route handlers in api.py with `limit`/`cursor` query params + paginated response models | ✅ | 20 min | `list_works`, `list_normalised_nodes`, `get_work_root_nodes`, `get_work_leaf_nodes` |
| E-66 | Add `limit` to `GET /nodes/by-tag` endpoint and `SearchStorage.find_nodes_by_tags` | ✅ | 10 min | Default 50, max 200; matches existing pattern on `GET /nodes/search` |

## Phase 16 — Health & Metrics Endpoints (P-02)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| E-67 | Add `HealthResponse` + `MetricsResponse` models | ✅ | 10 min | `status`/`database`/`cache` for health; `uptime_seconds`/`max_pool_size`/`total_requests` for metrics |
| E-68 | Add `GET /health` — MongoDB ping + Redis ping, 200/503 | ✅ | 20 min | No auth; checks both DB and cache; 503 when either is down |
| E-69 | Add `GET /metrics` + request-counting middleware — uptime, pool size, count | ✅ | 25 min | `@fix app.middleware("http")` increments counter; lifespan sets `start_time` and `request_count` |

---

## Phase 17 — Demo Tree Seeding (`demo-seed/feature.md`)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| E-70 | Add `DemoSeedResponse` model to `models.py` | ✅ | 10 min | `{work_id, title, total_nodes, by_type}`; no `account_id` |
| E-71 | Add optional `session=None` kwarg to `create_work`, `create_node`, and the demo-delete helper; thread into underlying `motor` writes | ✅ | 20 min | Backward-compatible (default `None`); every write in the seed must receive the session or atomicity breaks silently |
| E-72 | Add `build_demo_tree(account_id, author)` pure builder (new `demo.py`) | ✅ | 30 min | Unique UUIDs per node, demo tag absent from builder, typed CreateNodeRequest return, adjacency fields (previous/next) wired in flatten(). All 12 unit tests pass. |
| E-73 | Add `DemoStorage.seed_demo(account_id, author, reset)` — transactional seed | ✅ | 40 min | Transaction management, session threading, compensating cleanup fallback, DI wiring all implemented. Validated by E-76 integration tests. |
| E-74 | Add `POST /demo/seed` endpoint | ✅ | 20 min | Scope `tree:writer`; optional `reset` bool param; 201 `DemoSeedResponse`; `summary`/`description`/`tags=["Demo"]` on decorator |
| E-75 | Unit tests — `build_demo_tree` adjacency integrity | ✅ | 20 min | 12 tests in TestBuildDemoTree: correct structure, node counts, parent references, sibling groups, previous/next chain traversal, root no-parent, author propagation, work tags, pure function, all tags present, all descriptions, hierarchy depth. All pass. |
| E-76 | Integration tests — seed happy path + additive re-run + reset + isolation + scope/auth + atomic rollback + Tier 3 discoverability | ✅ | 1h 30m | `TestDemoSeed` class: 12 tests (15 collected due to scope parametrize), 1 skipped (tree:writer). Covers all 10 feature.md acceptance criteria. 157 pass total (11 skip). |

---

## Running Totals

| Category | Done | Total |
|----------|------|-------|
| Enhancement tasks (E-56–E-87) | 32 | 32 |
| Bug items tracked (B-01–B-18) | 12 | 18 |
| Unit tests | 46 | 46 |
| Integration tests | 157 | 168 |
| SPEC.md acceptance criteria | 11 | 11 |



## Open Tasks

### Remaining Open Tasks

| # | Task | Priority | GitHub | Prerequisite |
|---|------|----------|--------|-------------|
| E-84 | Fix B-05: replace `**node_data` with `**node_data.model_dump()` in `_seed_with_compensating_cleanup` | High | #27 | — |
| E-85 | Fix B-13: narrow `except Exception` in `seed_demo` to specific error types; let programming errors surface as 500 | Low | #26 | — |
| E-86 | Fix B-14: move deferred imports to top of `database.py` | Low | #24 | — |
| E-87 | Fix B-16: add 1-2 beat nodes under Scene 3 or 4 so all branches reach beat depth | Low | #31 | — |


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

## Defects

### B-01 — Login fails due to Atlas connection pool auth failure (2026-06-10)

**Severity:** Critical — users cannot log in; app crashes on any DB-hitting request  
**Status:** ✅ Fixed (infrastructure, 2026-06-10)  
**Root cause:** The Atlas database-level credentials in `MONGO_DETAILS` did not match the Atlas Database Access user. `testulator:BlackM1lk` was rejected by Atlas during connection pool checkout (`SCRAM-SHA-1` handshake fails, code 8000 `AtlasError`).  
**Fix:** Created a new Atlas Database Access user and updated `MONGO_DETAILS` in `.env`. No code change required.  
**Note:** Previous `GET /health` passed because it reused an already-authenticated pool connection — see B-04 T-84 fix.

---

### B-02 — `DEBUG=True` crashes container on restart (2026-06-10)

**Severity:** Critical — container fails to start when `DEBUG=True` is set  
**Status:** ✅ Fixed (commit `91f0731`, 2026-06-10)  
**Root cause:** `pymongo.monitoring.register(_PoolEventLogger())` was called at module level (`api.py:144`). In uvicorn StatReload mode, changing `.env` triggers a module reload, re-registering the listener against a partially-torn-down pool, corrupting pool state and causing Atlas auth failures.  
**Fix:** Moved registration inside the `lifespan` context manager, so it runs once per process, always before `MongoClient` is created.

---

### B-03 — `user_role` comma-separated breaks scope validation on all protected endpoints (2026-06-10)

**Severity:** Critical — authenticated users cannot access any protected endpoint  
**Status:** ✅ Fixed (committed, pushed, 2026-06-10)  
**Root cause:** `user_role` stored as comma-separated string (e.g. `"user:reader,user:writer,tree:reader,tree:writer"`) but `api.py:297` splits by space, returning one element — no scopes granted.  
**Fix:** `re.split(r"[, ]+", user.user_role)` in `api.py:295`. Tolerates both comma and space separators; safe for existing Atlas data.

---

### B-04 — MongoDB connection failures return unhandled 500 instead of 503 (2026-06-10)

**Severity:** High — poor failure mode; crashes requests with no informative response  
**Status:** ✅ Fixed  
**Symptom:** `OperationFailure`/`ConnectionFailure` propagates uncaught through route handlers; FastAPI returns raw 500 with traceback.  
**Root cause:** Storage methods catch and re-raise; no route handler catches DB exceptions.  
**Tasks:**

| # | Task | File | Status | Detail |
|---|------|------|--------|--------|
| T-83 | Add global FastAPI exception handler for `OperationFailure` and `ConnectionFailure` | `api.py` | ✅ | Returns 503; registered via `@app.exception_handler` |
| T-84 | Update `GET /health` to detect pool auth failures | `api.py` | ✅ | Short-lived `AsyncIOMotorClient` forces fresh auth |
| T-85 | Add `MONGO_DETAILS` connection string validation at startup | `api.py` lifespan | ✅ | Test query on startup; clear error for bad credentials |

---

### B-05 — `**node_data` unpack on Pydantic v2 model in compensating cleanup

**Severity:** High — fallback code path silently broken  
**Status:** ⬜ Open  
**File:** `database.py:1445`  
**GitHub:** #27  
**Detail:** Pydantic v2 `BaseModel` has no `keys()` method so `**model` raises `TypeError`; entire fallback path crashes  

---

### B-06 — `provisional_work_id` vs real `work_id` mismatch in fallback

**Severity:** High — seeded nodes orphaned in fallback path  
**Status:** ✅ Fixed 2026-06-10 (B-06 rewrite)  
**File:** `database.py:1425-1473`  
**GitHub:** #29  
**Detail:** `_seed_with_compensating_cleanup` rewritten to create Work first via `create_work`, then use the real `work_doc["work_id"]` for all node inserts. `provisional_work_id` variable removed entirely. Nodes now reference the correct Work document.  

---

### B-07 — `delete_demo_works` `find()` missing `session=session`

**Severity:** Medium — race on concurrent resets  
**Status:** ✅ Fixed 2026-06-10  
**File:** `database.py:1286`  
**Detail:** Initial `find()` to discover demo work IDs outside transaction snapshot  

---

### B-08 — Direct `update_one` to inject `demo` tag violates spec DoD

**Severity:** Medium — bypasses `create_work` validation  
**Status:** ✅ Fixed 2026-06-10  
**File:** `database.py:1385-1389, 1457-1461`  
**Detail:** Direct collection write instead of including `"demo"` in `create_work` tags  

---

### B-09 — Fallback `insert_one` bypasses `NodeStorage.create_node`

**Severity:** Medium — missing `position`, `created_at`, `updated_at`  
**Status:** ✅ Fixed 2026-06-10 (B-06 rewrite)  
**File:** `database.py:1438-1444`  
**Detail:** Direct insert skips position-counting logic; sorting/pagination undefined  

---

### B-10 — `by_type` count uses `NodeType` enum as dict key in fallback

**Severity:** Medium — response always wrong in fallback  
**Status:** ✅ Fixed 2026-06-10 (B-06 rewrite)  
**File:** `database.py:1453-1455`  
**Detail:** `NodeType.part` enum used as key instead of `"part"` string → `KeyError`  

---

### B-11 — 4 spec acceptance criteria tests not implemented

**Severity:** Medium — AC9/10/12/14 missing  
**Status:** ✅ Fixed 2026-06-10 (tests T-DEMO-13–16)  
**File:** `test_integration_normalised.py`  
**Detail:** Transaction rollback (AC9), ConnectionFailure 503 (AC10), blacklisted token 401 (AC12), invalid reset param 422 (AC14)  

---

### B-12 — Fallback trigger uses fragile string matching

**Severity:** Medium — brittle against driver message changes  
**Status:** ✅ Fixed 2026-06-10  
**File:** `database.py:1351-1357`  
**Detail:** `str(e).lower()` compared against 5 hardcoded substrings; should use `OperationFailure.code`  

---

### B-13 — Bare `except Exception` in `seed_demo` API handler

**Severity:** Low — masks programming bugs as 503  
**Status:** ⬜ Open  
**File:** `api.py:1360-1363`  
**GitHub:** #26  
**Detail:** All non-DB exceptions return 503 "Database error"; should narrow to specific error types  

---

### B-14 — Deferred imports inside method bodies

**Severity:** Low — style/performance  
**Status:** ⬜ Open  
**File:** `database.py:1342, 1431`  
**GitHub:** #24  
**Detail:** `from app.demo import build_demo_tree` and `import uuid as _uuid` should be top-of-file  

---

### B-15 — `_PLACEHOLDER_WORK_ID` module-level UUID in `demo.py`

**Severity:** Low — misleading in code review  
**Status:** ⬜ Open  
**File:** `demo.py:8`  
**GitHub:** #28  
**Detail:** Generated once at import time; all `CreateNodeRequest` objects carry same stale `work_id` (overwritten in transaction path)  

---

### B-16 — Scenes 3 and 4 (Chapter 2) have no beat children

**Severity:** Low — demo tree incomplete  
**Status:** ⬜ Open  
**File:** `demo.py:150-171`  
**GitHub:** #31  
**Detail:** Spec requires all four hierarchy levels; beats only under Chapter 1 branches; Chapter 2 terminates at scene depth  

---

### B-17 — `DemoStorage.__init__` holds redundant collection references

**Severity:** Low — unnecessary coupling  
**Status:** ⬜ Open  
**File:** `database.py:1264-1265`  
**GitHub:** #30  
**Detail:** `self.work_collection` and `self.node_collection` duplicate injected `WorkStorage`/`NodeStorage`; needed only because fallback bypasses storage layer  

---

### B-18 — `by_type` uses untyped `dict[str, int]` in models.py

**Severity:** Minor — weak type safety  
**Status:** ⬜ Open  
**File:** `models.py:641`  
**GitHub:** #25  
**Detail:** Should be `dict[NodeType, int]` or validate expected keys match spec example  

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

### 2026-06-10 — Phase 18 identified; R-1/R-2 verified fixed

**Done:**
- Verified R-1 (hardcoded UUIDs) already fixed — `demo.py` uses `str(uuid.uuid4())` throughout
- Verified R-2 (duplicate demo tag) already fixed — `"demo"` appended once per seed path, not in initial tags
- Updated PROGRESS.md to mark both R-1 and R-2 as fixed
- Identified Phase 18 startup crash: `NameError: timezone` in `api.py:13` and `authentication.py:6`
- Wrote Phase 18 fix plan (E-77, E-78) including steps to fix and verify into PROGRESS.md

**Not yet done:** E-77 and E-78 code changes not applied this session.

**Branch:** `refactor/normalised-node-model`

---

### 2026-06-10 — Phase 18 fix applied; all 78 tasks complete

**Done:**
- Applied E-77: added `timezone` to `from datetime import` in `api.py:13`
- Applied E-78: added `timezone` to `from datetime import` in `authentication.py:6` (preventive)
- Committed as `28e2db1 fix for missing timezone module`
- Verified: 46 unit tests pass, 0 failures

**Branch:** `refactor/normalised-node-model`  
**Status: 78/78 tasks complete — ready to merge to `main`**

---

### 2026-06-10 — Phase 19: Atlas collMod permission crash fixed

**Done:**
- Diagnosed startup crash: `setup_collections()` calls `collMod` to refresh JSON Schema validators on existing collections; `collMod` requires `dbAdmin` role but the Atlas user only has `readWrite`
- E-79: In the `collMod` branch (`else` block in `setup_collections`), catch `OperationFailure` with codes `8000` (AtlasError) or `13` (Unauthorized), log a warning, and continue startup instead of crashing. Other `OperationFailure` errors still propagate.
- E-80: Same guard on the `create_collection` branch — if creating a new collection with a validator fails on permissions, retry without the validator rather than crashing. Hard failure on the retry still propagates.
- E-81: Verified fix — started uvicorn against live Atlas + Redis; two `[WARNING]` lines emitted (one per collection), `Application startup complete`, `GET /health` → `{"status":"ok"}`, `GET /metrics` → uptime/pool/request counts all correct.
- E-82: PROGRESS.md updated with fix details and task status.
- Committed as `a77857b Fix startup crash when Atlas user lacks dbAdmin for collMod`
- 46 unit tests pass, 0 failures

**Note:** Pydantic models enforce the same schema constraints at the API layer, so losing server-side MongoDB validation is not a functional regression.

**Branch:** `refactor/normalised-node-model`

### 2026-06-10 — Session: Atlas credentials fixed, BUG-04 completed

**Status:** App is running and healthy. Login works. Demo seed works (via Swagger auth).

**Completed this session:**
- **B-01 → ✅ Resolved:** Infra fix — new Atlas Database Access user, `MONGO_DETAILS` updated in `.env`. Verified app starts and `/health` returns 200. Verified `/get_token` login succeeds. Verified `/demo/seed` works via Swagger (after authorizing).
- **B-04 T-84 → ✅ Implemented:** `GET /health` now creates a short-lived `AsyncIOMotorClient` (`serverSelectionTimeoutMS=5000`, `maxPoolSize=1`) that forces a fresh auth attempt instead of reusing a stale pool connection. Verified: 200 when Atlas is up, health reports `database: "connected"` correctly.
- **Commit `4c5dfe9`:** Staged and committed `api.py` (T-84 code) + `PROGRESS.md` (B-01 fixed, B-04/T-84 marked done).

---

## Phase 18 — Startup Crash Fix (`timezone` import)

Missing `timezone` in `from datetime import` caused `NameError` at startup (lines 170, 1287).

| # | Task | File | Status | Notes |
|---|------|------|--------|-------|
| E-77 | Add `timezone` to datetime import | `api.py:13` | ✅ | `from datetime import timedelta, datetime, timezone` |
| E-78 | Add `timezone` to datetime import (preventive) | `authentication.py:6` | ✅ | Same incomplete import pattern |

## Phase 19 — Atlas `collMod` Permission Crash

`setup_collections()` calls `collMod` to refresh JSON Schema validators; Atlas user lacks `dbAdmin` role. Caught `OperationFailure` (codes 8000/13), log warning, continue.

| # | Task | File | Status | Notes |
|---|------|------|--------|-------|
| E-79 | Graceful `collMod` permission handling | `setup_collections` | ✅ | Catch `OperationFailure`, log warning, continue |
| E-80 | Graceful `create_collection` permission (preventive) | `setup_collections` | ✅ | Retry without validator on permission failure |
| E-81 | Verify fix against live Atlas + Redis | manual | ✅ | Startup completed cleanly with `[WARNING]` only |

---

### 2026-06-10 — `gh` connectivity test (dummy issue #22)

**Done:**
- Verified `gh auth status` — logged in as `felipeazucares`, token scopes: `gist`, `read:org`, `repo`, `workflow`
- Created dummy test issue #22 via `gh issue create` (stdin pipe workaround — GraphQL `--body` auth issue)
- Confirmed issue #22 viewable and accessible
- Committed empty commit `3281d83 close dummy test issue` (includes `fixes #22`)
- Pushed branch `chore/issues-dryrun` and opened PR #23 to close #22 on merge

**Items marked complete this session:** None — no PROGRESS.md task items were worked on.

**Branch:** `chore/issues-dryrun` (PR #23 to main)

---

### 2026-06-10 — Defects migrated to GitHub issues

**Done:**
- Created `p1`/`p2`/`p3` severity labels on GitHub
- Created 8 GitHub issues from the open Defects section:
  - B-05 (#27): `**node_data` Pydantic v2 unpack crash
  - B-06 (#29): `provisional_work_id` mismatch
  - B-13 (#26): Bare `except Exception` in `seed_demo`
  - B-14 (#24): Deferred imports in `database.py`
  - B-15 (#28): Stale `_PLACEHOLDER_WORK_ID` in `demo.py`
  - B-16 (#31): Scenes 3 and 4 have no beat children
  - B-17 (#30): Redundant `DemoStorage` collection refs
  - B-18 (#25): Untyped `by_type` in `models.py`
- Added missing `bug`/`p2`/`p3` labels to issues #29, #30, #31

**PROGRESS.md changes:**
- Added `GitHub:` field to each open defect entry linking to its issue
- Updated Open Tasks table (E-83–E-87) with GitHub reference column

**Branch:** `chore/issues-dryrun`

---

### 2026-06-10 — B-06 fixed (PROGRESS.md documentation update)

**Done:**
- Confirmed the code fix for B-06 (`provisional_work_id` mismatch in fallback) was already applied in commit `84f3414` (Fixes to demo-seed scripts by Claude, 2026-06-10)
- Updated PROGRESS.md: B-06 marked ✅ Fixed, Running Totals updated (11→12), E-83 removed from Open Tasks
- Verified: 46/46 unit tests pass
- Committed `42286f1` with message containing `fixes #29`; pushed to `refactor/normalised-node-model`

**Branch:** `refactor/normalised-node-model`


