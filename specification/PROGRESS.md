# Refactor Progress — Normalised Adjacency-List Model

**Branch:** `refactor/normalised-node-model`
**Spec:** `SPEC.md` v0.3 | **Tests:** `TEST_SPEC.md` v0.2 | **Rules:** `CONSTITUTION.md` v1.0
**Started:** 2026-06-07

---

## Status Key

| Symbol | Meaning |
|--------|---------|
| ✅ | Done — committed |
| 🔄 | In progress |
| ⬜ | Not started |
| ❌ | Blocked |

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
| T-21 | `GET /nodes/{node_id}/children` — ordered by position | ⬜ | 20 min | |
| T-22 | `GET /nodes/{node_id}/parent` — null for Part root | ⬜ | 20 min | |
| T-23 | `GET /nodes/{node_id}/ancestors` — root-to-parent ordered list | ⬜ | 20 min | |
| T-24 | `GET /nodes/{node_id}/siblings` — excludes self; ordered by position | ⬜ | 20 min | |
| T-25 | `GET /works/{work_id}/nodes/root` — all Part nodes for Work | ⬜ | 20 min | |
| T-26 | `GET /works/{work_id}/nodes/leaves` — all Beat nodes for Work | ⬜ | 15 min | |
| T-27 | `GET /works/{work_id}/stats` — `WorkStatsResponse` with type counts and max depth | ⬜ | 25 min | |

---

## Phase 7 — Reorder & Duplicate Endpoints (`api.py`)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-28 | `PUT /nodes/{node_id}/reorder` — clamp to max sibling; renumber all siblings | ⬜ | 30 min | |
| T-29 | `POST /nodes/{node_id}/duplicate` — shallow copy; `"{tag} (copy)"`; position `original + 1` | ⬜ | 30 min | |
| T-30 | `POST /nodes/{node_id}/duplicate?deep=true` — recursive subtree copy; new UUIDs; Beat guard → 400 | ⬜ | 45 min | |

---

## Phase 8 — Remove Old Endpoints & `treelib`

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-31 | Remove from `api.py`: prune, graft, `/saves`, `/loads` endpoints | ✅ | 30 min | Verify nothing external references before removing |
| T-32 | Remove/retire `TreeStorage` from `database.py` | ✅ | 20 min | `UserStorage` untouched |
| T-33 | Remove `treelib==1.8.0` from `requirements.txt`; remove all treelib imports | ✅ | 15 min | |
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
| T-45 | Author propagation — non-null + null | T-UNIT-11, T-UNIT-12 | ⬜ | 15 min |

---

## Phase 11 — Integration Tests (`test_api_integration.py`)

| # | Task | Test IDs | Count | Status | Est |
|---|------|----------|-------|--------|-----|
| T-46 | Work CRUD — happy path + errors + isolation + scope | T-WORK-01 → T-WORK-SCOPE-02 | 22 | ⬜ | 2h |
| T-47 | Node creation — happy path + errors + isolation + scope | T-CREATE-01 → T-CREATE-SCOPE-01 | 25 | ⬜ | 2h |
| T-48 | Node retrieval — happy path + errors + isolation + scope | T-READ-01 → T-READ-SCOPE-01 | 23 | ⬜ | 2h |
| T-49 | Node update + delete — all cases | T-UPDATE-01 → T-DELETE-SCOPE-01 | 21 | ⬜ | 1h 30m |
| T-50 | Reorder + duplicate — all cases | T-REORDER-01 → T-DUP-SCOPE-01 | 18 | ⬜ | 1h 30m |

---

## Phase 12 — Documentation Updates

| # | Task | Status | Est |
|---|------|--------|-----|
| T-51 | Update `CONSTITUTION.md` Part I.2 (append-only removed), Part IV (new node schema) | ⬜ | 20 min |
| T-52 | Update `DESIGN.md` Part IV.1 (data model), Part III.1 (API contract), DD-01, DD-03 | ⬜ | 30 min |
| T-53 | Tick all checkboxes in `SPEC.md` Part VII acceptance criteria | ⬜ | 10 min |

---

## Phase 13 — Verification & PR

| # | Task | Status | Est |
|---|------|--------|-----|
| T-54 | Run full test suite; confirm 0 failures; verify all SPEC.md Part VII boxes checked | ⬜ | 20 min |
| T-55 | Push branch, open PR | ⬜ | 15 min |

---

## Running Totals

| Category | Done | Total |
|----------|------|-------|
| Unit tests | 4 | 5 |
| Integration tests | 0 | 5 |
| SPEC.md acceptance criteria | 5 | 11 |
| Tasks complete | 35 | 55 |

---

## Session Handoff

### Last Session: Phases 4 + 5 — Work + Node Core CRUD Endpoints

- **Phase 4 (T-11 to T-15)** ✅ — All five Work endpoints implemented in `api.py`:
  - `POST /works` (line 214) — 201, `WorkResponse`, title validation, author used from request.
  - `GET /works` (line 243) — 200, `list[WorkResponse]`, ordered by `created_at` desc.
  - `GET /works/{work_id}` (line 266) — 200, `WorkResponse`, UUID path validation, 404 on wrong account.
  - `PUT /works/{work_id}` (line 292) — 200, `WorkResponse`, partial update via `exclude_unset=True`, author cascade to nodes.
  - `DELETE /works/{work_id}` (line 325) — 200, returns descendant count, cascade delete on `node_collection`.
- **Phase 5 (T-16 to T-20)** ✅ — All five Node core CRUD endpoints implemented in `api.py`:
  - `POST /nodes` (line 357) — 201, `NodeResponse`, hierarchy validation via `is_valid_parent_child`, no-parent guard, author copied from Work, position auto-assigned.
  - `GET /works/{work_id}/nodes` (line 423) — 200, `list[NodeResponse]`, optional `?node_type=` filter via `Optional[NodeType]` enum, work ownership check.
  - `GET /nodes/{node_id}` (line 465) — 200, `NodeResponse`, UUID path validation, 404 on wrong account.
  - `PUT /nodes/{node_id}` (line 491) — 200, `NodeResponse`, reparenting with hierarchy check + cycle detection (`would_create_cycle`), hierarchy checked before cycle.
  - `DELETE /nodes/{node_id}` (line 583) — 200, returns descendant count, BFS cascade delete.
- **All endpoints have**: `response_model`, `summary`, `description`, `tags`, proper `response_model` types, `Security()` with scope enforcement, and database error → HTTP 503 with sanitised `"Database error"` message.
- **No commits made this session** — working tree has uncommitted changes to: `database.py`, `models.py`, `api.py`, `tests/test_phase10.py`, `specification/PROGRESS.md`.

### Current State (verified 2026-06-08)

- **Working tree is dirty** — changes to `database.py`, `models.py`, `api.py`, `tests/test_phase10.py`, `specification/PROGRESS.md` are uncommitted.
- **`test_phase10.py`** contains 33 passing tests across four classes (`TestIsValidParentChild` × 18, `TestWouldCreateCycle` × 5, `TestReorderSiblings` × 5, `TestDuplicateNode` × 5).
- **T-45 not started** — author propagation unit tests.
- **Phases 6 and 7** (Navigation, Reorder, Duplicate endpoints) — DB methods are complete, but route handlers are NOT yet implemented in `api.py`.
- **Phase 11** (Integration tests) — blocked until Phases 6 and 7 endpoints exist.
- **35 of 55 tasks complete** — Phases 0–5, 8–9, and 10 (partial) done.

### Issues & Decisions
- T-41 & T-42 written in a standalone `test_phase10` module to avoid dependency chain issues in `test_unit.py`
- All tests use mocked MongoDB via `AsyncMock` / `MagicMock` — no real DB required (per Constitution rule)
- `duplicate_shallow` returns `_strip_id(new_doc)` directly (in-memory dict) — no second `get_node` call at end; differs from `reorder_siblings` mock pattern
- `duplicate_shallow` and `duplicate_deep` both tested via `storage.get_node = AsyncMock(return_value=...)` patched on the instance
- All completed Phase 8 and Phase 9 changes have been committed and pushed to `origin/refactor/normalised-node-model`

### Next Steps

1. **Commit current uncommitted changes** — `database.py`, `models.py`, `api.py`, `tests/test_phase10.py`, `specification/PROGRESS.md`
2. **T-45** — Write author propagation unit tests (non-null author propagates; null author handled)
3. **Phases 6–7** — Navigation endpoints (T-21 to T-27), Reorder (T-28), Duplicate (T-29, T-30) — all DB methods complete; route handlers needed in `api.py`
4. **Phase 11** — Integration tests (blocked until Phase 6–7 endpoints exist)

---

### Acceptance Criteria (SPEC.md Part VII)

- [ ] All EARS requirements in SPEC.md Parts III, V, VI implemented and verified by tests (Work CRUD + Node CRUD done; Navigation, Reorder, Duplicate pending)
- [x] `tree_collection` no longer written to by any route handler
- [x] `treelib` removed from `requirements.txt`
- [x] `work_collection` created with JSON Schema validator and indexes
- [x] `node_collection` created with JSON Schema validator and indexes
- [x] All new endpoints have `response_model`, `summary`, `description`, and `tags`
- [ ] Isolation tests exist for every new endpoint
- [ ] Scope tests exist for every new endpoint
- [ ] Unit tests cover hierarchy validation, cycle detection, sibling reordering, author cascade (T-45 author cascade still pending)
- [ ] `CONSTITUTION.md` Part I.2 and Part IV updated to reflect new model
- [ ] `DESIGN.md` Part IV.1, Part III.1, DD-01 updated to reflect new model
