# Fabulator — Test Specification
## Normalised Adjacency-List Refactor

**Version:** 0.1
**Date:** 2026-06-06
**Maps to:** `SPEC.md` v0.2
**Companion documents:** `CONSTITUTION.md`, `SPEC.md`

---

## How to Use This Document

Each test case maps to one or more EARS requirements in `SPEC.md`. Test IDs follow the pattern `T-{AREA}-{NUMBER}`. The `Requirement` column references the SPEC.md requirement being verified.

Test cases are grouped by area. Within each area, happy-path cases come first, then error cases, then isolation and scope cases.

All integration tests require live MongoDB Atlas and Redis. Unit tests are marked `[UNIT]` and require neither.

---

## Part I — Test Data Conventions

### I.1 — Standard Test Fixtures

| Fixture | Description |
|---------|-------------|
| `auth_token_full` | JWT with all scopes for User A |
| `auth_token_reader` | JWT with `tree:reader` only for User A |
| `auth_token_writer` | JWT with `tree:writer` only for User A |
| `auth_token_user_b` | JWT with all scopes for User B (isolation tests) |
| `part_node` | A valid Part node belonging to User A |
| `chapter_node` | A valid Chapter node under `part_node` |
| `scene_node` | A valid Scene node under `chapter_node` |
| `beat_node` | A valid Beat node under `scene_node` |

### I.2 — Valid Node Payloads

**Minimal valid Part:**
```json
{ "node_type": "part", "parent_id": null, "tag": "Act One" }
```

**Minimal valid Chapter:**
```json
{ "node_type": "chapter", "parent_id": "{part_node_id}", "tag": "Chapter 1" }
```

**Full valid Beat:**
```json
{
  "node_type": "beat",
  "parent_id": "{scene_node_id}",
  "tag": "Opening beat",
  "description": "The hero arrives",
  "text": "Long form content here",
  "previous": "Prologue",
  "next": "Rising action",
  "tags": ["action", "intro"]
}
```

---

## Part II — Node Creation Tests

### Happy Path

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-CREATE-01 | Create a Part with no parent | `node_type: "part"`, `parent_id: null`, `tag: "Act One"` | HTTP 201, NodeResponse with `node_type: "part"`, `parent_id: null`, `position: 0`, `node_id` is valid UUID4 | NODE-01 |
| T-CREATE-02 | Create a Chapter under a Part | `node_type: "chapter"`, `parent_id: {part_id}` | HTTP 201, NodeResponse with `parent_id == part_id`, `position: 0` | NODE-01 |
| T-CREATE-03 | Create a Scene under a Chapter | `node_type: "scene"`, `parent_id: {chapter_id}` | HTTP 201, NodeResponse with `node_type: "scene"` | NODE-01 |
| T-CREATE-04 | Create a Beat under a Scene | `node_type: "beat"`, `parent_id: {scene_id}` | HTTP 201, NodeResponse with `node_type: "beat"` | NODE-01 |
| T-CREATE-05 | Second Chapter under same Part gets position 1 | Create two Chapters under same Part | Second Chapter has `position: 1` | NODE-05 |
| T-CREATE-06 | First child of a new parent gets position 0 | Create Chapter under Part with no existing children | `position: 0` | NODE-05 |
| T-CREATE-07 | Create node with all optional fields populated | Full valid Beat payload | HTTP 201, all fields present in response | NODE-01 |
| T-CREATE-08 | `created_at` and `updated_at` are set on creation | Create any node | Both timestamps present, equal, UTC | NODE-01 |

### Error Cases

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-CREATE-09 | Chapter with no parent rejected | `node_type: "chapter"`, `parent_id: null` | HTTP 422, `detail: "Only nodes of type 'part' may be created without a parent"` | NODE-02, HIER-02 |
| T-CREATE-10 | Scene with no parent rejected | `node_type: "scene"`, `parent_id: null` | HTTP 422, same message as T-CREATE-09 | NODE-02 |
| T-CREATE-11 | Beat with no parent rejected | `node_type: "beat"`, `parent_id: null` | HTTP 422, same message as T-CREATE-09 | NODE-02 |
| T-CREATE-12 | Chapter under Scene rejected | `node_type: "chapter"`, `parent_id: {scene_id}` | HTTP 422, `detail: "Invalid parent-child relationship: a chapter cannot be placed under a scene"` | NODE-04, HIER-03 |
| T-CREATE-13 | Part under Chapter rejected | `node_type: "part"`, `parent_id: {chapter_id}` | HTTP 422, hierarchy violation message | NODE-04 |
| T-CREATE-14 | Beat under Part rejected | `node_type: "beat"`, `parent_id: {part_id}` | HTTP 422, hierarchy violation message | NODE-04 |
| T-CREATE-15 | Non-existent parent_id | `parent_id: {valid_uuid_not_in_db}` | HTTP 404, `detail: "Parent node not found"` | NODE-03 |
| T-CREATE-16 | Empty tag rejected | `tag: ""` | HTTP 422, `detail: "tag must not be empty"` | NODE-06 |
| T-CREATE-17 | Whitespace-only tag rejected | `tag: "   "` | HTTP 422, `detail: "tag must not be empty"` | NODE-06 |
| T-CREATE-18 | Invalid node_type rejected | `node_type: "paragraph"` | HTTP 422 | READ-05 (by analogy) |
| T-CREATE-19 | Invalid UUID format for parent_id | `parent_id: "not-a-uuid"` | HTTP 422 | SEC-03 |

### Isolation and Scope

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-CREATE-ISO-01 | User B's parent_id used by User A | HTTP 404, `detail: "Parent node not found"` | NODE-03, SEC-01 |
| T-CREATE-SCOPE-01 | Create node with `tree:reader` only token | HTTP 403 | CONSTITUTION II.2 |

---

## Part III — Node Retrieval Tests

### Happy Path

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-READ-01 | Get single node by ID | `GET /nodes/{node_id}` | HTTP 200, correct NodeResponse | READ-01 |
| T-READ-02 | Get all nodes returns full account list | `GET /nodes` with 4-node tree | HTTP 200, list of 4 NodeResponse objects | READ-03 |
| T-READ-03 | Filter by node_type returns only matching nodes | `GET /nodes?node_type=beat` | HTTP 200, only Beat nodes | READ-04 |
| T-READ-04 | Get children returns direct children ordered by position | `GET /nodes/{part_id}/children` | HTTP 200, list of Chapters ordered by position | READ-06 |
| T-READ-05 | Get children of leaf node returns empty list | `GET /nodes/{beat_id}/children` | HTTP 200, empty list | READ-07 |
| T-READ-06 | Get parent returns parent node | `GET /nodes/{chapter_id}/parent` | HTTP 200, Part NodeResponse | READ-08 (by analogy) |
| T-READ-07 | Get parent of Part returns null | `GET /nodes/{part_id}/parent` | HTTP 200, `data: null` | READ-08 |
| T-READ-08 | Get ancestors of Beat returns [Part, Chapter, Scene] | `GET /nodes/{beat_id}/ancestors` | HTTP 200, AncestorsResponse with 3 nodes in order | READ-09 |
| T-READ-09 | Get ancestors of Part returns empty list | `GET /nodes/{part_id}/ancestors` | HTTP 200, `ancestors: []` | READ-10 |
| T-READ-10 | Get siblings returns other nodes with same parent | `GET /nodes/{chapter_id}/siblings` | HTTP 200, other Chapter nodes under same Part, excluding self | READ-11 |
| T-READ-11 | Get siblings of only child returns empty list | `GET /nodes/{chapter_id}/siblings` when no other chapters | HTTP 200, empty list | READ-11 |
| T-READ-12 | Get root returns all Part nodes | `GET /trees/root` | HTTP 200, list of Part nodes | READ-12 |
| T-READ-13 | Get stats returns correct counts | `GET /trees/stats` with known tree | HTTP 200, correct `by_type` counts and `max_depth` | READ-13 |
| T-READ-14 | Get leaves returns all Beat nodes | `GET /trees/leaves` | HTTP 200, only Beat nodes | SPEC IV.1 |

### Error Cases

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-READ-ERR-01 | Get non-existent node | HTTP 404, `detail: "Node not found"` | READ-02 |
| T-READ-ERR-02 | Invalid UUID format in path | HTTP 422 | SEC-03 |
| T-READ-ERR-03 | Invalid node_type filter value | HTTP 422, `detail: "node_type must be one of: part, chapter, scene, beat"` | READ-05 |

### Isolation and Scope

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-READ-ISO-01 | User A requests User B's node by ID | HTTP 404, `detail: "Node not found"` | SEC-01 |
| T-READ-ISO-02 | User A requests children of User B's node | HTTP 404 | SEC-01 |
| T-READ-ISO-03 | `GET /nodes` only returns User A's nodes | No User B nodes in list | READ-03, SEC-01 |
| T-READ-SCOPE-01 | Get node with no token | HTTP 401 | CONSTITUTION II.2 |

---

## Part IV — Node Update Tests

### Happy Path

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-UPDATE-01 | Update tag only | `PUT /nodes/{id}` `{ "tag": "New name" }` | HTTP 200, `tag` updated, `updated_at` > `created_at` | UPDATE-01 |
| T-UPDATE-02 | Update text content fields | `description`, `text`, `previous`, `next`, `tags` | HTTP 200, all fields updated | UPDATE-01 |
| T-UPDATE-03 | Reparent Chapter to a different Part | `parent_id: {other_part_id}` | HTTP 200, `parent_id` updated | UPDATE-02 |
| T-UPDATE-04 | `updated_at` is set on every update | Any update | `updated_at` is later than before the request | UPDATE-01 |

### Error Cases

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-UPDATE-ERR-01 | Reparent with hierarchy violation | HTTP 422, hierarchy violation message | UPDATE-02, HIER-03 |
| T-UPDATE-ERR-02 | Move node into its own descendant | HTTP 422, `detail: "Cannot move a node into its own descendant"` | UPDATE-03 |
| T-UPDATE-ERR-03 | Update non-existent node | HTTP 404, `detail: "Node not found"` | UPDATE-04 |
| T-UPDATE-ERR-04 | Reparent to non-existent parent | HTTP 404, `detail: "Parent node not found"` | UPDATE-05 |
| T-UPDATE-ERR-05 | Invalid UUID in path | HTTP 422 | SEC-03 |

### Isolation and Scope

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-UPDATE-ISO-01 | User A updates User B's node | HTTP 404 | SEC-01 |
| T-UPDATE-ISO-02 | User A reparents to User B's parent | HTTP 404, `detail: "Parent node not found"` | UPDATE-05, SEC-01 |
| T-UPDATE-SCOPE-01 | Update node with `tree:reader` only token | HTTP 403 | CONSTITUTION II.2 |

---

## Part V — Node Deletion Tests

### Happy Path

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-DELETE-01 | Delete leaf Beat node | `DELETE /nodes/{beat_id}` | HTTP 200, `detail: "Node and 0 descendants deleted"` | DELETE-01, DELETE-03 |
| T-DELETE-02 | Delete Chapter deletes Chapter + all Scenes + all Beats | `DELETE /nodes/{chapter_id}` with 2 scenes, 4 beats | HTTP 200, `detail: "Node and 6 descendants deleted"` | DELETE-01, HIER-05 |
| T-DELETE-03 | Delete Part deletes entire subtree | `DELETE /nodes/{part_id}` | HTTP 200, correct descendant count | DELETE-01 |
| T-DELETE-04 | Deleted node is no longer retrievable | Delete then `GET /nodes/{id}` | HTTP 404 on subsequent GET | DELETE-01 |
| T-DELETE-05 | Deleted node's children are no longer retrievable | Delete Chapter then GET child Scene | HTTP 404 | DELETE-01, HIER-05 |

### Error Cases

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-DELETE-ERR-01 | Delete non-existent node | HTTP 404, `detail: "Node not found"` | DELETE-02 |
| T-DELETE-ERR-02 | Invalid UUID in path | HTTP 422 | SEC-03 |

### Isolation and Scope

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-DELETE-ISO-01 | User A deletes User B's node | HTTP 404 | SEC-01 |
| T-DELETE-SCOPE-01 | Delete with `tree:reader` only token | HTTP 403 | CONSTITUTION II.2 |

---

## Part VI — Reorder Tests

### Happy Path

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-REORDER-01 | Move Chapter from position 2 to position 0 | Three chapters, reorder middle to 0 | Target at position 0, others renumbered to 1 and 2 | REORDER-01 |
| T-REORDER-02 | Move Chapter to current position (no-op) | Reorder to same position | HTTP 200, no change | REORDER-01 |
| T-REORDER-03 | Position clamped when exceeds sibling count | 3 siblings, request position 99 | HTTP 200, node placed at position 2 | REORDER-02 |
| T-REORDER-04 | Sibling positions remain contiguous after reorder | Any reorder | All sibling positions form a zero-based contiguous sequence | REORDER-01 |

### Error Cases

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-REORDER-ERR-01 | Negative position | HTTP 422, `detail: "position must be a non-negative integer"` | REORDER-03 |
| T-REORDER-ERR-02 | Reorder non-existent node | HTTP 404, `detail: "Node not found"` | SEC-01 (by analogy) |

### Isolation and Scope

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-REORDER-ISO-01 | User A reorders User B's node | HTTP 404 | SEC-01 |
| T-REORDER-SCOPE-01 | Reorder with `tree:reader` only token | HTTP 403 | CONSTITUTION II.2 |

---

## Part VII — Duplicate Tests

### Happy Path

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-DUP-01 | Shallow duplicate of Chapter | `POST /nodes/{chapter_id}/duplicate` | HTTP 201, new node with `tag: "Chapter 1 (copy)"`, new `node_id`, same `parent_id`, no children | DUP-01 |
| T-DUP-02 | Shallow duplicate gets position after original | Original at position 1, duplicate it | Duplicate at position 2, subsequent siblings renumbered | DUP-01 |
| T-DUP-03 | Deep duplicate of Scene copies Scene + all Beats | `POST /nodes/{scene_id}/duplicate?deep=true` | HTTP 201, new Scene with all Beats copied, all new `node_id` values | DUP-02 |
| T-DUP-04 | Deep duplicate preserves content fields | Deep duplicate a node with `description`, `text`, `tags` | Copied nodes have identical content fields | DUP-02 |
| T-DUP-05 | Deep duplicate Part copies entire subtree | `POST /nodes/{part_id}/duplicate?deep=true` | HTTP 201, complete subtree copied with new node_ids | DUP-02 |
| T-DUP-06 | Shallow duplicate of Beat succeeds | `POST /nodes/{beat_id}/duplicate` | HTTP 201, copied Beat | DUP-01 |

### Error Cases

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-DUP-ERR-01 | Deep duplicate of Beat rejected | HTTP 400, `detail: "Beat nodes cannot be deep-copied as they have no children"` | DUP-03 |
| T-DUP-ERR-02 | Duplicate non-existent node | HTTP 404, `detail: "Node not found"` | DUP-04 |

### Isolation and Scope

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-DUP-ISO-01 | User A duplicates User B's node | HTTP 404 | SEC-01 |
| T-DUP-SCOPE-01 | Duplicate with `tree:reader` only token | HTTP 403 | CONSTITUTION II.2 |

---

## Part VIII — Unit Tests

These tests verify business logic in isolation without a running database.

| ID | Description | What to test | Requirement |
|----|-------------|-------------|-------------|
| T-UNIT-01 | Hierarchy validator — valid combinations | `is_valid_parent_child("part", None)` → True, `is_valid_parent_child("chapter", "part")` → True, all valid pairs | HIER-01 |
| T-UNIT-02 | Hierarchy validator — invalid combinations | `is_valid_parent_child("beat", "part")` → False, all invalid pairs | HIER-01 |
| T-UNIT-03 | Cycle detection — direct cycle | Node A → parent is Node A | UPDATE-03 |
| T-UNIT-04 | Cycle detection — indirect cycle | Node A → B → C, attempt to make C parent of A | UPDATE-03 |
| T-UNIT-05 | Sibling renumbering — insert at start | Insert at position 0 with 3 existing siblings | Siblings renumbered to 1, 2, 3 | REORDER-01 |
| T-UNIT-06 | Sibling renumbering — insert at end | Insert after last sibling | New sibling gets position = count | NODE-05 |
| T-UNIT-07 | Sibling renumbering — remove from middle | Delete position 1 of 3 | Remaining positions are 0, 1 | DELETE-01 |
| T-UNIT-08 | Position clamping | Request position 99 with 3 siblings | Returns 2 | REORDER-02 |
| T-UNIT-09 | Tag suffix on duplicate | `build_copy_tag("Chapter 1")` → `"Chapter 1 (copy)"` | DUP-01 |
| T-UNIT-10 | Beat deep-copy guard | `can_deep_copy("beat")` → False | DUP-03 |

---

## Part IX — Test Coverage Checklist

Before the refactor is considered complete, all of the following must have at least one passing test:

- [ ] Every happy-path case in Parts II–VII
- [ ] Every error case in Parts II–VII
- [ ] Every isolation case (User B cannot access User A's data)
- [ ] Every scope case (insufficient scope returns 403)
- [ ] All unit tests in Part VIII
- [ ] `GET /trees/stats` returns correct counts after creates and deletes
- [ ] Cascade delete verified: deleting a Part leaves no orphaned nodes for that account

---

*Co-Authored-By: Millie Kovacs / Claude Sonnet 4.6 <noreply@anthropic.com>*
