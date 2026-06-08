# Fabulator API — Consolidated Requirements

**Version:** 1.0  
**Branch:** `refactor/normalised-node-model`  
**Source specifications:** See feature docs in subfolders of `specification/`

---

## Introduction

This document consolidates all functional requirements, non-functional requirements, and correctness properties for the Fabulator normalised adjacency-list API. It is the single authoritative requirements document for the refactored backend, mapping to the seven feature specifications in the `specification/` directory tree.

**Feature groups covered:**

| # | Feature Group | Spec File | Status |
|---|--------------|-----------|--------|
| 1 | Work CRUD | `../work-crud/feature.md` | Complete |
| 2 | Node CRUD | `node-crud/feature.md` | Complete |
| 3 | Node Hierarchy | `node-hierarchy/feature.md` | Complete |
| 4 | Node Navigation | `node-navigation/feature.md` | Partially complete (DB done; API endpoints missing) |
| 5 | Node Reorder | `node-reorder/feature.md` | Partially complete (DB done; API endpoint missing) |
| 6 | Node Duplicate | `node-duplicate/feature.md` | Partially complete (DB done; API endpoint missing) |
| 7 | MongoDB Setup | `mongodb-setup/feature.md` | Complete |

**Normative references:** `CONSTITUTION.md`, `DESIGN.md`

---

## Glossary

| Term | Definition |
|------|-----------|
| **Work** | A MongoDB document in `work_collection` representing one narrative project. Top-level container for all Nodes. |
| **work_id** | UUID4 string. Primary key for a Work. Never MongoDB's `_id`. |
| **Node** | A MongoDB document in `node_collection` representing one structural unit (Part / Chapter / Scene / Beat). |
| **node_id** | UUID4 string. Primary key for a Node. |
| **account_id** | bcrypt hash of the user's username. Universal tenant partition key. MUST NEVER appear in any API response body. (CONSTITUTION I.4) |
| **parent_id** | UUID4 foreign key pointing to a node's parent. `null` for root Part nodes. |
| **node_type** | Enum: `"part"` \| `"chapter"` \| `"scene"` \| `"beat"`. Strict hierarchy enforced at application and DB level. |
| **position** | Zero-based integer ordering among siblings sharing the same `parent_id`. |
| **tag** | Display name of a Node. Required, 1–200 chars, whitespace stripped. |
| **author** | Free-text attribution on a Work. Denormalised onto every child Node at creation; cascaded via `update_many` when updated. (CONSTITUTION I.7) |
| **hierarchy** | Fixed type chain: `null → part → chapter → scene → beat`. No levels may be skipped. |
| **_VALID_CHILD** | `{None: "part", "part": "chapter", "chapter": "scene", "scene": "beat", "beat": None}`. Encodes the complete hierarchy. |
| **is_valid_parent_child(parent_type, child_type)** | Module-level function returning True iff `_VALID_CHILD.get(parent_type) == child_type`. |
| **would_create_cycle** | `NodeStorage` async method. Returns True if setting `new_parent_id` as parent of `node_id` would form a cycle. |
| **Beat guard** | Check preventing duplication of Beat (leaf) nodes. Applied at API layer before any DB call. |
| **cascade delete** | BFS traversal from a node, collecting all descendant IDs, then single `delete_many`. |
| **author cascade** | Bulk `update_many` on `node_collection` triggered when Work `author` changes. |
| **setup_collections** | `async def setup_collections(db)`. Idempotent startup function creating validators and indexes. |
| **_WORK_VALIDATOR** | `$jsonSchema` dict applied to `work_collection`. |
| **_NODE_VALIDATOR** | `$jsonSchema` dict applied to `node_collection`. Enforces `node_type` enum, `position >= 0`, UUID4 patterns. |
| **shallow duplicate** | Copy of a node without children. New UUID4, tag gets `" (copy)"` suffix, position is `original.position + 1`. |
| **deep duplicate** | Recursive copy of a node and all descendants. All copies get fresh UUID4 `node_id` values. |
| **WorkResponse** | Pydantic response model: `work_id`, `title`, `description`, `author`, `tags`, `created_at`, `updated_at`. No `account_id`. |
| **NodeResponse** | Pydantic response model: `node_id`, `work_id`, `author`, `node_type`, `parent_id`, `position`, `tag`, `description`, `text`, `previous`, `next`, `tags`, `created_at`, `updated_at`. No `account_id`. |
| **AncestorsResponse** | `{"ancestors": [NodeResponse, ...]}`. Ordered root-first. |
| **WorkStatsResponse** | `{"work_id": str, "total_nodes": int, "by_type": dict, "max_depth": int}`. |
| **ReorderRequest** | `{"position": int}`. Validates `position >= 0`. |
| **UUID4 pattern** | `r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"` |
| **idempotent** | Calling `setup_collections` multiple times produces the same result as calling it once. |

---

## Functional Requirements

### Requirement 1: Create Work

**Feature group:** Work CRUD (`../work-crud/feature.md`)  
**User Story:** As an authenticated writer, I want to create a new narrative Work, so that I can organise a set of story nodes under a named project.  
**Endpoint:** `POST /works` — scope: `tree:writer` — returns `201 WorkResponse`

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:writer` scope WHEN `POST /works` is called with `{"title": "My Novel", "author": "Jane Doe", "tags": ["fiction"]}` THEN the server returns HTTP 201 with `work_id` (UUID4), `title: "My Novel"`, `author: "Jane Doe"`, `tags: ["fiction"]`, ISO8601 `created_at`/`updated_at`, and no `account_id`.
2. GIVEN a valid JWT WHEN `POST /works` is called with `{"title": "   "}` (whitespace-only) THEN the server returns HTTP 422.
3. GIVEN a valid JWT WHEN `POST /works` is called with a `tags` list of 51 items THEN the server returns HTTP 422.
4. GIVEN no Authorization header WHEN `POST /works` is called THEN the server returns HTTP 401.
5. GIVEN a JWT with only `tree:reader` scope WHEN `POST /works` is called THEN the server returns HTTP 403 with `detail: "Insufficient permissions to complete action"`.
6. GIVEN a database `ConnectionFailure` WHEN `POST /works` is called THEN the server returns HTTP 503 with `detail: "Database error"`.

---

### Requirement 2: List Works

**Feature group:** Work CRUD (`../work-crud/feature.md`)  
**User Story:** As an authenticated reader, I want to list all my Works ordered by creation date, so that I can see my projects at a glance.  
**Endpoint:** `GET /works` — scope: `tree:reader` — returns `200 list[WorkResponse]`

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:reader` scope and at least two Works WHEN `GET /works` is called THEN the server returns HTTP 200 with Works ordered by `created_at` descending.
2. GIVEN a valid JWT with no Works WHEN `GET /works` is called THEN the server returns HTTP 200 with an empty array `[]`.
3. GIVEN User A has Works and User B is authenticated WHEN User B calls `GET /works` THEN User B receives only their own Works.
4. GIVEN no Authorization header WHEN `GET /works` is called THEN the server returns HTTP 401.

---

### Requirement 3: Get Single Work

**Feature group:** Work CRUD (`../work-crud/feature.md`)  
**User Story:** As an authenticated reader, I want to fetch a single Work by its ID, so that I can display its details.  
**Endpoint:** `GET /works/{work_id}` — scope: `tree:reader` — returns `200 WorkResponse`

#### Acceptance Criteria

1. GIVEN a valid JWT and a `work_id` belonging to the authenticated account WHEN `GET /works/{work_id}` is called THEN the server returns HTTP 200 with `WorkResponse`.
2. GIVEN a valid JWT WHEN `GET /works/{work_id}` is called with a non-existent `work_id` THEN the server returns HTTP 404 with `detail: "Work not found"`.
3. GIVEN User A owns Work W and User B is authenticated WHEN User B calls `GET /works/{W.work_id}` THEN the server returns HTTP 404 (not 403).
4. GIVEN a valid JWT WHEN `GET /works/not-a-uuid` is called THEN the server returns HTTP 422.

---

### Requirement 4: Update Work

**Feature group:** Work CRUD (`../work-crud/feature.md`)  
**User Story:** As an authenticated writer, I want to update Work metadata and have `author` changes automatically propagated to all child nodes.  
**Endpoint:** `PUT /works/{work_id}` — scope: `tree:writer` — returns `200 WorkResponse`

#### Acceptance Criteria

1. GIVEN a valid JWT and an owned Work WHEN `PUT /works/{work_id}` is called with `{"title": "Updated Title"}` THEN the server returns HTTP 200 with `title: "Updated Title"` and a refreshed `updated_at`.
2. GIVEN a valid JWT and a Work with child nodes WHEN `PUT /works/{work_id}` is called with `{"author": "New Author"}` THEN all nodes for that work in `node_collection` have `author: "New Author"`.
3. GIVEN a valid JWT WHEN `PUT /works/{work_id}` is called with a non-existent or cross-account `work_id` THEN the server returns HTTP 404 with `detail: "Work not found"`.
4. GIVEN a valid JWT with `tree:reader` scope only WHEN `PUT /works/{work_id}` is called THEN the server returns HTTP 403.

---

### Requirement 5: Delete Work with Node Cascade

**Feature group:** Work CRUD (`../work-crud/feature.md`)  
**User Story:** As an authenticated writer, I want to delete a Work and all its associated nodes in one operation.  
**Endpoint:** `DELETE /works/{work_id}` — scope: `tree:writer` — returns `200 {"detail": "Work deleted. {N} node(s) removed."}`

#### Acceptance Criteria

1. GIVEN a valid JWT and a Work with 3 child nodes WHEN `DELETE /works/{work_id}` is called THEN the server returns HTTP 200 with `detail: "Work deleted. 3 node(s) removed."` and no documents remain in either collection for that `work_id`.
2. GIVEN a valid JWT and a Work with no nodes WHEN `DELETE /works/{work_id}` is called THEN the server returns HTTP 200 with `detail: "Work deleted. 0 node(s) removed."`.
3. GIVEN a valid JWT WHEN `DELETE /works/{work_id}` is called with a non-existent or cross-account `work_id` THEN the server returns HTTP 404 with `detail: "Work not found"`.

---

### Requirement 6: Create Node

**Feature group:** Node CRUD (`node-crud/feature.md`)  
**User Story:** As an authenticated writer, I want to create a node within a Work, so that I can build my narrative hierarchy.  
**Endpoint:** `POST /nodes` — scope: `tree:writer` — returns `201 NodeResponse`

#### Acceptance Criteria

1. GIVEN a valid JWT and a Work `W` with no nodes WHEN `POST /nodes` is called with `{"work_id": W.work_id, "node_type": "part", "tag": "Part One"}` THEN the server returns HTTP 201 with `node_type: "part"`, `parent_id: null`, `position: 0`, and `author` equal to the Work's `author`.
2. GIVEN a Part node `P` WHEN `POST /nodes` is called with `{"node_type": "chapter", "parent_id": P.node_id, ...}` THEN the server returns HTTP 201 with `parent_id: P.node_id`, `position: 0`.
3. GIVEN a third Part node is created when two already exist THEN `position` is 2.
4. GIVEN a valid JWT WHEN `POST /nodes` is called with a non-existent `work_id` THEN the server returns HTTP 404 with `detail: "Work not found"`.
5. GIVEN a valid JWT WHEN `POST /nodes` is called with a non-existent `parent_id` THEN the server returns HTTP 404 with `detail: "Parent node not found"`.
6. GIVEN a Part parent WHEN `POST /nodes` is called with `node_type: "scene"` THEN the server returns HTTP 422 with `detail: "A scene cannot be a child of a part"`.
7. GIVEN no `parent_id` and `node_type: "chapter"` WHEN `POST /nodes` is called THEN the server returns HTTP 422 with `detail: "Only 'part' nodes may have no parent"`.
8. GIVEN a JWT with `tree:reader` scope only WHEN `POST /nodes` is called THEN the server returns HTTP 403.

---

### Requirement 7: List Nodes

**Feature group:** Node CRUD (`node-crud/feature.md`)  
**User Story:** As an authenticated reader, I want to list all nodes for a Work (optionally filtered by type).  
**Endpoint:** `GET /works/{work_id}/nodes` — scope: `tree:reader` — returns `200 list[NodeResponse]`

#### Acceptance Criteria

1. GIVEN a valid JWT and a Work with 3 nodes of different types WHEN `GET /works/{work_id}/nodes` is called THEN the server returns HTTP 200 with all 3 nodes.
2. GIVEN a Work with 2 Part and 2 Chapter nodes WHEN `GET /works/{work_id}/nodes?node_type=part` is called THEN only the 2 Part nodes are returned.
3. GIVEN a valid JWT WHEN called with an invalid `node_type` value THEN the server returns HTTP 422.
4. GIVEN a valid JWT WHEN called with a non-existent or cross-account `work_id` THEN the server returns HTTP 404 with `detail: "Work not found"`.

---

### Requirement 8: Get Single Node

**Feature group:** Node CRUD (`node-crud/feature.md`)  
**User Story:** As an authenticated reader, I want to fetch a specific node by its ID.  
**Endpoint:** `GET /nodes/{node_id}` — scope: `tree:reader` — returns `200 NodeResponse`

#### Acceptance Criteria

1. GIVEN a valid JWT and an owned `node_id` WHEN `GET /nodes/{node_id}` is called THEN the server returns HTTP 200 with the full `NodeResponse`.
2. GIVEN a valid JWT WHEN `GET /nodes/{node_id}` is called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.
3. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `GET /nodes/{N.node_id}` THEN the server returns HTTP 404 (not 403).
4. GIVEN a valid JWT WHEN `GET /nodes/not-a-uuid` is called THEN the server returns HTTP 422.

---

### Requirement 9: Update Node

**Feature group:** Node CRUD (`node-crud/feature.md`)  
**User Story:** As an authenticated writer, I want to update node content or reparent a node.  
**Endpoint:** `PUT /nodes/{node_id}` — scope: `tree:writer` — returns `200 NodeResponse`

#### Acceptance Criteria

1. GIVEN a valid JWT and an owned node WHEN `PUT /nodes/{node_id}` is called with `{"tag": "Revised Title"}` THEN the server returns HTTP 200 with updated `tag` and refreshed `updated_at`.
2. GIVEN a Chapter node with parent Part `P1` and another Part `P2` WHEN `PUT /nodes/{chapter_id}` is called with `{"parent_id": P2.node_id}` THEN the chapter's `parent_id` is now `P2.node_id`.
3. GIVEN a Part node `A` with Chapter child `B` WHEN `PUT /nodes/{A.node_id}` is called with `{"parent_id": B.node_id}` THEN the server returns HTTP 422 with `detail: "Reparenting would create a cycle"`.
4. GIVEN a Part node `P` and Scene node `S` WHEN `PUT /nodes/{P.node_id}` is called with `{"parent_id": S.node_id}` THEN the server returns HTTP 422 with `detail: "Invalid hierarchy: a part cannot be a child of a scene"`.
5. GIVEN a valid JWT WHEN `PUT /nodes/{node_id}` is called on a non-existent or cross-account node THEN the server returns HTTP 404 with `detail: "Node not found"`.

---

### Requirement 10: Delete Node with Cascade

**Feature group:** Node CRUD (`node-crud/feature.md`)  
**User Story:** As an authenticated writer, I want to delete a node and all of its descendants.  
**Endpoint:** `DELETE /nodes/{node_id}` — scope: `tree:writer` — returns `200 {"detail": "Node deleted. {N} descendant(s) removed."}`

#### Acceptance Criteria

1. GIVEN a Part node with 2 Chapter children each with 1 Scene WHEN `DELETE /nodes/{part_node_id}` is called THEN the server returns HTTP 200 with `detail: "Node deleted. 4 descendant(s) removed."` and no descendant nodes remain.
2. GIVEN a leaf Beat node WHEN `DELETE /nodes/{beat_id}` is called THEN the server returns HTTP 200 with `detail: "Node deleted. 0 descendant(s) removed."`.
3. GIVEN a valid JWT WHEN `DELETE /nodes/{node_id}` is called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.
4. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `DELETE /nodes/{N.node_id}` THEN the server returns HTTP 404.

---

### Requirement 11: Valid Parent-Child Enforcement

**Feature group:** Node Hierarchy (`node-hierarchy/feature.md`)  
**User Story:** As an authenticated writer, I want the API to reject invalid parent-child combinations so that the hierarchy always forms a correct Part → Chapter → Scene → Beat structure.  
**Maps to:** `is_valid_parent_child(parent_type, child_type)` — called on every create and reparent operation.

#### Acceptance Criteria

1. GIVEN `is_valid_parent_child(None, "part")` is called THEN it returns `True`.
2. GIVEN `is_valid_parent_child("part", "chapter")` is called THEN it returns `True`.
3. GIVEN `is_valid_parent_child("beat", "beat")` is called THEN it returns `False` (Beat is a leaf).
4. GIVEN a valid JWT WHEN `POST /nodes` is called with `node_type: "scene"` and a Part `parent_id` THEN the server returns HTTP 422 with `detail: "A scene cannot be a child of a part"`.
5. GIVEN a valid JWT WHEN `PUT /nodes/{id}` is called with a `parent_id` that would violate hierarchy THEN the server returns HTTP 422 with a `detail` containing both type names.

---

### Requirement 12: Root-Only Constraint for Part Nodes

**Feature group:** Node Hierarchy (`node-hierarchy/feature.md`)  
**User Story:** As an authenticated writer, I want the API to ensure only Part nodes can be root-level (no parent).  
**Maps to:** No-`parent_id` branch in `create_normalised_node` (api.py).

#### Acceptance Criteria

1. GIVEN a valid JWT WHEN `POST /nodes` is called with `{"node_type": "part", ...}` and no `parent_id` THEN the server returns HTTP 201.
2. GIVEN a valid JWT WHEN `POST /nodes` is called with `{"node_type": "chapter", ...}` and no `parent_id` THEN the server returns HTTP 422 with exact `detail: "Only 'part' nodes may have no parent"`.
3. GIVEN a valid JWT WHEN `POST /nodes` is called with `{"node_type": "beat", ...}` and no `parent_id` THEN the server returns HTTP 422 with exact `detail: "Only 'part' nodes may have no parent"`.

---

### Requirement 13: Cycle Detection on Reparent

**Feature group:** Node Hierarchy (`node-hierarchy/feature.md`)  
**User Story:** As an authenticated writer, I want the API to prevent reparenting a node to one of its own descendants.  
**Maps to:** `NodeStorage.would_create_cycle(node_id, new_parent_id, account_id)` (database.py).

#### Acceptance Criteria

1. GIVEN a Part node `A` with Chapter child `B` WHEN `PUT /nodes/{A.node_id}` is called with `{"parent_id": B.node_id}` THEN the server returns HTTP 422 with `detail: "Reparenting would create a cycle"`.
2. GIVEN a Part → Chapter → Scene chain WHEN `PUT /nodes/{part_id}` is called with `{"parent_id": scene_id}` THEN the server returns HTTP 422 with `detail: "Reparenting would create a cycle"`.
3. GIVEN `would_create_cycle(node_id="A", new_parent_id="A", ...)` is called (self-loop) THEN it returns `True`.
4. GIVEN `would_create_cycle(node_id="A", new_parent_id="B", ...)` where B has no ancestors THEN it returns `False`.
5. GIVEN a reparent that violates both hierarchy and cycle WHEN `PUT /nodes/{id}` is called THEN the hierarchy error fires first (is_valid_parent_child is checked before would_create_cycle).

---

### Requirement 14: MongoDB JSON Schema Validator for node_type

**Feature group:** Node Hierarchy (`node-hierarchy/feature.md`)  
**User Story:** As a system administrator, I want the MongoDB schema validator to enforce `node_type` values even if application validation is bypassed.  
**Maps to:** `_NODE_VALIDATOR` dict (database.py), applied via `setup_collections`.

#### Acceptance Criteria

1. GIVEN `node_collection` has its validator active WHEN a document is inserted directly with `node_type: "volume"` THEN MongoDB rejects the insert.
2. GIVEN `node_collection` validator is active WHEN a document is inserted with `node_type: "part"` THEN the insert succeeds.
3. GIVEN `setup_collections` is called on an existing `node_collection` THEN the validator is updated via `collMod` without data loss.

---

### Requirement 15: Get Children

**Feature group:** Node Navigation (`node-navigation/feature.md`)  
**User Story:** As an authenticated reader, I want to retrieve the direct children of a node, so that I can navigate down the hierarchy one level.  
**Endpoint:** `GET /nodes/{node_id}/children` — scope: `tree:reader` — returns `200 list[NodeResponse]`  
**Status:** API endpoint not yet implemented (DB method complete).

#### Acceptance Criteria

1. GIVEN a valid JWT and a Part node `P` with 2 Chapter children WHEN `GET /nodes/{P.node_id}/children` is called THEN the server returns HTTP 200 with 2 `NodeResponse` objects ordered by `position` ascending.
2. GIVEN a valid JWT and a Beat node (leaf) WHEN `GET /nodes/{beat_id}/children` is called THEN the server returns HTTP 200 with an empty list `[]`.
3. GIVEN a valid JWT WHEN called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.
4. GIVEN no Authorization header WHEN `GET /nodes/{node_id}/children` is called THEN the server returns HTTP 401.
5. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `GET /nodes/{N.node_id}/children` THEN the server returns HTTP 404.

---

### Requirement 16: Get Parent

**Feature group:** Node Navigation (`node-navigation/feature.md`)  
**User Story:** As an authenticated reader, I want to retrieve the parent of a node, so that I can navigate up the hierarchy.  
**Endpoint:** `GET /nodes/{node_id}/parent` — scope: `tree:reader` — returns `200 NodeResponse | null`  
**Status:** API endpoint not yet implemented (DB method complete).

#### Acceptance Criteria

1. GIVEN a valid JWT and a Chapter node `C` with parent Part `P` WHEN `GET /nodes/{C.node_id}/parent` is called THEN the server returns HTTP 200 with the `NodeResponse` for `P`.
2. GIVEN a valid JWT and a Part node (root, `parent_id == null`) WHEN `GET /nodes/{part_id}/parent` is called THEN the server returns HTTP 200 with a JSON body of `null`.
3. GIVEN a valid JWT WHEN called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.
4. GIVEN no Authorization header WHEN `GET /nodes/{node_id}/parent` is called THEN the server returns HTTP 401.

---

### Requirement 17: Get Ancestors

**Feature group:** Node Navigation (`node-navigation/feature.md`)  
**User Story:** As an authenticated reader, I want to retrieve the full ancestor chain from root to parent, so that I can display breadcrumb navigation.  
**Endpoint:** `GET /nodes/{node_id}/ancestors` — scope: `tree:reader` — returns `200 AncestorsResponse`  
**Status:** API endpoint not yet implemented (DB method complete).

#### Acceptance Criteria

1. GIVEN a valid JWT and a Beat node `B` with ancestors Part `P` → Chapter `C` → Scene `S` WHEN `GET /nodes/{B.node_id}/ancestors` is called THEN the server returns HTTP 200 with `{"ancestors": [P, C, S]}` (root-first order).
2. GIVEN a valid JWT and a Part node (root) WHEN `GET /nodes/{part_id}/ancestors` is called THEN the server returns HTTP 200 with `{"ancestors": []}`.
3. GIVEN a valid JWT WHEN called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.

---

### Requirement 18: Get Siblings

**Feature group:** Node Navigation (`node-navigation/feature.md`)  
**User Story:** As an authenticated reader, I want to retrieve the siblings of a node, so that I can navigate the hierarchy laterally.  
**Endpoint:** `GET /nodes/{node_id}/siblings` — scope: `tree:reader` — returns `200 list[NodeResponse]`  
**Status:** API endpoint not yet implemented (DB method complete).

#### Acceptance Criteria

1. GIVEN 3 Chapter nodes under Part `P` at positions 0, 1, 2 WHEN `GET /nodes/{chapter1_id}/siblings` is called THEN the server returns HTTP 200 with the other 2 Chapters ordered by `position` (chapter1 itself excluded).
2. GIVEN a Chapter node that is the only child of its parent WHEN `GET /nodes/{C.node_id}/siblings` is called THEN the server returns HTTP 200 with an empty list `[]`.
3. GIVEN a valid JWT WHEN called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.

---

### Requirement 19: Get Root Nodes

**Feature group:** Node Navigation (`node-navigation/feature.md`)  
**User Story:** As an authenticated reader, I want to retrieve all root (Part) nodes for a Work, so that I can render the top level of the hierarchy.  
**Endpoint:** `GET /works/{work_id}/nodes/root` — scope: `tree:reader` — returns `200 list[NodeResponse]`  
**Status:** API endpoint not yet implemented (DB method complete).

#### Acceptance Criteria

1. GIVEN a valid JWT and a Work with 2 Part nodes WHEN `GET /works/{work_id}/nodes/root` is called THEN the server returns HTTP 200 with the 2 Part nodes ordered by `position` ascending.
2. GIVEN a valid JWT and a Work with no nodes WHEN `GET /works/{work_id}/nodes/root` is called THEN the server returns HTTP 200 with an empty list `[]`.
3. GIVEN a valid JWT WHEN called with a non-existent or cross-account `work_id` THEN the server returns HTTP 404 with `detail: "Work not found"`.
4. GIVEN User A has Work W and User B is authenticated WHEN User B calls `GET /works/{W.work_id}/nodes/root` THEN the server returns HTTP 404.

---

### Requirement 20: Get Leaf Nodes

**Feature group:** Node Navigation (`node-navigation/feature.md`)  
**User Story:** As an authenticated reader, I want to retrieve all leaf (Beat) nodes for a Work, so that I can find story endpoints.  
**Endpoint:** `GET /works/{work_id}/nodes/leaves` — scope: `tree:reader` — returns `200 list[NodeResponse]`  
**Status:** API endpoint not yet implemented (DB method complete).

#### Acceptance Criteria

1. GIVEN a valid JWT and a Work with 3 Beat nodes WHEN `GET /works/{work_id}/nodes/leaves` is called THEN the server returns HTTP 200 with the 3 Beat nodes ordered by `position` ascending.
2. GIVEN a valid JWT and a Work with no Beat nodes WHEN `GET /works/{work_id}/nodes/leaves` is called THEN the server returns HTTP 200 with an empty list `[]`.
3. GIVEN a valid JWT WHEN called with a non-existent or cross-account `work_id` THEN the server returns HTTP 404 with `detail: "Work not found"`.

---

### Requirement 21: Get Work Statistics

**Feature group:** Node Navigation (`node-navigation/feature.md`)  
**User Story:** As an authenticated reader, I want to see aggregate statistics for a Work (node counts by type and max depth).  
**Endpoint:** `GET /works/{work_id}/stats` — scope: `tree:reader` — returns `200 WorkStatsResponse`  
**Status:** API endpoint not yet implemented (DB method complete).

#### Acceptance Criteria

1. GIVEN a Work with 1 Part, 2 Chapters, 2 Scenes, 2 Beats WHEN `GET /works/{work_id}/stats` is called THEN the server returns HTTP 200 with `{"work_id": "...", "total_nodes": 7, "by_type": {"part": 1, "chapter": 2, "scene": 2, "beat": 2}, "max_depth": 3}`.
2. GIVEN a Work with no nodes WHEN `GET /works/{work_id}/stats` is called THEN the server returns HTTP 200 with `total_nodes: 0` and `max_depth: 0`.
3. GIVEN a Work with only a single Part node WHEN `GET /works/{work_id}/stats` is called THEN `max_depth` is 0.
4. GIVEN a valid JWT WHEN called with a non-existent or cross-account `work_id` THEN the server returns HTTP 404 with `detail: "Work not found"`.

---

### Requirement 22: Reorder Node Among Siblings

**Feature group:** Node Reorder (`node-reorder/feature.md`)  
**User Story:** As an authenticated writer, I want to move a node to a specific position among its siblings, so that I can arrange chapters or scenes in the desired narrative order.  
**Endpoint:** `PUT /nodes/{node_id}/reorder` — scope: `tree:writer` — returns `200 NodeResponse`  
**Status:** API endpoint not yet implemented (DB method `reorder_siblings` complete).

#### Acceptance Criteria

1. GIVEN 3 sibling Chapter nodes at positions 0, 1, 2 WHEN `PUT /nodes/{chapter_2_id}/reorder` is called with `{"position": 0}` THEN the server returns HTTP 200 with a `NodeResponse` where `position` is 0 and the other two are renumbered to 1 and 2.
2. GIVEN 3 sibling nodes WHEN `PUT /nodes/{node_id}/reorder` is called with `{"position": 100}` THEN the server returns HTTP 200 with `position: 2` (clamped to last valid index).
3. GIVEN a node that is the only child WHEN `PUT /nodes/{node_id}/reorder` is called with `{"position": 5}` THEN the server returns HTTP 200 with `position: 0`.
4. GIVEN a valid JWT WHEN `PUT /nodes/{node_id}/reorder` is called with `{"position": -1}` THEN the server returns HTTP 422.
5. GIVEN a valid JWT WHEN called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.
6. GIVEN a JWT with `tree:reader` scope only WHEN `PUT /nodes/{node_id}/reorder` is called THEN the server returns HTTP 403.

---

### Requirement 23: Sibling Renumbering After Reorder

**Feature group:** Node Reorder (`node-reorder/feature.md`)  
**User Story:** As a system, I want all siblings to be renumbered after every reorder, so that `position` values are always a contiguous zero-based sequence.  
**Maps to:** Renumbering loop in `NodeStorage.reorder_siblings` (database.py).

#### Acceptance Criteria

1. GIVEN 4 sibling nodes at positions 0, 1, 2, 3 WHEN `reorder_siblings` moves position 3 to position 0 THEN all 4 nodes are renumbered with no gaps.
2. GIVEN 3 sibling nodes WHEN ANY reorder is performed THEN querying `node_collection` for those siblings and sorting by `position` yields consecutive integers starting from 0.

---

### Requirement 24: Shallow and Deep Node Duplication

**Feature group:** Node Duplicate (`node-duplicate/feature.md`)  
**User Story:** As an authenticated writer, I want to create a copy of a node (with or without its children) as the next sibling.  
**Endpoint:** `POST /nodes/{node_id}/duplicate[?deep=true]` — scope: `tree:writer` — returns `201 NodeResponse`  
**Status:** API endpoint not yet implemented (DB methods `duplicate_shallow` and `duplicate_deep` complete).

#### Acceptance Criteria

1. GIVEN a Chapter node `C` at position 1 with siblings at positions 0 and 2 WHEN `POST /nodes/{C.node_id}/duplicate` is called THEN the server returns HTTP 201 with `tag: "{C.tag} (copy)"`, `position: 2`, and the former position-2 sibling is now at position 3.
2. GIVEN a Chapter node with no children WHEN `POST /nodes/{C.node_id}/duplicate` (shallow) is called THEN the result has no children (calling `GET /nodes/{new_id}/children` returns `[]`).
3. GIVEN a Part node with 2 Chapter children each with 1 Scene WHEN `POST /nodes/{P.node_id}/duplicate?deep=true` is called THEN the server returns HTTP 201 for the Part copy with 2 Chapter children each with 1 Scene child (all with new `node_id` values).
4. GIVEN a valid JWT WHEN `POST /nodes/{beat_id}/duplicate` is called on a Beat node THEN the server returns HTTP 400 with `detail: "Beat nodes cannot be duplicated"`.
5. GIVEN a valid JWT WHEN `POST /nodes/{beat_id}/duplicate?deep=true` is called on a Beat node THEN the server returns HTTP 400 with `detail: "Beat nodes cannot be duplicated"`.
6. GIVEN a valid JWT WHEN called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.
7. GIVEN a JWT with `tree:reader` scope only WHEN `POST /nodes/{node_id}/duplicate` is called THEN the server returns HTTP 403.

---

### Requirement 25: Deep Duplicate Preserves Subtree

**Feature group:** Node Duplicate (`node-duplicate/feature.md`)  
**User Story:** As an authenticated writer, I want a deep copy to recursively copy all descendants so that I can branch an entire story section.  
**Maps to:** `NodeStorage.duplicate_deep` (database.py) — implementation complete; this requirement covers verification.

#### Acceptance Criteria

1. GIVEN a Part with 2 Chapter children each with 2 Scene children WHEN `duplicate_deep` is called THEN the result has 2 Chapter children (new UUIDs) each with 2 Scene children (new UUIDs) — 6 new nodes total.
2. GIVEN a Part copy from deep duplicate THEN the root copy's `tag` ends with `" (copy)"` but child copies have unmodified original tags.
3. GIVEN any deep duplicate THEN all newly created `node_id` values are UUID4 strings distinct from the originals.

---

### Requirement 26: Create work_collection with Validator and Indexes

**Feature group:** MongoDB Setup (`mongodb-setup/feature.md`)  
**User Story:** As a system administrator, I want `work_collection` to be created with schema validators and indexes at startup, so that Work documents are always valid and queries are fast.  
**Maps to:** `setup_collections` (database.py), lifespan startup (api.py).

#### Acceptance Criteria

1. GIVEN the FastAPI server starts WHEN `setup_collections` completes THEN `work_collection` exists in the `fabulator` database.
2. GIVEN `work_collection` exists WHEN a document is inserted without the `title` field THEN MongoDB rejects the insert.
3. GIVEN a valid Work document is inserted WHEN a second document with the same `work_id` is inserted THEN MongoDB rejects it with a duplicate key error.
4. GIVEN `setup_collections` is called twice THEN no error is raised.

---

### Requirement 27: Create node_collection with Validator and Indexes

**Feature group:** MongoDB Setup (`mongodb-setup/feature.md`)  
**User Story:** As a system administrator, I want `node_collection` to have schema enforcement and optimised indexes, so that node documents are always valid and relationship queries are efficient.  
**Maps to:** `setup_collections` (database.py).

#### Acceptance Criteria

1. GIVEN the FastAPI server starts WHEN `setup_collections` completes THEN `node_collection` exists in the `fabulator` database.
2. GIVEN `node_collection` exists WHEN a document is inserted with `node_type: "volume"` THEN MongoDB rejects the insert.
3. GIVEN `node_collection` exists WHEN a document is inserted with `position: -1` THEN MongoDB rejects the insert.
4. GIVEN a valid document is inserted WHEN a second document with the same `node_id` is inserted THEN MongoDB rejects it with a duplicate key error.
5. GIVEN 1000 node documents exist WHEN `list_nodes(work_id, account_id)` is called THEN the query uses the `{account_id, work_id}` index (verified via `explain()`).

---

### Requirement 28: Idempotent Setup and Startup Integration

**Feature group:** MongoDB Setup (`mongodb-setup/feature.md`)  
**User Story:** As an operator, I want `setup_collections` to be safe to call on every server restart, so that I can redeploy without manual database migration.  
**Maps to:** `setup_collections` conditional logic (database.py) and lifespan startup (api.py).

#### Acceptance Criteria

1. GIVEN a fresh database with no collections WHEN `setup_collections` is called THEN both collections are created with their validators and all 7 indexes.
2. GIVEN both collections already exist with data WHEN `setup_collections` is called again THEN no existing documents are deleted, no error is raised, and validators are refreshed via `collMod`.
3. GIVEN `setup_collections` raises `OperationFailure` THEN it propagates through the lifespan startup, causing the FastAPI app to fail to start.

---

## Non-Functional Requirements

### NR 1: Authentication Enforcement (Work Endpoints)

**Feature group:** Work CRUD  
**User Story:** As a system administrator, I want every Work endpoint to enforce JWT authentication and scope checks.

#### Acceptance Criteria

1. GIVEN no `Authorization` header WHEN any Work endpoint is called THEN the server returns HTTP 401.
2. GIVEN a valid JWT but missing the required scope WHEN a write Work endpoint is called THEN the server returns HTTP 403 with `detail: "Insufficient permissions to complete action"`.
3. GIVEN a blacklisted token WHEN any Work endpoint is called THEN the server returns HTTP 401.

---

### NR 2: Account Isolation (Work Endpoints)

**Feature group:** Work CRUD  
**User Story:** As a user, I want my Works to be invisible to other users.

#### Acceptance Criteria

1. GIVEN User A has a Work and User B is authenticated WHEN User B calls `GET /works/{A's work_id}` THEN the server returns HTTP 404 (not 403).
2. GIVEN User A and User B each have Works WHEN User B calls `GET /works` THEN the response contains only User B's Works.

---

### NR 3: Input Validation (Work Endpoints)

**Feature group:** Work CRUD  
**User Story:** As an API consumer, I want clear validation errors for malformed Work requests.

#### Acceptance Criteria

1. GIVEN `POST /works` with `title` longer than 200 characters THEN the server returns HTTP 422.
2. GIVEN `POST /works` with a `tags` item that is an empty string THEN the server returns HTTP 422.
3. GIVEN `GET /works/{work_id}` where `work_id` is not a valid UUID4 string THEN the server returns HTTP 422.

---

### NR 4: Error Message Format (Work Endpoints)

**Feature group:** Work CRUD  
**User Story:** As an API consumer, I want sanitised error messages that never expose internal server details.

#### Acceptance Criteria

1. GIVEN any Work endpoint error THEN the response body is exactly `{"detail": "<human-readable message>"}` with no stack trace, no `account_id`, no MongoDB internal IDs.
2. GIVEN a `ConnectionFailure` WHEN any Work endpoint is called THEN the server returns HTTP 503 with `detail: "Database error"`.

---

### NR 5: Authentication Enforcement (Node Endpoints)

**Feature group:** Node CRUD  
**User Story:** As a system administrator, I want every Node endpoint to enforce JWT authentication and scope.

#### Acceptance Criteria

1. GIVEN no `Authorization` header WHEN any Node endpoint is called THEN the server returns HTTP 401.
2. GIVEN a valid JWT with only `tree:reader` scope WHEN a write Node endpoint is called THEN the server returns HTTP 403.
3. GIVEN a blacklisted token WHEN any Node endpoint is called THEN the server returns HTTP 401.

---

### NR 6: Account Isolation (Node Endpoints)

**Feature group:** Node CRUD  
**User Story:** As a user, I want my nodes to be invisible to other users.

#### Acceptance Criteria

1. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `GET /nodes/{N.node_id}` THEN the server returns HTTP 404 (not 403).
2. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `PUT /nodes/{N.node_id}` THEN the server returns HTTP 404.

---

### NR 7: Input Validation (Node Endpoints)

**Feature group:** Node CRUD  
**User Story:** As an API consumer, I want validation errors for malformed node requests.

#### Acceptance Criteria

1. GIVEN `POST /nodes` with a `tag` field of 201 characters THEN the server returns HTTP 422.
2. GIVEN `POST /nodes` with `node_type: "volume"` (not in enum) THEN the server returns HTTP 422.
3. GIVEN `POST /nodes` with `tags` containing 51 items THEN the server returns HTTP 422.
4. GIVEN `GET /nodes/{node_id}` where `node_id` contains special characters THEN the server returns HTTP 422.

---

### NR 8: Error Message Format (Node Endpoints)

**Feature group:** Node CRUD  
**User Story:** As an API consumer, I want sanitised error messages from Node endpoints.

#### Acceptance Criteria

1. GIVEN any Node endpoint error THEN the response body is exactly `{"detail": "<message>"}` with no stack trace, no `account_id`, no MongoDB `_id`.
2. GIVEN a `ConnectionFailure` WHEN any Node endpoint is called THEN the server returns HTTP 503 with `detail: "Database error"`.

---

### NR 9: Hierarchy Errors Return HTTP 422

**Feature group:** Node Hierarchy  
**User Story:** As an API consumer, I want hierarchy violations to return 422 so that my client can distinguish them from other errors.

#### Acceptance Criteria

1. GIVEN any invalid parent-child combination WHEN `POST /nodes` is called THEN the status code is exactly 422.
2. GIVEN a cycle detection result WHEN `PUT /nodes/{id}` is called THEN the status code is exactly 422.

---

### NR 10: Hierarchy Error Messages are Sanitised

**Feature group:** Node Hierarchy  
**User Story:** As a security reviewer, I want hierarchy error messages to include only node type names, not internal IDs.

#### Acceptance Criteria

1. GIVEN `detail: "A scene cannot be a child of a part"` THEN the detail contains only `node_type` values from the request — no `node_id`, no `account_id`.
2. GIVEN `detail: "Reparenting would create a cycle"` THEN the detail is a static string with no dynamic values.

---

### NR 11: Hierarchy Check Precedes Cycle Check

**Feature group:** Node Hierarchy  
**User Story:** As an API consumer, I want consistent ordering — hierarchy checked before cycle — so that error messages are predictable.

#### Acceptance Criteria

1. GIVEN a reparent request that violates both hierarchy and would create a cycle WHEN `PUT /nodes/{id}` is called THEN the server returns the hierarchy error (not the cycle error). `is_valid_parent_child` is checked before `would_create_cycle`.

---

### NR 12: Authentication Enforcement (Navigation Endpoints)

**Feature group:** Node Navigation  
**User Story:** As a system administrator, I want all navigation endpoints to require `tree:reader` scope.

#### Acceptance Criteria

1. GIVEN no `Authorization` header WHEN any navigation endpoint is called THEN the server returns HTTP 401.
2. GIVEN a token without `tree:reader` scope WHEN any navigation endpoint is called THEN the server returns HTTP 403.

---

### NR 13: Account Isolation (Navigation Endpoints)

**Feature group:** Node Navigation  
**User Story:** As a user, I want cross-account resource access to return 404 so that the existence of other users' data is not revealed.

#### Acceptance Criteria

1. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `GET /nodes/{N.node_id}/children` THEN the server returns HTTP 404.
2. GIVEN User A has Work W and User B is authenticated WHEN User B calls `GET /works/{W.work_id}/stats` THEN the server returns HTTP 404.

---

### NR 14: Path Parameter Validation (Navigation Endpoints)

**Feature group:** Node Navigation  
**User Story:** As an API consumer, I want invalid path parameters to return 422 immediately.

#### Acceptance Criteria

1. GIVEN `GET /nodes/not-a-uuid/children` is called THEN the server returns HTTP 422.
2. GIVEN `GET /works/not-a-uuid/nodes/root` is called THEN the server returns HTTP 422.

---

### NR 15: Error Message Format (Navigation Endpoints)

**Feature group:** Node Navigation  
**User Story:** As an API consumer, I want navigation errors to use sanitised messages with no internal state.

#### Acceptance Criteria

1. GIVEN a 404 from a node-scoped navigation endpoint THEN `detail` is exactly `"Node not found"`.
2. GIVEN a 404 from a work-scoped navigation endpoint THEN `detail` is exactly `"Work not found"`.
3. GIVEN a database failure WHEN any navigation endpoint is called THEN `detail` is exactly `"Database error"` with HTTP 503.

---

### NR 16: Authentication Enforcement (Reorder Endpoint)

**Feature group:** Node Reorder  
**User Story:** As a system administrator, I want the reorder endpoint to enforce `tree:writer` scope.

#### Acceptance Criteria

1. GIVEN no `Authorization` header WHEN `PUT /nodes/{node_id}/reorder` is called THEN the server returns HTTP 401.
2. GIVEN a token with only `tree:reader` scope WHEN `PUT /nodes/{node_id}/reorder` is called THEN the server returns HTTP 403.

---

### NR 17: Account Isolation (Reorder Endpoint)

**Feature group:** Node Reorder  
**User Story:** As a user, I want reorder to be account-isolated so that I cannot reorder another user's nodes.

#### Acceptance Criteria

1. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `PUT /nodes/{N.node_id}/reorder` THEN the server returns HTTP 404 (not 403).

---

### NR 18: Input Validation (Reorder Endpoint)

**Feature group:** Node Reorder  
**User Story:** As an API consumer, I want position validation to reject negative integers immediately.

#### Acceptance Criteria

1. GIVEN `PUT /nodes/{node_id}/reorder` is called with `{"position": -1}` THEN the server returns HTTP 422.
2. GIVEN `PUT /nodes/{node_id}/reorder` is called with `{"position": "abc"}` THEN the server returns HTTP 422.
3. GIVEN a `node_id` path parameter that is not a valid UUID4 THEN the server returns HTTP 422.

---

### NR 19: Error Message Format (Reorder Endpoint)

**Feature group:** Node Reorder  
**User Story:** As an API consumer, I want reorder errors to use sanitised messages.

#### Acceptance Criteria

1. GIVEN a 404 error from the reorder endpoint THEN `detail` is exactly `"Node not found"`.
2. GIVEN a database failure WHEN `PUT /nodes/{node_id}/reorder` is called THEN HTTP 503 with `detail: "Database error"`.

---

### NR 20: Authentication Enforcement (Duplicate Endpoint)

**Feature group:** Node Duplicate  
**User Story:** As a system administrator, I want the duplicate endpoint to require `tree:writer` scope.

#### Acceptance Criteria

1. GIVEN no `Authorization` header WHEN `POST /nodes/{node_id}/duplicate` is called THEN the server returns HTTP 401.
2. GIVEN a token with only `tree:reader` scope WHEN `POST /nodes/{node_id}/duplicate` is called THEN the server returns HTTP 403.

---

### NR 21: Account Isolation (Duplicate Endpoint)

**Feature group:** Node Duplicate  
**User Story:** As a user, I want duplication to be account-isolated.

#### Acceptance Criteria

1. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `POST /nodes/{N.node_id}/duplicate` THEN the server returns HTTP 404 (not 403).
2. GIVEN a deep duplicate, all copied nodes MUST have `account_id` equal to the authenticated user's `account_id`.

---

### NR 22: Beat Guard Enforcement (Duplicate Endpoint)

**Feature group:** Node Duplicate  
**User Story:** As a system, I want Beat nodes to be rejected before any write occurs.

#### Acceptance Criteria

1. GIVEN a Beat node `B` WHEN `POST /nodes/{B.node_id}/duplicate` is called THEN the server returns HTTP 400 with `detail: "Beat nodes cannot be duplicated"` and NO document is written to `node_collection`.
2. GIVEN the API returns HTTP 400 for a Beat THEN `duplicate_shallow` or `duplicate_deep` MUST NOT have been called.

---

### NR 23: Error Message Format (Duplicate Endpoint)

**Feature group:** Node Duplicate  
**User Story:** As an API consumer, I want duplicate errors to use sanitised messages.

#### Acceptance Criteria

1. GIVEN a 404 from the duplicate endpoint THEN `detail` is exactly `"Node not found"`.
2. GIVEN a 400 from the duplicate endpoint THEN `detail` is exactly `"Beat nodes cannot be duplicated"`.

---

### NR 24: Setup Runs at Startup, Not Per-Request

**Feature group:** MongoDB Setup  
**User Story:** As a system administrator, I want collection setup to occur once at server startup.

#### Acceptance Criteria

1. GIVEN the FastAPI lifespan context manager WHEN the server starts THEN `setup_collections` is called exactly once before the first request is served.
2. GIVEN a request comes in after startup THEN `setup_collections` is NOT called as part of request handling.

---

### NR 25: Error Logging and Propagation (Setup)

**Feature group:** MongoDB Setup  
**User Story:** As an operator, I want setup failures to be logged with full context and then re-raised.

#### Acceptance Criteria

1. GIVEN `db.create_collection` raises `OperationFailure` WHEN `setup_collections` handles it THEN `logger.error(f"Failed to create collection {name}", exc_info=True)` is called and the error is re-raised.
2. GIVEN `setup_collections` raises any exception THEN the FastAPI lifespan startup fails and the server does not serve requests.

---

## Correctness Properties

### CP 1: account_id Never Exposed (Works)

- **Description:** `account_id` MUST NOT appear in any Work endpoint response body. The `WorkResponse` Pydantic model excludes it by field selection. (CONSTITUTION I.4)
- **Testable:** Assert `"account_id"` key is absent from every Work endpoint response body.

---

### CP 2: work_id is Always UUID4

- **Description:** Every Work document in `work_collection` MUST have a `work_id` value matching the UUID4 pattern, generated by `str(uuid.uuid4())`. (CONSTITUTION IV.4)
- **Testable:** After `POST /works`, assert `re.match(UUID4_PATTERN, response["work_id"])` is truthy.

---

### CP 3: Timestamps are Always UTC

- **Description:** `created_at` and `updated_at` MUST be set using `datetime.now(timezone.utc)`. `datetime.utcnow()` and `pytz` are prohibited. (CONSTITUTION IV.6)
- **Testable:** After any Work write, assert the stored timestamp is timezone-aware UTC: `assert work["created_at"].tzinfo is not None`.

---

### CP 4: Author Cascade is Atomic and Complete

- **Description:** When `PUT /works/{work_id}` changes the `author` field, `cascade_author_to_nodes` MUST be called. All nodes with `{work_id, account_id}` MUST have `author` updated before the response is returned. (CONSTITUTION I.7)
- **Testable:** Create a Work with author "A", add 3 nodes, `PUT /works/{id}` with `{"author": "B"}`, query `node_collection` and assert all 3 nodes have `author: "B"`.

---

### CP 5: Work Delete Removes All Nodes

- **Description:** After `DELETE /works/{work_id}`, no documents in `node_collection` with that `work_id` MUST remain. (CONSTITUTION I.1)
- **Testable:** Create Work, add nodes, delete Work, query `node_collection` with `{"work_id": deleted_id}` and assert empty result.

---

### CP 6: account_id Never Exposed (Nodes)

- **Description:** `account_id` MUST NOT appear in any NodeResponse. (CONSTITUTION I.4)
- **Testable:** Assert `"account_id"` key is absent from every node endpoint response body.

---

### CP 7: node_id is Always UUID4

- **Description:** Every node document MUST have a `node_id` matching the UUID4 pattern. (CONSTITUTION IV.4)
- **Testable:** After `POST /nodes`, assert `re.match(UUID4_PATTERN, response["node_id"])` is truthy.

---

### CP 8: position is Non-Negative

- **Description:** `position` MUST be a non-negative integer (>= 0). The first sibling gets `position: 0`. (CONSTITUTION IV.5)
- **Testable:** Query all nodes for a work. Assert all `position` values are >= 0 and first inserted node has `position: 0`.

---

### CP 9: author Copied from Work at Node Creation

- **Description:** When a node is created, `author` MUST be set to `work_doc.get("author")`, not any user-supplied value. (CONSTITUTION I.7)
- **Testable:** Create Work with `author: "Alice"`. Create a node. Assert the node's `author` is `"Alice"`.

---

### CP 10: Cascade Delete Removes All Descendants

- **Description:** After `DELETE /nodes/{node_id}`, no descendant nodes (at any depth) may remain in `node_collection`. (CONSTITUTION I.2)
- **Testable:** Create a 4-level hierarchy, delete the Part, query `node_collection` for the Part's subtree — assert 0 documents remain.

---

### CP 11: node_type Immutable After Creation

- **Description:** The `node_type` of a node MUST NOT be changed via `PUT /nodes/{node_id}`. `UpdateNodeRequest` does not include `node_type`. (CONSTITUTION I.5, IV.3)
- **Testable:** Call `PUT /nodes/{id}` with extra field `{"node_type": "scene"}` — assert `node_type` is unchanged after the call.

---

### CP 12: Strict Hierarchy Invariant

- **Description:** At every moment, every non-Part node MUST have a `parent_id` pointing to a node of the correct parent type. No skipped levels are permitted. (CONSTITUTION I.5)
- **Testable:** For each node in `node_collection`, fetch its parent and assert `_VALID_CHILD[parent_type] == node_type`.

---

### CP 13: Part is the Only Valid Root

- **Description:** A node with `parent_id == null` MUST have `node_type == "part"`. (CONSTITUTION I.5)
- **Testable:** Query `node_collection` for `{parent_id: null}`. Assert every result has `node_type: "part"`.

---

### CP 14: No Cycles in parent_id Chain

- **Description:** Following `parent_id` from any node MUST eventually reach a node with `parent_id == null`, without revisiting any node. (CONSTITUTION I.5)
- **Testable:** Walk the `parent_id` chain using a `visited` set. Assert the chain terminates without repeating any node.

---

### CP 15: Beat Has No Children

- **Description:** No node may have `parent_id` pointing to a Beat node via the API. (CONSTITUTION I.5)
- **Testable:** Attempt `POST /nodes` with `parent_id = beat_node_id` and any `node_type`. Assert HTTP 422 is returned. Query `node_collection` for `{parent_id: beat_node_id}` and assert empty result.

---

### CP 16: Children Ordered by Position Ascending

- **Description:** `GET /nodes/{id}/children` MUST return children in `position` ascending order (0 first), enforced by `sort=[("position", 1)]` in `NodeStorage.get_children`. (CONSTITUTION IV.5)
- **Testable:** Create 3 children under a node. Assert response list `position` values are `[0, 1, 2]`.

---

### CP 17: Ancestors Ordered Root-First

- **Description:** `GET /nodes/{id}/ancestors` MUST return the root Part at index 0 and the immediate parent at the last index, enforced by `ancestors.reverse()` in `NodeStorage.get_ancestors`.
- **Testable:** For a Beat node at depth 3, assert ancestors list has 3 items, first is a Part, last is a Scene.

---

### CP 18: Self Excluded from Siblings

- **Description:** `GET /nodes/{id}/siblings` MUST NOT include the queried node itself, enforced by `"node_id": {"$ne": node_id}` in `NodeStorage.get_siblings`. (CONSTITUTION IV.5)
- **Testable:** Assert the queried `node_id` does not appear in the siblings response array.

---

### CP 19: Root Nodes are Always Parts

- **Description:** `GET /works/{id}/nodes/root` MUST only return nodes with `node_type == "part"` and `parent_id == null`. (CONSTITUTION I.5)
- **Testable:** Assert every item in the roots response has `node_type: "part"` and `parent_id: null`.

---

### CP 20: Leaf Nodes are Always Beats

- **Description:** `GET /works/{id}/nodes/leaves` MUST only return nodes with `node_type == "beat"`. (CONSTITUTION I.5)
- **Testable:** Assert every item in the leaves response has `node_type: "beat"`.

---

### CP 21: Contiguous Zero-Based Positions After Reorder

- **Description:** After every call to `reorder_siblings`, the sibling group MUST have positions `0, 1, 2, ..., N-1` with no gaps and no duplicate values. (CONSTITUTION IV.5)
- **Testable:** After any reorder call, query `node_collection` for `{account_id, parent_id, work_id}`, sort by position, assert positions form a consecutive sequence starting at 0.

---

### CP 22: Position Clamped to Valid Range

- **Description:** The actual `position` assigned to the moved node MUST be in `[0, len(siblings) - 1]`. Requesting a position beyond this range MUST result in the node being placed last. (CONSTITUTION IV.5)
- **Testable:** Request `position: 999` for a 3-sibling group. Assert resulting `position` is 2. Request `position: 5` for a single-node group. Assert resulting `position` is 0.

---

### CP 23: Node Stays in Same Work After Reorder

- **Description:** Reordering MUST NOT change a node's `work_id`, `parent_id`, `node_type`, `tag`, or content fields. Only `position` and `updated_at` are changed. (CONSTITUTION I.2)
- **Testable:** Record all fields before reorder. Assert all fields except `position` and `updated_at` are unchanged after reorder.

---

### CP 24: All Copies Have Fresh UUID4 node_ids

- **Description:** Every document inserted by `duplicate_shallow` or `duplicate_deep` MUST have `node_id = str(uuid.uuid4())`. The original `node_id` MUST NOT appear in any copy. (CONSTITUTION IV.4)
- **Testable:** Collect all `node_id` values returned by a deep duplicate. Assert none match the original source's `node_id` or any original child's `node_id`.

---

### CP 25: Copy Inserted at original.position + 1

- **Description:** The shallow/deep root copy MUST be placed at `original.position + 1`. Siblings previously at positions `> original.position` MUST be incremented by 1. (CONSTITUTION IV.5)
- **Testable:** Record sibling positions before duplicate. Assert copy is at `original.position + 1`. Assert all former successors are incremented by exactly 1.

---

### CP 26: Root Copy Tag Ends with " (copy)"

- **Description:** The root copy's `tag` MUST be `f"{source.tag} (copy)"`. Child copies in a deep duplicate MUST NOT have `" (copy)"` appended.
- **Testable:** After shallow duplicate, assert `result["tag"] == f"{source_tag} (copy)"`. After deep duplicate, assert child copies have `tag == original_child_tag`.

---

### CP 27: Beat Nodes Cannot Be Duplicated

- **Description:** The API MUST return HTTP 400 for Beat nodes before calling any DB method. No document MUST be inserted when the source is a Beat. (CONSTITUTION I.5)
- **Testable:** Count documents in `node_collection` before and after a Beat duplicate attempt. Assert the count is unchanged and HTTP 400 was returned.

---

### CP 28: work_id is Globally Unique in work_collection

- **Description:** The unique index on `{work_id: 1}` MUST prevent two Work documents from sharing the same `work_id`. (CONSTITUTION IV.4)
- **Testable:** Attempt to insert two documents with the same `work_id` directly via Motor. Assert the second insert raises `DuplicateKeyError`.

---

### CP 29: node_id is Globally Unique in node_collection

- **Description:** The unique index on `{node_id: 1}` MUST prevent two node documents from sharing the same `node_id`. (CONSTITUTION IV.4)
- **Testable:** Attempt to insert two documents with the same `node_id` directly via Motor. Assert the second insert raises `DuplicateKeyError`.

---

### CP 30: node_type Enum Enforced at DB Level

- **Description:** The `_NODE_VALIDATOR` enforces `node_type` as one of `["part", "chapter", "scene", "beat"]`. No other value may be stored. (CONSTITUTION IV.3)
- **Testable:** Directly insert a document with `node_type: "act"` into `node_collection`. Assert the insert fails with a MongoDB write error.

---

### CP 31: Position Must Be Non-Negative at DB Level

- **Description:** The `_NODE_VALIDATOR` enforces `position >= 0`. (CONSTITUTION IV.5)
- **Testable:** Directly insert a document with `position: -1` into `node_collection`. Assert the insert fails with a MongoDB write error.

---

### CP 32: Required Fields Enforced at DB Level

- **Description:** Documents missing any required field (`node_id`, `work_id`, `account_id`, `tag`, `node_type`, `position`, `tags` for nodes; `work_id`, `account_id`, `title`, `tags` for works) MUST be rejected by the validator. (CONSTITUTION IV.1, IV.2)
- **Testable:** For each required field, insert an otherwise valid document without that field. Assert each attempt raises a MongoDB `WriteError`.
