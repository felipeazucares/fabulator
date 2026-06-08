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
| T-11 | `GET /works` — list all Works for account, ordered by `created_at` desc | ⬜ | 30 min | |
| T-12 | `GET /works/{work_id}` — single Work; 404 on wrong account | ⬜ | 20 min | |
| T-13 | `POST /works` — create; whitespace title → 422; HTTP 201 | ⬜ | 30 min | |
| T-14 | `PUT /works/{work_id}` — update; author change triggers node cascade | ⬜ | 30 min | |
| T-15 | `DELETE /works/{work_id}` — delete Work + all nodes; return count in detail | ⬜ | 30 min | |

---

## Phase 5 — Node Core CRUD Endpoints (`api.py`)

| # | Task | Status | Est | Notes |
|---|------|--------|-----|-------|
| T-16 | `GET /works/{work_id}/nodes` — list with optional `?node_type=` filter; 422 on invalid type | ⬜ | 30 min | |
| T-17 | `GET /nodes/{node_id}` — single node; 404 on wrong account | ⬜ | 20 min | |
| T-18 | `POST /nodes` — hierarchy validation (HIER-01/02/03); position assignment (NODE-05); author copy from Work | ⬜ | 45 min | |
| T-19 | `PUT /nodes/{node_id}` — content update + reparent; hierarchy re-validation; cycle detection (UPDATE-03) | ⬜ | 45 min | |
| T-20 | `DELETE /nodes/{node_id}` — cascade delete; return descendant count | ⬜ | 30 min | |

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
| T-44 | Position clamping, tag suffix on duplicate, Beat deep-copy guard | T-UNIT-08, T-UNIT-09, T-UNIT-10 | ⬜ | 20 min | Beat guard committed in `database.py` (`duplicate_shallow` line 937, `duplicate_deep` line 992). Unit tests not yet written. |
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
| Unit tests | 3 | 5 |
| Integration tests | 0 | 5 |
| SPEC.md acceptance criteria | 0 | 11 |
| Tasks complete | 24 | 55 |

---

## Session Handoff

### Last Session: Phase 10 — T-43 Sibling Renumbering Unit Tests

- **T-43** ✅ — Added `TestReorderSiblings` class to `test_phase10.py`. 5 tests covering T-UNIT-05 (insert-at-start), T-UNIT-06 (insert-at-end with clamping), T-UNIT-07 (remove-from-middle), plus single-node clamp-to-zero and node-not-found edge cases. All 28 tests pass.
- **Treelib regression fixed** — commit `b66e3bf` had accidentally re-introduced `from treelib import Tree` into `models.py` and restored the full `TreeStorage` class into `database.py` (reverting the Phase 8 T-32/T-33 work). Re-removed: treelib import from `models.py`, `TreeStorage` class from `database.py`, unused `TreeSaveSchema` and `saves_helper` from `models.py`, dead `TreeDepthLimitExceeded` import from `api.py`.
- **No commits made this session** — working tree has uncommitted changes to: `database.py`, `models.py`, `api.py`, `tests/test_phase10.py`, `specification/PROGRESS.md`.

### Current State (verified 2026-06-08)

- **Working tree is dirty** — changes to `database.py`, `models.py`, `api.py`, `tests/test_phase10.py` are uncommitted.
- **Beat guard is committed** in `database.py`: `duplicate_shallow` (line 937) and `duplicate_deep` (line 992) both return `None` for Beat nodes.
- **`test_phase10.py`** contains 28 passing tests across three classes (`TestIsValidParentChild` × 18, `TestWouldCreateCycle` × 5, `TestReorderSiblings` × 5). Note: previous session recorded 29 — the correct count is 28.
- **T-44 unit tests not written** — duplicate position/tag/Beat-guard tests do not yet exist.
- **T-45 not started.**

### Issues & Decisions
- T-41 & T-42 written in a standalone `test_phase10` module to avoid dependency chain issues in `test_unit.py`
- All tests use mocked MongoDB via `AsyncMock` / `MagicMock` — no real DB required (per Constitution rule)
- `test_chapter_to_scene_valid_recheck`: corrected from "invalid" to "valid" — it IS a valid pair per `_VALID_CHILD`
- T-39 fix: Created separate `UserDetailsSafe` model rather than using Pydantic's `Field(exclude=True)` approach
- `duplicate_shallow` returns `_strip_id(new_doc)` directly (in-memory dict) — no second `get_node` call at end; differs from `reorder_siblings` mock pattern
- All completed Phase 8 and Phase 9 changes have been committed and pushed to `origin/refactor/normalised-node-model`

### Next Steps

Phase 10 remaining work (in order):
1. **Commit current uncommitted changes** — `database.py`, `models.py`, `api.py`, `tests/test_phase10.py`
2. **T-44** — Write duplicate unit tests: position = original+1, tag suffix " (copy)", Beat guard → `None` for both shallow and deep
3. **T-45** — Write author propagation unit tests (non-null author propagates; null author handled)

Then proceed to Phase 4–7 endpoints before writing integration tests — no API endpoints exist yet, so integration tests cannot run until those are implemented first.

---

### Acceptance Criteria (SPEC.md Part VII)

- [ ] All EARS requirements in SPEC.md Parts III, V, VI implemented and verified by tests
- [ ] `tree_collection` no longer written to by any route handler
- [ ] `treelib` removed from `requirements.txt`
- [ ] `work_collection` created with JSON Schema validator and indexes
- [ ] `node_collection` created with JSON Schema validator and indexes
- [ ] All new endpoints have `response_model`, `summary`, `description`, and `tags`
- [ ] Isolation tests exist for every new endpoint
- [ ] Scope tests exist for every new endpoint
- [ ] Unit tests cover hierarchy validation, cycle detection, sibling reordering, author cascade
- [ ] `CONSTITUTION.md` Part I.2 and Part IV updated to reflect new model
- [ ] `DESIGN.md` Part IV.1, Part III.1, DD-01 updated to reflect new model
