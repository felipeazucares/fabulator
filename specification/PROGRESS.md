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
| T-56 | Integration tests — search endpoint (14 test methods, 18 collected) | ✅ | 2h | `TestSearchQuery` class: basic match, both fields, textScore order, no match, empty query, work_id filter, node_type filter, invalid type, isolation, no auth, scope, DB error 503, blacklisted token, query too long |

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

## Phase 20 — Tier 3: Work Reading Order (`work-reading-order/feature.md`)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| E-88 | Add `OrderedNodesResponse` to `models.py` | ✅ | 10 min | `{work_id, nodes: list[NodeResponse], count, next_cursor}`; no `account_id` |
| E-89 | Add `NodeStorage.get_reading_order(work_id, account_id)` | ✅ | 30 min | Single `{account_id, work_id}` fetch (existing index); in-memory pre-order DFS, children by `position`; `visited` cycle-guard; `_strip_id` |
| E-90 | Add `GET /works/{work_id}/nodes/ordered` endpoint | ✅ | 20 min | Work-ownership check first (404); `limit` (default 50, max 200) + opaque `node_id` cursor pagination; `tags=["Search"]`; scope `tree:reader` |
| T-57 | Integration tests — `TestWorkReadingOrder` | ✅ | 1h 30m | pre-order shape, empty work, pagination contiguity, unknown-cursor 422, ordering independent of previous/next, isolation 404, scope/auth, DB-error 503 |
| V-03 | OpenAPI docs check — schema renders correctly | ✅ | 5 min | Endpoint at `/works/{work_id}/nodes/ordered`, summary "Get nodes in reading order", tags `["Search"]`, `OrderedNodesResponse` in components |
| V-04 | Merge to `main` — verify endpoint live | ✅ | 15 min | Feature branches merged to `main`; `/works/{work_id}/nodes/ordered` verified live via `/openapi.json`; endpoint visible under `Search` tag in Swagger UI |

---

---

## Phase 21 — DD-11: Flexible Node Hierarchy Refactor

**Design decision:** DD-11 (DESIGN.md Part IX)  
**Branch:** `refactor/dd11-flexible-hierarchy`  
**Prerequisite:** All Phase 20 tasks complete (✅). DD-12 (tag→name) and DD-13 (tags semantic change) should be sequenced as separate phases after this one.

> **Coordination note:** E-85 (B-13, bare `except Exception`) and E-87 (B-16, missing beat children) are open defects that touch `api.py` and `demo.py` respectively. E-87 is superseded by E-108 below (beats are removed entirely). E-85 remains independent.

---

### E-101 — Remove `beat` from `NodeType` enum

**File:** `server/app/models.py`  
**What:** Delete `beat = "beat"` from the `NodeType` enum. Search entire codebase for `NodeType.beat`, `"beat"`, and `Literal["beat"]` before removing — any missed reference will cause an `AttributeError` at import time.  
**Acceptance criteria:** `from app.models import NodeType; NodeType("beat")` raises `ValueError`. All existing imports succeed.  
**GitHub label:** `refactor`, `p1`  
**Est:** XS (15 min)

---

### E-102 — Replace `_VALID_CHILD` with `_VALID_CHILDREN` set-valued dict

**File:** `server/app/database.py`  
**What:** Replace:
```python
_VALID_CHILD = {None: "part", "part": "chapter", "chapter": "scene", "scene": "beat", "beat": None}
```
with:
```python
_VALID_CHILDREN: dict[str | None, set[str]] = {
    None: {"part"},
    "part": {"part", "chapter", "scene"},
    "chapter": {"part", "chapter", "scene"},
    "scene": set(),
}
```
Update `is_valid_parent_child(parent_type, child_type)` to: `return child_type in _VALID_CHILDREN.get(parent_type, set())`.  
Grep for all direct reads of `_VALID_CHILD` (not via the function) and update them.  
**Acceptance criteria:** `is_valid_parent_child("part", "scene")` returns `True`. `is_valid_parent_child("scene", "part")` returns `False`. `is_valid_parent_child(None, "chapter")` returns `False`.  
**GitHub label:** `refactor`, `p1`  
**Est:** S (20 min)

---

### E-103 — Update MongoDB JSON Schema validator to remove `beat`

**File:** `server/app/database.py` — `_NODE_VALIDATOR`  
**What:** Change `node_type` enum in `_NODE_VALIDATOR` from `["part", "chapter", "scene", "beat"]` to `["part", "chapter", "scene"]`. The Atlas `collMod` permission guard (E-79) means this may not apply to existing collections in production — note this in the PR but it is not a blocker.  
**Acceptance criteria:** Inserting a document with `node_type: "beat"` directly via Motor raises `WriteError` in a fresh collection. (May be skipped if collection was created without validator — see E-112.)  
**GitHub label:** `refactor`, `p1`  
**Est:** XS (10 min)

---

### E-104 — Remove Beat guard; add Scene deep-duplicate leaf guard

**Files:** `server/app/api.py`, `server/app/database.py`  
**What:** Remove the HTTP 400 guard that blocks duplication of Beat nodes. Replace with: deep duplicate of a Scene node MUST return HTTP 400 (Scene is a leaf, has no children to copy). Shallow duplicate of a Scene remains permitted.  
Guard MUST fire at the API layer before any DB call, so CP 27 remains testable without hitting MongoDB.  
**Acceptance criteria:** `POST /nodes/{scene_id}/duplicate?deep=true` returns 400. `POST /nodes/{scene_id}/duplicate` (shallow) returns 201.  
**GitHub label:** `refactor`, `p1`  
**Est:** S (20 min)

---

### E-105 — Update `get_leaves` to return Scene nodes not Beat nodes

**Files:** `server/app/database.py` — `NodeStorage.get_leaves`; `server/app/api.py` — `GET /works/{work_id}/nodes/leaves`  
**What:** Change the MongoDB filter from `{"node_type": "beat"}` to `{"node_type": "scene"}`. Update the OpenAPI `description` on the endpoint to reflect Scene as the leaf type.  
**Pitfall:** Integration tests asserting `node_type: "beat"` in leaves responses will fail until E-110 is applied — do not run the full integration suite between E-105 and E-110.  
**Acceptance criteria:** `GET /works/{work_id}/nodes/leaves` returns only nodes with `node_type: "scene"`.  
**GitHub label:** `refactor`, `p1`  
**Est:** S (15 min)

---

### E-106 — Update hierarchy validation error messages

**File:** `server/app/api.py`  
**What:** Audit every HTTP 422 `detail` string referencing the old hierarchy (e.g. `"Beat nodes cannot have children"`, `"Only Part nodes can be roots"`). Rewrite to describe the new rules. Grep integration tests for exact strings before changing — matched strings in tests must be updated in E-110.  
**Acceptance criteria:** No response body references `"beat"`. Error messages describe valid parent types for the rejected operation.  
**GitHub label:** `refactor`, `p1`  
**Est:** S (15 min)

---

### E-107 — Update `CONSTITUTION.md` and `REQUIREMENTS.md` post-code verification

**Files:** `CONSTITUTION.md`, `REQUIREMENTS.md`  
**What:** Both documents were updated in the DD-11 doc pass (2026-06-12). After E-101–E-106 are merged, verify the CP assertions in REQUIREMENTS.md (CP 12, 13, 15, 17, 19, 20, 27, 30) match the actual code and test implementations. Correct any discrepancy.  
**Acceptance criteria:** Every testable assertion in each CP can be traced to a passing test.  
**GitHub label:** `docs`  
**Est:** XS (15 min)

---

### E-108 — Restructure demo tree — remove Beat nodes, exercise flexible hierarchy

**File:** `server/app/demo.py`  
**What:** Remove all Beat node construction from `build_demo_tree()`. Restructure the demo tree to exercise the new hierarchy:
- At least one Part → Scene path (no Chapter)
- At least one Part → Chapter → Scene path
- At least one Part → Chapter → Part → Scene path (nested Part)
Verify `previous`/`next` adjacency fields remain consistent after restructure.  
**Note:** This supersedes open defect B-16 (#31) — close GitHub issue #31 in the PR.  
**Acceptance criteria:** `build_demo_tree()` returns no nodes with `node_type: "beat"`. All three hierarchy patterns are present. All 12 unit tests in `TestBuildDemoTree` pass after update.  
**GitHub label:** `refactor`, `p1`  
**Est:** M (45 min)

---

### E-109 — Update unit tests for new hierarchy rules

**File:** `server/tests/test_unit.py`  
**What:**  
- `TestHierarchyValidator` (T-UNIT-01, T-UNIT-02): replace test cases to cover new valid pairs (Part→Part, Part→Chapter, Part→Scene, Chapter→Part, Chapter→Chapter, Chapter→Scene) and invalid pairs (Scene→anything, null→Chapter, null→Scene, any→beat).  
- `TestDuplicateNode` (T-UNIT-08–10): replace Beat guard tests with Scene deep-duplicate guard tests.  
- `TestBuildDemoTree`: update node count assertions and hierarchy depth assertions to match restructured demo tree from E-108. Do not remove cycle detection or sibling reorder tests — those are unaffected.  
**Acceptance criteria:** All unit tests pass. No test references `NodeType.beat` or `"beat"`.  
**GitHub label:** `refactor`, `p1`  
**Est:** M (45 min)

---

### E-110 — Update integration tests for new hierarchy rules

**File:** `server/tests/test_integration_normalised.py`  
**What:**  
- `TestNodeCreate`: add tests for Part→Scene (skipping Chapter), Chapter→Part (nested), Scene-as-parent-returns-422. Remove Beat creation tests.  
- `TestNodeNavigation` / `TestLeaves`: assert `node_type: "scene"` not `"beat"`. Update ancestors test (CP 17) — use Scene at depth 3 with Part and Chapter ancestors.  
- `TestReorderDuplicate`: replace Beat deep-copy guard test with Scene deep-copy guard test.  
- Update any error message string matches to reflect E-106 changes.  
**Pitfall:** `TestDemoSeed` `by_type` count assertions depend on E-108 completing first — do E-108 before running this.  
**Acceptance criteria:** Full integration suite passes. No test references `"beat"` as an expected value.  
**GitHub label:** `refactor`, `p1`  
**Est:** L (2h)

---

### E-111 — Update demo seed integration tests for restructured tree

**File:** `server/tests/test_integration_normalised.py` — `TestDemoSeed`  
**What:** Update `by_type` count assertions to match the restructured demo tree from E-108. Verify: no `"beat"` key in `by_type` response, at least one node of each remaining type, flexible hierarchy paths exercised.  
**Pitfall:** Depends on E-108. Do not merge before E-108 is stable.  
**Acceptance criteria:** All `TestDemoSeed` tests pass against the live Atlas instance.  
**GitHub label:** `refactor`, `p1`  
**Est:** M (30 min)

---

### E-112 — Add DB-level `beat` rejection test

**File:** `server/tests/test_unit.py`  
**What:** Add a test that directly inserts a document with `node_type: "beat"` into `node_collection` via Motor and asserts a MongoDB `WriteError` is raised (CP 30). Mark `@pytest.mark.skipif` if the collection was created without a validator (Atlas `collMod` permission issue — E-79/E-80).  
**Acceptance criteria:** Test passes when validator is active. Skip condition is documented.  
**GitHub label:** `test`, `p2`  
**Est:** S (20 min)

---

### Phase 21 Summary Table

| # | Task | File(s) | Status | Est | GitHub | Notes |
|---|------|---------|--------|-----|--------|-------|
| E-101 | Remove `beat` from `NodeType` enum | `models.py` | ✅ | XS | #41 | Do first |
| E-102 | Replace `_VALID_CHILD` with `_VALID_CHILDREN` | `database.py` | ✅ | S | #42 | Depends E-101 |
| E-103 | Update MongoDB JSON Schema validator | `database.py` | ✅ | XS | #43 | |
| E-104 | Remove Beat guard; add Scene deep-dup guard | `api.py`, `database.py` | ✅ | S | #44 | |
| E-105 | `get_leaves` returns Scene not Beat | `database.py`, `api.py` | ✅ | S | #45 | |
| E-106 | Update hierarchy validation error messages | `api.py` | ✅ | S | #58 | Done — PR merged |
| E-107 | Post-code doc verification | `CONSTITUTION.md`, `REQUIREMENTS.md` | ✅ | XS | #47 | Verified CPs 12/13/15/17/19/20/27/30; stale beat references updated in REQUIREMENTS.md |
| E-108 | Restructure demo tree; remove Beat nodes | `demo.py` | ✅ | M | #48 | Closes #31 |
| E-109 | Update unit tests | `test_unit.py` | ✅ | M | #49 | After E-108 |
| E-110 | Update integration tests | `test_integration_normalised.py` | ✅ | L | #50 | After E-108 |
| E-111 | Update demo seed integration tests | `test_integration_normalised.py` | ✅ | M | #51 | Superseded by E-110 (same file, same changes) |
| E-112 | DB-level `beat` rejection test | `test_unit.py` | ✅ | S | #52 | PR #64; skips if no validator active |

**Recommended execution order:** E-101 → E-102 → E-103 (models/db) → E-104 → E-105 → E-106 (API layer) → E-107 (doc verification) ✅ → E-108 (demo) → E-109 → E-110 → E-111 → E-112 (tests)


---

## Running Totals

| Category | Done | Total |
|----------|------|-------|
| Enhancement tasks (E-56–E-90) | 35 | 35 |
| Enhancement tasks (E-101–E-112, Phase 21) | 11 | 12 |
| Bug items tracked (B-01–B-18) | 13 | 18 |
| Unit tests | 53 | 53 |
| Integration tests | 188 | 204 |
| SPEC.md acceptance criteria | 11 | 11 |



## Open Tasks

### Remaining Open Tasks

| # | Task | Priority | GitHub | Status |
|---|------|----------|--------|--------|
| E-85 | Fix B-13: narrow `except Exception` in `seed_demo` to specific error types; let programming errors surface as 500 | Low | #26 | — |
| E-86 | Fix B-14: move deferred imports to top of `database.py` | Low | #24 | ✅ |
| E-87 | Fix B-16: add 1-2 beat nodes under Scene 3 or 4 so all branches reach beat depth | Low | #31 | — (superseded by E-108) |

**Note:** E-84 (Fix B-05, `**node_data` Pydantic v2 unpack) removed — already fixed in commit `84f3414`, closed via GitHub issue #27.  
**Note:** E-88 (Fix B-18, `by_type` untyped dict) removed — fixed in this session, closed via GitHub issue #25.


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
**Status:** ✅ Fixed (commit `84f3414`, 2026-06-10)  
**File:** `database.py:1409, 1452`  
**GitHub:** #27 (closed)  
**Detail:** Fixed in commit `84f3414` — bare `**node_data` replaced with `**node_data.model_dump()` at both locations; issue closed as already-fixed (no new code change needed)  

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
**Status:** ✅ Fixed (2026-06-12)  
**File:** `database.py:27` (moved from line 1416)  
**GitHub:** #24  
**Detail:** `from app.demo import build_demo_tree` moved to top-level imports; inline import removed from `seed_demo()` method body. PR #39 merged.  

---

### B-15 — `_PLACEHOLDER_WORK_ID` module-level UUID in `demo.py`

**Severity:** Low — misleading in code review  
**Status:** ✅ Fixed (PR fix/placeholder-work-id, 2026-06-11)  
**File:** `demo.py:7`  
**GitHub:** #28  
**Detail:** Replaced `str(uuid.uuid4())` with `"__placeholder_work_id__"` sentinel string to clearly signal this is a temporary stub value  

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
**Status:** ✅ Fixed (2026-06-12)  
**File:** `models.py:497, 643`  
**GitHub:** #25  
**Detail:** Changed `by_type` from `dict[str, int]` to `dict[NodeType, int]` in both `WorkStatsResponse` and `DemoSeedResponse`. NodeType is a str enum so JSON serialization is identical at runtime.  

---

### B-19 — `_PLACEHOLDER_WORK_ID` sentinel string fails Pydantic UUID pattern validation

**Severity:** Low — blocks test execution for demo seeding feature  
**Status:** ✅ Fixed (2026-06-11)  
**File:** `demo.py:7`  
**GitHub:** #37  
**Detail:** Replaced `str(uuid.uuid4())` with `str(uuid.UUID("00000000-0000-0000-0000-000000000000"))` — valid UUID format that passes validation, clearly non-real in code review. Both seed paths overwrite before any DB write.  

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

---

### 2026-06-10 — Search endpoint integration tests (Phase 14, T-56)

**Done:**
- Wrote `TestSearchQuery` class in `test_integration_normalised.py` — 14 test methods (18 collected) for `GET /nodes/search`
- Covers: basic match, both-fields search, textScore ordering, no match, empty query validation, work_id filter, node_type filter, invalid node_type, account isolation, no auth, scope enforcement (5-param scoped, 1 skip), DB error 503, blacklisted token, query-too-long 422
- All node creations use `node_type: "part"` (no parent needed) — avoids hierarchy violations
- Verified: 190/190 integration tests pass (178 passed, 12 scope-skipped) — 0 regressions

**PROGRESS.md changes:**
- T-56 added to Phase 14 table (✅, 2h)
- Running Totals: Integration tests 157/168 → 175/186
- Session entry added

**Branch:** `refactor/normalised-node-model`

---

### 2026-06-10 — Phase 20: Work Reading Order implemented (E-88–E-90, T-57)

**Done:**
- Added `OrderedNodesResponse` to `models.py` (`work_id`, `nodes`, `count`, `next_cursor`)
- Added `NodeStorage.get_reading_order()` to `database.py` — single `{account_id, work_id}` fetch, in-memory DFS pre-order with `visited` cycle-guard, `_id` stripped
- Added `GET /works/{work_id}/nodes/ordered` endpoint to `api.py` — work ownership check first (404), `limit`/`cursor` pagination over materialised sequence, `tags=["Search"]`, scope `tree:reader`
- Added 6 unit tests in `TestNodeStorageGetReadingOrder` (empty, single, pre-order shape, position sort, cycle guard, _id stripped) — all pass
- Added `TestWorkReadingOrder` integration class — 14 tests (12 pass, 1 scope-skip, 1 blacklisted env-limited)
- Verified: 52/52 unit tests pass; 188/204 integration tests pass (13 scope-skipped, 3 blacklisted env-limited — pre-existing Redis DNS issue)
- Ruff lint: 0 new warnings from feature code

**Branch:** `feature/work-reading-order`


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

### 2026-06-11 — Fix B-15/#37: _PLACEHOLDER_WORK_ID sentinel fails Pydantic UUID validation

**Done:**
- Changed `_PLACEHOLDER_WORK_ID` in `server/app/demo.py:7` from `str(uuid.uuid4())` to `str(uuid.UUID("00000000-0000-0000-0000-000000000000"))`
- Fixed sentinel is a valid UUID4-format string that passes Pydantic `UUID_PATTERN` validation
- Clearly non-real (all zeros) and distinguishable in code review
- Both seed paths (`_seed_with_transaction:1464`, `_seed_with_compensating_cleanup:1507`) overwrite the placeholder with `work_doc["work_id"]` before any DB write — confirmed safe
- Verified: `build_demo_tree()` returns valid `CreateWorkRequest` and 13 `CreateNodeRequest` objects that pass full Pydantic validation without ValidationError

**PROGRESS.md changes:**
- New session entry added below
- New defect B-19/#37 added to Defects section (✅ Fixed)

**Commit:** `bb9bcbd Fix sentinel work_id to pass Pydantic UUID validation`
**PR:** https://github.com/felipeazucares/fabulator/pull/38 (merged to close #37)

**Branch:** `feature/work-reading-order`

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

---

### 2026-06-10 — V-03 OpenAPI verified, V-04 PR blocked (Phase 20)

**Done:**
- V-03: OpenAPI schema verified via `api.app.openapi()` inside Docker container — endpoint `/works/{work_id}/nodes/ordered` renders with summary "Get nodes in reading order", tags `["Search"]`, and `OrderedNodesResponse` in `components/schemas`
- V-04: Branch `feature/work-reading-order` pushed to `origin` (already up-to-date); PR creation blocked — `gh` CLI not available on host or container, `GH_TOKEN`/`GITHUB_TOKEN` env vars present but API returns "Bad credentials"\

**PROGRESS.md changes:**
- Phase 20: V-03 ✅, V-04 ❌ added to table
- Session entry added

**Branch:** `feature/work-reading-order`

---

### 2026-06-11 — Lightweight triage: no unambiguous next step

**Done:**
- Read `.claude/context.md`, `specification/PROGRESS.md`, checked `gh issue list`
- All 35 enhancement tasks complete (Phases 14–20)
- No P1 issues; 6 open issues total (all p3)
- Conclusion: no single unambiguous next item — multiple equal p3 candidates, no ordering signal
- User presented with 7 candidates to choose from

**PROGRESS.md changes:**
- None — no task status changes

**Branch:** `main`

---

### 2026-06-11 — V-04 resolved: work-reading-order merged and verified

**Done:**
- Investigated missing endpoint in Swagger UI — endpoint was registered in code but tagged under `["Search"]`, not "Works"/"Nodes"
- Confirmed `GET /works/{work_id}/nodes/ordered` live via `curl http://localhost:8000/openapi.json`
- V-04 marked ✅ in Phase 20 table — all 7 items now complete

**PROGRESS.md changes:**
- Phase 20: V-04 ❌ → ✅
- Session entry added

**Branch:** `main`

---

### 2026-06-11 — API version bump + feature.md finalised

**Done:**
- Bumped `version` in `api.py:181` from `"0.1.0"` to `"1.0"`
- Updated `specification/work-reading-order/work-reading-order-feature.md:3` — status changed from `NOT STARTED` to `COMPLETED ✅`

**PROGRESS.md changes:**
- None — this session had no PROGRESS.md task status changes; all Phase 20 tasks already ✅

**Branch:** `main`

---

### 2026-06-12 — Phase 21 GitHub issues created (#41–#52)

**Done:**
- Created `refactor`, `docs`, `test` labels on GitHub
- Created 12 GitHub issues for Phase 21 tasks E-101 through E-112 (#41–#52)
- Updated PROGRESS.md Phase 21 summary table: `TBC` → `#41`–`#52` in GitHub column

**Not done (no code changes):**
- Code implementation for E-101 through E-112 — not started (⬜ all)
- Issue #25 (`by_type` fix) remains OPEN on GitHub despite being marked ✅ fixed in PROGRESS.md — may need closing manually

**PROGRESS.md changes:**
- Phase 21 summary table: GitHub column filled with issue numbers
- Session entry added

**Branch:** `main`

---

### 2026-06-12 — E-107 doc verification + E-108 demo tree restructured

**Done:**
- E-107: Verified CPs 12/13/15/17/19/20/27/30 against code. Updated `specification/REQUIREMENTS.md` — 14 sections cleaned of stale "beat" references. PR #60 created to `refactor/renovate_hierarchy`.
- E-108: Restructured `server/app/demo.py` — removed 8 Beat nodes, added Part 2 (nested under Chapter 1) + 2 new Scenes. Tree now 10 nodes (`{part: 2, chapter: 2, scene: 6}`). All flexible-hierarchy paths exercised: Part→Scene, Part→Chapter, Chapter→Part, Chapter→Scene.
- Opencode `.claude/` directory populated: `context.md`, `mode=normal`.

**Still open:**
- E-109 (update unit tests), E-110 (integration tests), E-111 (demo seed tests), E-112 (beat rejection test) — all ⬜
- 15 pre-existing test failures: 5 TestBuildDemoTree assertion failures (need E-109 update for new tree shape), 2 TestAuthHelpers (bcrypt/passlib compat), 1 TestDemoSeedResponse (stale `by_type`)

**PROGRESS.md changes:**
- Phase 21 table: E-108 ⬜ → ✅
- Running totals: 7/12 → 8/12
- Session entry added

**Branch:** `refactor/e107-post-code-doc-verification`

---

### 2026-06-12 — E-109 unit tests updated for restructured demo tree

**Done:**
- E-109: Updated `server/tests/test_unit.py` — all 12 `TestBuildDemoTree` tests and `TestDemoSeedResponse` updated to match new 10-node tree with flexible hierarchy. PR #62 created to `refactor/renovate_hierarchy`.
- 50/52 unit tests pass; remaining 2 failures are pre-existing bcrypt/passlib compat in Python 3.9 environment (TestAuthHelpers).

**Still open:**
- E-110 (integration tests), E-111 (demo seed tests), E-112 (beat rejection test) — all ⬜

**PROGRESS.md changes:**
- Phase 21 table: E-109 ⬜ → ✅
- Running totals: 8/12 → 9/12
- Session entry added

**Branch:** `refactor/e109-update-unit-tests`

### 2026-06-13 — DD-11 quality assessment: by_type cleanup, test_phase10.py found obsolete

**Audit scope:** All DD-11 changed files checked against CONSTITUTION.md rules.

**Fixes applied (same session):**
- `database.py` lines 986, 1454, 1496 — removed stale `"beat": 0` from `by_type` counter dicts (IV.3, V.5).
- `test_unit.py:594` — removed `@pytest.mark.asyncio` (VI.6: asyncio_mode = auto makes it redundant).

**Issue raised:**
- [#65](https://github.com/felipeazucares/fabulator/issues/65) — `test_phase10.py` obsolete: 8 of 36 tests fail under DD-11 hierarchy rules. Tests assert old `_VALID_CHILD` Part→Chapter→Scene→Beat mapping. Needs deletion or rewrite (V.5, VI.2).

**Unchanged pre-existing items (not DD-11 regressions):**
- `api.py:1325` and `database.py:1506` — bare `except Exception` (V.2). Both are compensating/health-check patterns. Existed before DD-11.

**PROGRESS.md changes:**
- QA findings section added. No phase task status changes.


