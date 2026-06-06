# Fabulator — Test Specification
## Normalised Adjacency-List Refactor

**Version:** 0.2
**Date:** 2026-06-06
**Maps to:** `SPEC.md` v0.3
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
| `work_a` | A valid Work belonging to User A |
| `work_b` | A valid Work belonging to User B |
| `part_node` | A valid Part node in `work_a` |
| `chapter_node` | A valid Chapter node under `part_node` |
| `scene_node` | A valid Scene node under `chapter_node` |
| `beat_node` | A valid Beat node under `scene_node` |

### I.2 — Valid Payloads

**Minimal valid Work:**
```json
{ "title": "My Novel" }
```

**Full valid Work:**
```json
{
  "title": "My Novel",
  "description": "A story about things",
  "author": "Philip Suggars",
  "tags": ["fiction", "drama"]
}
```

**Minimal valid Part:**
```json
{ "work_id": "{work_id}", "node_type": "part", "parent_id": null, "tag": "Act One" }
```

**Full valid Beat:**
```json
{
  "work_id": "{work_id}",
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

## Part II — Work CRUD Tests

### Happy Path

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-WORK-01 | Create a Work with title only | `{ "title": "My Novel" }` | HTTP 201, WorkResponse with `work_id` (UUID4), `title`, timestamps | WORK-01 |
| T-WORK-02 | Create a Work with all fields | Full valid Work payload | HTTP 201, all fields present in WorkResponse | WORK-01 |
| T-WORK-03 | List all Works returns account's Works | Create 2 Works, call `GET /works` | HTTP 200, list of 2 WorkResponse objects, ordered by `created_at` descending | WORK-03 |
| T-WORK-04 | List Works returns empty list when none exist | `GET /works` with no Works | HTTP 200, empty list | WORK-03 |
| T-WORK-05 | Get single Work by ID | `GET /works/{work_id}` | HTTP 200, correct WorkResponse | WORK-04 |
| T-WORK-06 | Update Work title | `PUT /works/{work_id}` `{ "title": "New Title" }` | HTTP 200, `title` updated, `updated_at` > `created_at` | WORK-06 |
| T-WORK-07 | Update author cascades to all child nodes | Work with 4 nodes, `PUT /works/{work_id}` `{ "author": "New Author" }` | HTTP 200, all 4 nodes have `author: "New Author"` | WORK-07 |
| T-WORK-08 | Update non-author field does not cascade | `PUT /works/{work_id}` `{ "title": "New Title" }` | Node `author` fields unchanged | WORK-06 |
| T-WORK-09 | Delete Work deletes Work and all nodes | Work with 4 nodes, `DELETE /works/{work_id}` | HTTP 200, `detail: "Work and 4 nodes deleted"`, nodes no longer retrievable | WORK-08 |
| T-WORK-10 | Delete Work with no nodes | `DELETE /works/{work_id}` with empty Work | HTTP 200, `detail: "Work and 0 nodes deleted"` | WORK-08 |

### Error Cases

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-WORK-ERR-01 | Create Work with empty title | `{ "title": "" }` | HTTP 422, `detail: "title must not be empty"` | WORK-02 |
| T-WORK-ERR-02 | Create Work with whitespace title | `{ "title": "   " }` | HTTP 422, `detail: "title must not be empty"` | WORK-02 |
| T-WORK-ERR-03 | Get non-existent Work | `GET /works/{valid_uuid_not_in_db}` | HTTP 404, `detail: "Work not found"` | WORK-05 |
| T-WORK-ERR-04 | Update non-existent Work | `PUT /works/{valid_uuid_not_in_db}` | HTTP 404, `detail: "Work not found"` | WORK-05 |
| T-WORK-ERR-05 | Delete non-existent Work | `DELETE /works/{valid_uuid_not_in_db}` | HTTP 404, `detail: "Work not found"` | WORK-09 |
| T-WORK-ERR-06 | Invalid UUID format in path | `GET /works/not-a-uuid` | HTTP 422 | SEC-04 |

### Isolation and Scope

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-WORK-ISO-01 | User A gets User B's Work | HTTP 404, `detail: "Work not found"` | SEC-02 |
| T-WORK-ISO-02 | User A updates User B's Work | HTTP 404 | SEC-02 |
| T-WORK-ISO-03 | User A deletes User B's Work | HTTP 404 | SEC-02 |
| T-WORK-ISO-04 | `GET /works` only returns User A's Works | No User B Works in list | WORK-03, SEC-02 |
| T-WORK-SCOPE-01 | Create Work with `tree:reader` only token | HTTP 403 | CONSTITUTION II.2 |
| T-WORK-SCOPE-02 | Delete Work with `tree:reader` only token | HTTP 403 | CONSTITUTION II.2 |

---

## Part III — Node Creation Tests

### Happy Path

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-CREATE-01 | Create a Part with no parent | `work_id`, `node_type: "part"`, `parent_id: null`, `tag: "Act One"` | HTTP 201, NodeResponse with `node_type: "part"`, `parent_id: null`, `position: 0`, `work_id` present, `author` copied from Work | NODE-01 |
| T-CREATE-02 | Create a Chapter under a Part | `node_type: "chapter"`, `parent_id: {part_id}` | HTTP 201, NodeResponse with `parent_id == part_id`, `position: 0` | NODE-01 |
| T-CREATE-03 | Create a Scene under a Chapter | `node_type: "scene"`, `parent_id: {chapter_id}` | HTTP 201, `node_type: "scene"` | NODE-01 |
| T-CREATE-04 | Create a Beat under a Scene | `node_type: "beat"`, `parent_id: {scene_id}` | HTTP 201, `node_type: "beat"` | NODE-01 |
| T-CREATE-05 | Author is copied from Work at creation | Work has `author: "Philip"`, create any node | Node `author == "Philip"` | NODE-01 |
| T-CREATE-06 | Author is null when Work has no author | Work has no author, create node | Node `author == null` | NODE-01 |
| T-CREATE-07 | Second Chapter gets position 1 | Create two Chapters under same Part | Second Chapter has `position: 1` | NODE-05 |
| T-CREATE-08 | First child gets position 0 | Create Chapter under Part with no children | `position: 0` | NODE-05 |
| T-CREATE-09 | Create node with all optional fields | Full valid Beat payload | HTTP 201, all fields in response | NODE-01 |
| T-CREATE-10 | `created_at` and `updated_at` set on creation | Create any node | Both timestamps present, equal, UTC | NODE-01 |

### Error Cases

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-CREATE-ERR-01 | Chapter with no parent rejected | `node_type: "chapter"`, `parent_id: null` | HTTP 422, `detail: "Only nodes of type 'part' may be created without a parent"` | NODE-02, HIER-02 |
| T-CREATE-ERR-02 | Scene with no parent rejected | `node_type: "scene"`, `parent_id: null` | HTTP 422, same message | NODE-02 |
| T-CREATE-ERR-03 | Beat with no parent rejected | `node_type: "beat"`, `parent_id: null` | HTTP 422, same message | NODE-02 |
| T-CREATE-ERR-04 | Chapter under Scene rejected | `node_type: "chapter"`, `parent_id: {scene_id}` | HTTP 422, `detail: "Invalid parent-child relationship: a chapter cannot be placed under a scene"` | NODE-04, HIER-03 |
| T-CREATE-ERR-05 | Part under Chapter rejected | `node_type: "part"`, `parent_id: {chapter_id}` | HTTP 422, hierarchy violation message | NODE-04 |
| T-CREATE-ERR-06 | Beat under Part rejected | `node_type: "beat"`, `parent_id: {part_id}` | HTTP 422, hierarchy violation message | NODE-04 |
| T-CREATE-ERR-07 | Non-existent parent_id | `parent_id: {valid_uuid_not_in_db}` | HTTP 404, `detail: "Parent node not found"` | NODE-03 |
| T-CREATE-ERR-08 | Non-existent work_id | `work_id: {valid_uuid_not_in_db}` | HTTP 404, `detail: "Work not found"` | NODE-07 |
| T-CREATE-ERR-09 | Empty tag rejected | `tag: ""` | HTTP 422, `detail: "tag must not be empty"` | NODE-06 |
| T-CREATE-ERR-10 | Whitespace-only tag rejected | `tag: "   "` | HTTP 422, `detail: "tag must not be empty"` | NODE-06 |
| T-CREATE-ERR-11 | Invalid node_type rejected | `node_type: "paragraph"` | HTTP 422 | NODE-04 |
| T-CREATE-ERR-12 | Invalid UUID for parent_id | `parent_id: "not-a-uuid"` | HTTP 422 | SEC-04 |

### Isolation and Scope

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-CREATE-ISO-01 | User B's parent_id used by User A | HTTP 404, `detail: "Parent node not found"` | NODE-03, SEC-01 |
| T-CREATE-ISO-02 | User B's work_id used by User A | HTTP 404, `detail: "Work not found"` | NODE-07, SEC-02 |
| T-CREATE-SCOPE-01 | Create node with `tree:reader` only token | HTTP 403 | CONSTITUTION II.2 |

---

## Part IV — Node Retrieval Tests

### Happy Path

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-READ-01 | Get single node by ID | `GET /nodes/{node_id}` | HTTP 200, correct NodeResponse including `work_id` and `author` | READ-01 |
| T-READ-02 | Get all nodes for Work | `GET /works/{work_id}/nodes` with 4-node tree | HTTP 200, list of 4 NodeResponse objects | READ-03 |
| T-READ-03 | Filter by node_type | `GET /works/{work_id}/nodes?node_type=beat` | HTTP 200, only Beat nodes | READ-04 |
| T-READ-04 | Get children ordered by position | `GET /nodes/{part_id}/children` | HTTP 200, Chapters ordered by position | READ-06 |
| T-READ-05 | Get children of Beat returns empty list | `GET /nodes/{beat_id}/children` | HTTP 200, empty list | READ-07 |
| T-READ-06 | Get parent returns parent node | `GET /nodes/{chapter_id}/parent` | HTTP 200, Part NodeResponse | READ-08 |
| T-READ-07 | Get parent of Part returns null | `GET /nodes/{part_id}/parent` | HTTP 200, `data: null` | READ-08 |
| T-READ-08 | Get ancestors of Beat returns [Part, Chapter, Scene] | `GET /nodes/{beat_id}/ancestors` | HTTP 200, AncestorsResponse with 3 nodes in order | READ-09 |
| T-READ-09 | Get ancestors of Part returns empty list | `GET /nodes/{part_id}/ancestors` | HTTP 200, `ancestors: []` | READ-10 |
| T-READ-10 | Get siblings excludes self | `GET /nodes/{chapter_id}/siblings` | HTTP 200, other Chapters under same Part, self excluded | READ-11 |
| T-READ-11 | Get siblings of only child returns empty list | `GET /nodes/{chapter_id}/siblings` when no other Chapters | HTTP 200, empty list | READ-11 |
| T-READ-12 | Get root returns Part nodes for Work | `GET /works/{work_id}/nodes/root` | HTTP 200, Part nodes only | READ-12 |
| T-READ-13 | Get stats returns correct counts | `GET /works/{work_id}/stats` with known tree | HTTP 200, correct `by_type` counts and `max_depth` | READ-13 |
| T-READ-14 | Get leaves returns all Beat nodes for Work | `GET /works/{work_id}/nodes/leaves` | HTTP 200, only Beat nodes | SPEC IV.1 |

### Error Cases

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-READ-ERR-01 | Get non-existent node | HTTP 404, `detail: "Node not found"` | READ-02 |
| T-READ-ERR-02 | Get nodes for non-existent Work | HTTP 404, `detail: "Work not found"` | WORK-05 |
| T-READ-ERR-03 | Invalid UUID format in path | HTTP 422 | SEC-04 |
| T-READ-ERR-04 | Invalid node_type filter | HTTP 422, `detail: "node_type must be one of: part, chapter, scene, beat"` | READ-05 |

### Isolation and Scope

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-READ-ISO-01 | User A gets User B's node | HTTP 404, `detail: "Node not found"` | SEC-01 |
| T-READ-ISO-02 | User A gets nodes for User B's Work | HTTP 404, `detail: "Work not found"` | SEC-02 |
| T-READ-ISO-03 | User A gets children of User B's node | HTTP 404 | SEC-01 |
| T-READ-ISO-04 | `GET /works/{work_id}/nodes` only returns nodes for that Work | Nodes from other Works not included | READ-03 |
| T-READ-SCOPE-01 | Get node with no token | HTTP 401 | CONSTITUTION II.2 |

---

## Part V — Node Update Tests

### Happy Path

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-UPDATE-01 | Update tag only | `{ "tag": "New name" }` | HTTP 200, `tag` updated, `updated_at` > `created_at` | UPDATE-01 |
| T-UPDATE-02 | Update text content fields | `description`, `text`, `previous`, `next`, `tags` | HTTP 200, all fields updated | UPDATE-01 |
| T-UPDATE-03 | Reparent Chapter to a different Part | `parent_id: {other_part_id}` | HTTP 200, `parent_id` updated | UPDATE-02 |
| T-UPDATE-04 | `updated_at` is set on every update | Any update | `updated_at` later than before request | UPDATE-01 |

### Error Cases

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-UPDATE-ERR-01 | Reparent with hierarchy violation | HTTP 422, hierarchy violation message | UPDATE-02, HIER-03 |
| T-UPDATE-ERR-02 | Move node into its own descendant | HTTP 422, `detail: "Cannot move a node into its own descendant"` | UPDATE-03 |
| T-UPDATE-ERR-03 | Update non-existent node | HTTP 404, `detail: "Node not found"` | UPDATE-04 |
| T-UPDATE-ERR-04 | Reparent to non-existent parent | HTTP 404, `detail: "Parent node not found"` | UPDATE-05 |
| T-UPDATE-ERR-05 | Invalid UUID in path | HTTP 422 | SEC-04 |

### Isolation and Scope

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-UPDATE-ISO-01 | User A updates User B's node | HTTP 404 | SEC-01 |
| T-UPDATE-ISO-02 | User A reparents to User B's parent node | HTTP 404, `detail: "Parent node not found"` | UPDATE-05, SEC-01 |
| T-UPDATE-SCOPE-01 | Update with `tree:reader` only token | HTTP 403 | CONSTITUTION II.2 |

---

## Part VI — Node Deletion Tests

### Happy Path

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-DELETE-01 | Delete leaf Beat | `DELETE /nodes/{beat_id}` | HTTP 200, `detail: "Node and 0 descendants deleted"` | DELETE-01, DELETE-03 |
| T-DELETE-02 | Delete Chapter cascades to Scenes and Beats | Chapter with 2 Scenes, 4 Beats | HTTP 200, `detail: "Node and 6 descendants deleted"` | DELETE-01, HIER-05 |
| T-DELETE-03 | Delete Part deletes entire subtree | `DELETE /nodes/{part_id}` | HTTP 200, correct descendant count | DELETE-01 |
| T-DELETE-04 | Deleted node not retrievable | Delete then `GET /nodes/{id}` | HTTP 404 | DELETE-01 |
| T-DELETE-05 | Deleted node's children not retrievable | Delete Chapter, GET child Scene | HTTP 404 | DELETE-01, HIER-05 |

### Error Cases

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-DELETE-ERR-01 | Delete non-existent node | HTTP 404, `detail: "Node not found"` | DELETE-02 |
| T-DELETE-ERR-02 | Invalid UUID in path | HTTP 422 | SEC-04 |

### Isolation and Scope

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-DELETE-ISO-01 | User A deletes User B's node | HTTP 404 | SEC-01 |
| T-DELETE-SCOPE-01 | Delete with `tree:reader` only token | HTTP 403 | CONSTITUTION II.2 |

---

## Part VII — Reorder Tests

### Happy Path

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-REORDER-01 | Move Chapter from position 2 to 0 | 3 Chapters, reorder last to 0 | Target at 0, others renumbered to 1 and 2 | REORDER-01 |
| T-REORDER-02 | Reorder to current position is a no-op | Reorder to same position | HTTP 200, no change | REORDER-01 |
| T-REORDER-03 | Position clamped when exceeds sibling count | 3 siblings, request position 99 | HTTP 200, placed at position 2 | REORDER-02 |
| T-REORDER-04 | Positions remain contiguous after reorder | Any reorder | All sibling positions form zero-based contiguous sequence | REORDER-01 |

### Error Cases

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-REORDER-ERR-01 | Negative position | HTTP 422, `detail: "position must be a non-negative integer"` | REORDER-03 |
| T-REORDER-ERR-02 | Reorder non-existent node | HTTP 404, `detail: "Node not found"` | SEC-01 |

### Isolation and Scope

| ID | Description | Expected | Requirement |
|----|-------------|----------|-------------|
| T-REORDER-ISO-01 | User A reorders User B's node | HTTP 404 | SEC-01 |
| T-REORDER-SCOPE-01 | Reorder with `tree:reader` only token | HTTP 403 | CONSTITUTION II.2 |

---

## Part VIII — Duplicate Tests

### Happy Path

| ID | Description | Input | Expected | Requirement |
|----|-------------|-------|----------|-------------|
| T-DUP-01 | Shallow duplicate of Chapter | `POST /nodes/{chapter_id}/duplicate` | HTTP 201, `tag: "Chapter 1 (copy)"`, new `node_id`, same `parent_id` and `work_id`, no children | DUP-01 |
| T-DUP-02 | Shallow duplicate gets position after original | Original at position 1 | Duplicate at position 2, subsequent siblings renumbered | DUP-01 |
| T-DUP-03 | Deep duplicate of Scene copies Scene + all Beats | `?deep=true` on Scene | HTTP 201, new Scene with all Beats, all new `node_id` values | DUP-02 |
| T-DUP-04 | Deep duplicate preserves content and author | Deep duplicate node with `description`, `tags`, `author` | Copied nodes have identical content and `author` | DUP-02 |
| T-DUP-05 | Deep duplicate Part copies entire subtree | `?deep=true` on Part | HTTP 201, complete subtree with new node_ids | DUP-02 |
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

## Part IX — Unit Tests

| ID | Description | What to test | Requirement |
|----|-------------|-------------|-------------|
| T-UNIT-01 | Hierarchy validator — valid combinations | `is_valid_parent_child("part", None)` → True, all valid pairs | HIER-01 |
| T-UNIT-02 | Hierarchy validator — invalid combinations | `is_valid_parent_child("beat", "part")` → False, all invalid pairs | HIER-01 |
| T-UNIT-03 | Cycle detection — direct cycle | Node A with parent_id pointing to itself | UPDATE-03 |
| T-UNIT-04 | Cycle detection — indirect cycle | A→B→C, attempt to make C parent of A | UPDATE-03 |
| T-UNIT-05 | Sibling renumbering — insert at start | Insert at position 0 with 3 existing siblings | Existing siblings shift to 1, 2, 3 | REORDER-01 |
| T-UNIT-06 | Sibling renumbering — insert at end | Insert after last sibling | New sibling gets position = count | NODE-05 |
| T-UNIT-07 | Sibling renumbering — remove from middle | Delete position 1 of 3 | Remaining positions are 0, 1 | DELETE-01 |
| T-UNIT-08 | Position clamping | Request position 99 with 3 siblings | Returns 2 | REORDER-02 |
| T-UNIT-09 | Tag suffix on duplicate | `build_copy_tag("Chapter 1")` → `"Chapter 1 (copy)"` | DUP-01 |
| T-UNIT-10 | Beat deep-copy guard | `can_deep_copy("beat")` → False | DUP-03 |
| T-UNIT-11 | Author propagation on node create | Node created from Work with `author: "X"` → node `author == "X"` | NODE-01 |
| T-UNIT-12 | Author null propagation | Node created from Work with no author → node `author == null` | NODE-01 |

---

## Part X — Test Coverage Checklist

Before the refactor is considered complete, all of the following must have at least one passing test:

- [ ] Every happy-path case in Parts II–VIII
- [ ] Every error case in Parts II–VIII
- [ ] Every isolation case (User B cannot access User A's data)
- [ ] Every scope case (insufficient scope returns 403)
- [ ] All unit tests in Part IX
- [ ] Author cascade: updating Work author updates all child nodes
- [ ] Work delete: no orphaned nodes remain after Work deletion
- [ ] Cascade delete: deleting a Part leaves no orphaned nodes for that Work
- [ ] `GET /works/{work_id}/stats` returns correct counts after creates and deletes

---

*Co-Authored-By: Millie Kovacs / Claude Sonnet 4.6 <noreply@anthropic.com>*
