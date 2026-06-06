# Fabulator — Refactor Specification
## Normalised Adjacency-List Model

**Version:** 0.2
**Date:** 2026-06-06
**Status:** Draft — drives `refactor/normalised-node-model` branch
**Companion documents:** `CONSTITUTION.md`, `DESIGN.md`, `TEST_SPEC.md`
**Supersedes:** Design Document Part IV.1, Part III.1, DD-01, DD-03

---

## Part I — What This Refactor Does (Plain English)

The current Fabulator backend stores your entire narrative tree as a single JSON snapshot in MongoDB. Every time you create, update, or delete a node, the whole tree is serialised and saved as a new document. Loading a node means loading the entire tree first. There is no way to fetch a single node without fetching everything.

This refactor replaces that model with a normalised adjacency list. Each node becomes its own independent MongoDB document with a `parent_id` pointer to its parent. The tree structure is implicit in these pointers rather than explicit in a nested snapshot.

**What this means in practice:**

- Fetching a single node is a single document lookup — no tree loading
- Creating, updating, or deleting a node touches only that node's document (plus descendant cleanup on delete)
- The API is redesigned to reflect this — endpoints operate on individual nodes rather than loading and re-saving the whole tree
- The hierarchy (`Part → Chapter → Scene → Beat`) is enforced at both the application and MongoDB schema level
- treelib is removed entirely

**What is not changing:**

- Authentication, JWT, Redis blacklisting — unchanged
- User management endpoints — unchanged
- Account isolation model — unchanged
- The `user_collection` schema — unchanged

**Migration approach:**

There are no existing trees to migrate. The `tree_collection` is left in place and untouched. The new `node_collection` starts empty. Old snapshot data remains in MongoDB but is no longer read or written by the application.

---

## Part II — Data Model

### II.1 — Node Document Schema

Each node is stored as an independent MongoDB document in `node_collection`.

```
{
  "_id":         ObjectId,         // MongoDB auto-generated
  "node_id":     str (UUID4),      // application-level identifier — unique index
  "account_id":  str,              // bcrypt hash of username — tenant partition key
  "node_type":   str,              // "part" | "chapter" | "scene" | "beat"
  "parent_id":   str|null,         // UUID4 of parent node; null for Part (root)
  "position":    int,              // zero-based order among siblings
  "tag":         str,              // display name (e.g. "Chapter 1")
  "description": str|null,
  "text":        str|null,
  "previous":    str|null,         // narrative order hint (free text, not UUID)
  "next":        str|null,         // narrative order hint (free text, not UUID)
  "tags":        list[str],
  "created_at":  datetime (UTC),
  "updated_at":  datetime (UTC)
}
```

### II.2 — MongoDB JSON Schema Validator

`node_collection` MUST be created with a JSON Schema validator enforcing:

- `node_type` is one of: `"part"`, `"chapter"`, `"scene"`, `"beat"`
- `node_id` matches UUID4 pattern
- `account_id` is a non-empty string
- `tag` is a non-empty string
- `position` is a non-negative integer
- `tags` is an array of strings

Hierarchy parent-child rules (Part→Chapter→Scene→Beat) are enforced at application level only — the MongoDB validator enforces field types and enums, not relational constraints.

### II.3 — Required MongoDB Indexes

```
node_collection:
  { node_id: 1 }                      // unique
  { account_id: 1, parent_id: 1 }     // fetch children of a node
  { account_id: 1, node_type: 1 }     // fetch all nodes of a type
  { account_id: 1, node_id: 1 }       // ownership verification
```

---

## Part III — Hierarchy Rules

### III.1 — Node Type Hierarchy

```
null → Part → Chapter → Scene → Beat
```

| node_type | valid parent_type | can have children |
|-----------|------------------|-------------------|
| part      | null (root only) | yes (chapter only) |
| chapter   | part             | yes (scene only)   |
| scene     | chapter          | yes (beat only)    |
| beat      | scene            | no                 |

### III.2 — EARS Requirements — Hierarchy Enforcement

**HIER-01:** When a node creation request is received, the system SHALL validate that the `node_type` of the new node is the valid child type of the parent node's `node_type`, per the hierarchy table in III.1.

**HIER-02:** When a node creation request specifies `parent_id: null`, the system SHALL only permit `node_type: "part"`. Any other `node_type` with `parent_id: null` SHALL return HTTP 422 with message: `"Only nodes of type 'part' may be created without a parent"`.

**HIER-03:** When a hierarchy violation is detected on create or reparent, the system SHALL return HTTP 422 with message: `"Invalid parent-child relationship: a {child_type} cannot be placed under a {parent_type}"`.

**HIER-04:** When a node reparenting request is received (`PUT /nodes/{id}`), the system SHALL apply the same hierarchy validation as node creation before updating.

**HIER-05:** When a deletion request targets a node with descendants, the system SHALL delete the node and ALL descendants recursively in a single atomic operation.

---

## Part IV — API Specification

### IV.1 — Endpoint Surface

#### Node endpoints

| Method | Path | Scopes | Description |
|--------|------|--------|-------------|
| GET | /nodes | tree:reader | List all nodes for account (filterable) |
| GET | /nodes/{node_id} | tree:reader | Get single node by UUID |
| POST | /nodes | tree:writer | Create a new node |
| PUT | /nodes/{node_id} | tree:writer | Update node fields and/or reparent |
| DELETE | /nodes/{node_id} | tree:writer | Delete node and all descendants |
| GET | /nodes/{node_id}/children | tree:reader | Get direct children of a node |
| GET | /nodes/{node_id}/parent | tree:reader | Get parent of a node |
| GET | /nodes/{node_id}/ancestors | tree:reader | Get ordered path from root to node |
| GET | /nodes/{node_id}/siblings | tree:reader | Get sibling nodes |
| PUT | /nodes/{node_id}/reorder | tree:writer | Change position among siblings |
| POST | /nodes/{node_id}/duplicate | tree:writer | Copy node (shallow or deep) |

#### Tree-level endpoints

| Method | Path | Scopes | Description |
|--------|------|--------|-------------|
| GET | /trees/root | tree:reader | Get all root Part nodes for account |
| GET | /trees/leaves | tree:reader | Get all Beat nodes for account |
| GET | /trees/stats | tree:reader | Node count by type, max depth |

#### Removed endpoints

| Endpoint | Reason |
|----------|--------|
| GET /trees/{id} (prune) | Mutating GET — removed, not replaced |
| POST /trees/{id} (graft) | Replaced by POST /nodes with parent_id |
| GET /saves | No longer meaningful |
| GET /loads | No longer meaningful |
| GET /loads/{save_id} | No longer meaningful |
| DELETE /saves | No longer meaningful |

### IV.2 — Request Schemas

#### POST /nodes — CreateNodeRequest
```json
{
  "node_type":   "part | chapter | scene | beat",
  "parent_id":   "UUID4 string or null",
  "tag":         "1–100 character string",
  "description": "optional string or null",
  "text":        "optional string or null",
  "previous":    "optional string or null",
  "next":        "optional string or null",
  "tags":        ["optional list of strings"]
}
```

#### PUT /nodes/{node_id} — UpdateNodeRequest
```json
{
  "tag":         "optional string",
  "parent_id":   "optional UUID4 — triggers reparent",
  "description": "optional string or null",
  "text":        "optional string or null",
  "previous":    "optional string or null",
  "next":        "optional string or null",
  "tags":        ["optional list of strings"]
}
```

#### PUT /nodes/{node_id}/reorder — ReorderRequest
```json
{
  "position": "integer >= 0"
}
```

### IV.3 — Response Schemas

#### NodeResponse (all node read/write endpoints)
```json
{
  "node_id":     "UUID4 string",
  "node_type":   "part | chapter | scene | beat",
  "parent_id":   "UUID4 string or null",
  "position":    "integer",
  "tag":         "string",
  "description": "string or null",
  "text":        "string or null",
  "previous":    "string or null",
  "next":        "string or null",
  "tags":        ["list of strings"],
  "created_at":  "ISO 8601 datetime",
  "updated_at":  "ISO 8601 datetime"
}
```

#### AncestorsResponse (GET /nodes/{id}/ancestors)
```json
{
  "ancestors": [
    "ordered list of NodeResponse objects from root to immediate parent, inclusive"
  ]
}
```

#### TreeStatsResponse (GET /trees/stats)
```json
{
  "total_nodes": "integer",
  "by_type": {
    "part":    "integer",
    "chapter": "integer",
    "scene":   "integer",
    "beat":    "integer"
  },
  "max_depth": "integer"
}
```

#### ErrorResponse (all 4xx responses)
```json
{
  "detail": "human-readable error message string"
}
```

---

## Part V — EARS Behavioural Requirements

### V.1 — Node Creation

**NODE-01:** When `POST /nodes` is received with valid `node_type`, valid `parent_id`, valid `tag`, and a JWT with `tree:writer` scope, the system SHALL insert a new node document and return HTTP 201 with `NodeResponse`.

**NODE-02:** When `POST /nodes` is received with `parent_id: null` and `node_type` other than `"part"`, the system SHALL return HTTP 422 with `detail: "Only nodes of type 'part' may be created without a parent"`.

**NODE-03:** When `POST /nodes` is received and `parent_id` does not exist in `node_collection` for the authenticated `account_id`, the system SHALL return HTTP 404 with `detail: "Parent node not found"`.

**NODE-04:** When `POST /nodes` is received with a valid `parent_id` but a `node_type` that violates the hierarchy, the system SHALL return HTTP 422 with `detail: "Invalid parent-child relationship: a {child_type} cannot be placed under a {parent_type}"`.

**NODE-05:** When `POST /nodes` is received with a valid `parent_id`, the system SHALL set `position` to `max(sibling positions) + 1`. If no siblings exist, `position` SHALL be 0.

**NODE-06:** When `POST /nodes` is received with a `tag` field that is empty or whitespace only, the system SHALL return HTTP 422 with `detail: "tag must not be empty"`.

### V.2 — Node Retrieval

**READ-01:** When `GET /nodes/{node_id}` is received and the node exists and belongs to the authenticated account, the system SHALL return HTTP 200 with `NodeResponse`.

**READ-02:** When `GET /nodes/{node_id}` is received and the node does not exist or belongs to a different account, the system SHALL return HTTP 404 with `detail: "Node not found"`.

**READ-03:** When `GET /nodes` is received without query parameters, the system SHALL return HTTP 200 with a list of all `NodeResponse` objects for the account.

**READ-04:** When `GET /nodes?node_type={type}` is received, the system SHALL return HTTP 200 with only nodes of that type for the account.

**READ-05:** When `GET /nodes?node_type={invalid}` is received, the system SHALL return HTTP 422 with `detail: "node_type must be one of: part, chapter, scene, beat"`.

**READ-06:** When `GET /nodes/{node_id}/children` is received, the system SHALL return HTTP 200 with a list of `NodeResponse` objects where `parent_id == node_id`, ordered by `position` ascending.

**READ-07:** When `GET /nodes/{node_id}/children` is received for a node with no children, the system SHALL return HTTP 200 with an empty list.

**READ-08:** When `GET /nodes/{node_id}/parent` is received for a Part node (root), the system SHALL return HTTP 200 with `data: null`.

**READ-09:** When `GET /nodes/{node_id}/ancestors` is received, the system SHALL return HTTP 200 with `AncestorsResponse` containing nodes ordered from root to immediate parent, inclusive.

**READ-10:** When `GET /nodes/{node_id}/ancestors` is received for a Part node (root), the system SHALL return HTTP 200 with an empty `ancestors` list.

**READ-11:** When `GET /nodes/{node_id}/siblings` is received, the system SHALL return HTTP 200 with all nodes sharing the same `parent_id`, excluding the node itself, ordered by `position`.

**READ-12:** When `GET /trees/root` is received, the system SHALL return HTTP 200 with a list of all nodes where `parent_id == null` for the account.

**READ-13:** When `GET /trees/stats` is received, the system SHALL return HTTP 200 with `TreeStatsResponse`.

### V.3 — Node Update

**UPDATE-01:** When `PUT /nodes/{node_id}` is received with only content fields (`tag`, `description`, `text`, `previous`, `next`, `tags`), the system SHALL update only those fields and set `updated_at` to `datetime.now(timezone.utc)`, and return HTTP 200 with the updated `NodeResponse`.

**UPDATE-02:** When `PUT /nodes/{node_id}` is received with a new `parent_id`, the system SHALL validate the hierarchy rules. If invalid, return HTTP 422 with `detail: "Invalid parent-child relationship: a {child_type} cannot be placed under a {parent_type}"`.

**UPDATE-03:** When `PUT /nodes/{node_id}` is received with a `parent_id` that is a descendant of the node being moved, the system SHALL return HTTP 422 with `detail: "Cannot move a node into its own descendant"`.

**UPDATE-04:** When `PUT /nodes/{node_id}` is received and the node does not exist or belongs to a different account, the system SHALL return HTTP 404 with `detail: "Node not found"`.

**UPDATE-05:** When `PUT /nodes/{node_id}` is received with `parent_id` pointing to a node that does not exist or belongs to a different account, the system SHALL return HTTP 404 with `detail: "Parent node not found"`.

### V.4 — Node Deletion

**DELETE-01:** When `DELETE /nodes/{node_id}` is received and the node exists and belongs to the authenticated account, the system SHALL delete the node and all its descendants and return HTTP 200 with `detail: "Node and {n} descendants deleted"`.

**DELETE-02:** When `DELETE /nodes/{node_id}` is received and the node does not exist or belongs to a different account, the system SHALL return HTTP 404 with `detail: "Node not found"`.

**DELETE-03:** When `DELETE /nodes/{node_id}` is received for a leaf node (Beat with no children), the system SHALL delete only that node and return HTTP 200 with `detail: "Node and 0 descendants deleted"`.

### V.5 — Reorder

**REORDER-01:** When `PUT /nodes/{node_id}/reorder` is received with a valid `position` integer within the sibling range, the system SHALL update the `position` of the target node and renumber all siblings to maintain a contiguous zero-based sequence, and return HTTP 200 with the updated `NodeResponse`.

**REORDER-02:** When `PUT /nodes/{node_id}/reorder` is received with a `position` value greater than `max_sibling_index`, the system SHALL clamp to `max_sibling_index` and return HTTP 200.

**REORDER-03:** When `PUT /nodes/{node_id}/reorder` is received with a negative `position`, the system SHALL return HTTP 422 with `detail: "position must be a non-negative integer"`.

### V.6 — Duplicate

**DUP-01:** When `POST /nodes/{node_id}/duplicate` is received without `?deep=true`, the system SHALL create a shallow copy of the node only (no children), with a new `node_id`, `tag` set to `"{original_tag} (copy)"`, `position` set to `original_position + 1`, siblings renumbered accordingly, and return HTTP 201 with the new `NodeResponse`.

**DUP-02:** When `POST /nodes/{node_id}/duplicate?deep=true` is received for a node that is not a Beat, the system SHALL recursively copy the node and all descendants with new `node_id` values throughout, preserving structure, and return HTTP 201 with the root `NodeResponse` of the copied subtree.

**DUP-03:** When `POST /nodes/{node_id}/duplicate?deep=true` is received for a Beat node, the system SHALL return HTTP 400 with `detail: "Beat nodes cannot be deep-copied as they have no children"`.

**DUP-04:** When `POST /nodes/{node_id}/duplicate` is received and the node does not exist or belongs to a different account, the system SHALL return HTTP 404 with `detail: "Node not found"`.

---

## Part VI — Security Requirements

All security requirements from `CONSTITUTION.md` Part II remain in force. The following are specific to the new node endpoints:

**SEC-01:** Every node endpoint MUST verify that the target `node_id` belongs to the authenticated `account_id` before performing any read, write, or delete operation. A node belonging to another account MUST return HTTP 404, not HTTP 403.

**SEC-02:** `account_id` MUST NOT appear in any API response body.

**SEC-03:** All `node_id` path parameters MUST be validated as UUID4 via `Path(pattern=UUID_PATTERN)` before any database operation is attempted.

---

## Part VII — Acceptance Criteria Checklist

The refactor is complete when all of the following are true:

- [ ] All EARS requirements in Parts III, V, and VI are implemented and verified by the test spec
- [ ] `tree_collection` is no longer written to by any route handler
- [ ] treelib is removed from `requirements.txt`
- [ ] `node_collection` is created with JSON Schema validator (II.2) and indexes (II.3)
- [ ] All new endpoints have `response_model`, `summary`, `description`, and `tags` per Constitution III.3
- [ ] Isolation tests exist for every new endpoint
- [ ] Scope tests exist for every new endpoint
- [ ] Unit tests cover hierarchy validation, cycle detection, and sibling reordering
- [ ] `CONSTITUTION.md` Part I.2 and Part IV updated to reflect new model
- [ ] `DESIGN.md` Part IV.1, Part III.1, and DD-01 updated to reflect new model

---

*Co-Authored-By: Millie Kovacs / Claude Sonnet 4.6 <noreply@anthropic.com>*
