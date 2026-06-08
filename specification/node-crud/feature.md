# Feature Specification: Node CRUD

**Implementation status:** COMPLETE — all 5 endpoints and all core `NodeStorage` methods are committed on branch `refactor/normalised-node-model`. This document is authoritative for verification, test authoring, and corrective changes.

**Files in scope:**
- `server/app/database.py` — `NodeStorage` class, methods `create_node`, `get_node`, `list_nodes`, `update_node`, `delete_node_cascade` (lines 844–999)
- `server/app/api.py` — 5 Node route handlers (lines 358–609)
- `server/app/models.py` — `CreateNodeRequest`, `UpdateNodeRequest`, `NodeResponse`, `NodeType`

---

## Introduction

Node CRUD manages individual story-structure documents (Parts, Chapters, Scenes, Beats) stored in `node_collection`. Each node belongs to exactly one Work (`work_id`) and one account (`account_id`). Nodes form a hierarchy enforced at both application and MongoDB schema level. Position ordering among siblings is managed automatically: new nodes are appended at the end; deletion triggers no renumbering (gaps are allowed after delete; reordering is a separate operation). Author is copied from the parent Work at creation time. Hierarchy validation and cycle detection are applied on create and update. (CONSTITUTION I.1, I.5, I.6, I.7, Part X Tier 1)

---

## Glossary

| Term | Definition |
|------|-----------|
| **Node** | A MongoDB document in `node_collection`. Represents one structural unit (Part/Chapter/Scene/Beat). |
| **node_id** | UUID4 string. Primary key for a Node. Never MongoDB's `_id`. |
| **work_id** | UUID4 foreign key to the owning Work in `work_collection`. Required on every node. |
| **account_id** | bcrypt hash of username. Partition key. Never returned in API responses. |
| **parent_id** | UUID4 of the node's parent node. `null` for Part (root) nodes. |
| **position** | Non-negative integer. Zero-based ordering among siblings with the same `parent_id`. |
| **node_type** | Enum: `"part"` \| `"chapter"` \| `"scene"` \| `"beat"`. Strict hierarchy enforced. |
| **tag** | The display name of a node. Required, 1–200 chars, whitespace stripped. |
| **NodeType** | Python `Enum` in models.py: `NodeType.part`, `.chapter`, `.scene`, `.beat`. Passed as `.value` (string) to DB methods. |
| **NodeResponse** | Response model. Contains: `node_id`, `work_id`, `author`, `node_type`, `parent_id`, `position`, `tag`, `description`, `text`, `previous`, `next`, `tags`, `created_at`, `updated_at`. Does NOT contain `account_id`. |
| **is_valid_parent_child** | Module-level function in database.py that enforces hierarchy. `is_valid_parent_child(None, "part")` → True. `is_valid_parent_child("part", "chapter")` → True. All other combinations → False. |
| **would_create_cycle** | `NodeStorage` async method. Returns True if setting `new_parent_id` as parent of `node_id` would form a cycle. |
| **cascade delete** | BFS traversal from node, collecting all descendant IDs, then single `delete_many`. Returns `(True, descendants_deleted)` where count excludes the node itself. |
| **author** | Copied from the Work document at node creation time. Updated by author cascade (see Work CRUD spec). |

---

## Functional Requirements

### Requirement 1: Create Node

**User Story:** As an authenticated writer, I want to create a node within a Work, so that I can build my narrative hierarchy.

**Maps to:** `NodeStorage.create_node(account_id, work_doc, data) -> dict` (database.py:855) and `POST /nodes` handler `create_normalised_node` (api.py:371). (CONSTITUTION I.5, I.6, I.7, Part X Tier 1)

**Exact endpoint:**
```
Method:         POST
Path:           /nodes
Request body:   application/json — CreateNodeRequest
Response body:  NodeResponse
Status on success: 201
Required scope: tree:writer
OpenAPI tags:   ["Nodes"]
```

**Request shape (`CreateNodeRequest`):**
```json
{
  "work_id":     "UUID4 string, required",
  "node_type":   "\"part\" | \"chapter\" | \"scene\" | \"beat\", required",
  "parent_id":   "UUID4 string, optional (null = root Part)",
  "tag":         "string, required, 1–200 chars, whitespace stripped",
  "description": "string, optional, max 2000 chars",
  "text":        "string, optional, max 50000 chars",
  "previous":    "string, optional, max 200 chars",
  "next":        "string, optional, max 200 chars",
  "tags":        ["string array, optional, max 50 items, each max 100 chars"]
}
```

**Response shape (`NodeResponse`):**
```json
{
  "node_id":     "UUID4 string",
  "work_id":     "UUID4 string",
  "author":      "string or null",
  "node_type":   "\"part\" | \"chapter\" | \"scene\" | \"beat\"",
  "parent_id":   "UUID4 string or null",
  "position":    "integer >= 0",
  "tag":         "string",
  "description": "string or null",
  "text":        "string or null",
  "previous":    "string or null",
  "next":        "string or null",
  "tags":        ["string array"],
  "created_at":  "ISO8601 UTC datetime",
  "updated_at":  "ISO8601 UTC datetime"
}
```

**Route handler logic in api.py (do not modify):**
1. Validate Work exists and belongs to `account_id` — if not: 404 `"Work not found"`
2. If `parent_id` provided: validate parent exists — if not: 404 `"Parent node not found"`
3. If `parent_id` provided: validate hierarchy — if invalid: 422 `"A {node_type} cannot be a child of a {parent_type}"`
4. If no `parent_id`: validate node_type is `"part"` — if not: 422 `"Only 'part' nodes may have no parent"`
5. Call `node_storage.create_node(account_id=account_id, work_doc=work, data=request.model_dump())`
6. Return the result with status 201

**What `create_node` does (do not modify):**
- `position` = max sibling position + 1, or 0 if no siblings
- `author` = copied from `work_doc.get("author")`
- Generates `node_id = str(uuid.uuid4())`
- Sets `created_at = updated_at = datetime.now(timezone.utc)`
- Inserts into `node_collection`
- Returns doc with `_id` stripped

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:writer` scope, a Work `W`, and no existing nodes WHEN `POST /nodes` is called with `{"work_id": W.work_id, "node_type": "part", "tag": "Part One"}` THEN the server returns HTTP 201 with a `NodeResponse` where `node_type: "part"`, `parent_id: null`, `position: 0`, and `author` equals the Work's `author` value.
2. GIVEN a valid JWT with `tree:writer` scope, a Work `W`, a Part node `P` WHEN `POST /nodes` is called with `{"work_id": W.work_id, "node_type": "chapter", "parent_id": P.node_id, "tag": "Chapter 1"}` THEN the server returns HTTP 201 with `node_type: "chapter"`, `parent_id: P.node_id`, `position: 0`.
3. GIVEN two existing sibling Part nodes at positions 0 and 1 WHEN a third Part node is created THEN `position` is 2.
4. GIVEN a valid JWT with `tree:writer` scope WHEN `POST /nodes` is called with `{"work_id": "non-existent-uuid...", ...}` THEN the server returns HTTP 404 with `detail: "Work not found"`.
5. GIVEN a valid JWT WHEN `POST /nodes` is called with a `work_id` that belongs to a different account THEN the server returns HTTP 404 with `detail: "Work not found"`.
6. GIVEN a valid JWT WHEN `POST /nodes` is called with a non-existent `parent_id` THEN the server returns HTTP 404 with `detail: "Parent node not found"`.
7. GIVEN a Part node `P` WHEN `POST /nodes` is called with `node_type: "scene"` and `parent_id: P.node_id` THEN the server returns HTTP 422 with `detail: "A scene cannot be a child of a part"`.
8. GIVEN no `parent_id` in the request WHEN `POST /nodes` is called with `node_type: "chapter"` THEN the server returns HTTP 422 with `detail: "Only 'part' nodes may have no parent"`.
9. GIVEN a valid JWT with `tree:writer` scope WHEN `POST /nodes` is called with `tag: "   "` (whitespace-only) THEN the server returns HTTP 422.
10. GIVEN no Authorization header WHEN `POST /nodes` is called THEN the server returns HTTP 401.
11. GIVEN a valid JWT with `tree:reader` scope only WHEN `POST /nodes` is called THEN the server returns HTTP 403 with `detail: "Insufficient permissions to complete action"`.

**Definition of Done:**
- Returns 201 with NodeResponse on valid input
- `response_model=NodeResponse` declared on decorator
- `author` in response equals Work's author field
- `position` is 0 for first sibling, increments for subsequent siblings
- All error detail strings match exactly as specified
- `account_id` absent from response

---

### Requirement 2: List Nodes

**User Story:** As an authenticated reader, I want to list all nodes for a Work (optionally filtered by type), so that I can see the structure of my narrative.

**Maps to:** `NodeStorage.list_nodes(work_id, account_id, node_type) -> list[dict]` (database.py:913) and `GET /works/{work_id}/nodes` handler `list_normalised_nodes` (api.py:436). (CONSTITUTION I.6, Part X Tier 2)

**Exact endpoint:**
```
Method:         GET
Path:           /works/{work_id}/nodes
Path params:    work_id — UUID4 pattern
Query params:   node_type — optional, one of: "part", "chapter", "scene", "beat"
Response body:  list[NodeResponse]
Status on success: 200
Required scope: tree:reader
OpenAPI tags:   ["Nodes"]
```

**Route handler logic (do not modify):**
1. Validate Work exists and belongs to `account_id` — if not: 404 `"Work not found"`
2. Call `node_storage.list_nodes(work_id, account_id, node_type=node_type.value if node_type else None)`
3. Return list

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:reader` scope and a Work with 3 nodes of different types WHEN `GET /works/{work_id}/nodes` is called with no query params THEN the server returns HTTP 200 with all 3 nodes as `NodeResponse` objects.
2. GIVEN a Work with 2 Part nodes and 2 Chapter nodes WHEN `GET /works/{work_id}/nodes?node_type=part` is called THEN only the 2 Part nodes are returned.
3. GIVEN a valid JWT WHEN `GET /works/{work_id}/nodes?node_type=invalid_type` is called THEN the server returns HTTP 422 (FastAPI/Pydantic rejects the invalid enum value).
4. GIVEN a valid JWT WHEN `GET /works/{work_id}/nodes` is called with a non-existent or cross-account `work_id` THEN the server returns HTTP 404 with `detail: "Work not found"`.
5. GIVEN a Work with no nodes WHEN `GET /works/{work_id}/nodes` is called THEN the server returns HTTP 200 with an empty array `[]`.
6. GIVEN User A has a Work and User B is authenticated WHEN User B calls `GET /works/{A's work_id}/nodes` THEN the server returns HTTP 404 (not 200).

**Definition of Done:**
- Returns 200 with list of NodeResponse
- `node_type` query param filter works correctly
- Invalid `node_type` value returns 422
- Work ownership enforced (404 for cross-account)

---

### Requirement 3: Get Single Node

**User Story:** As an authenticated reader, I want to fetch a specific node by its ID, so that I can display or edit its content.

**Maps to:** `NodeStorage.get_node(node_id, account_id) -> dict | None` (database.py:901) and `GET /nodes/{node_id}` handler `get_normalised_node` (api.py:466). (CONSTITUTION I.4)

**Exact endpoint:**
```
Method:         GET
Path:           /nodes/{node_id}
Path params:    node_id — must match UUID4 pattern via Path(pattern=UUID_PATTERN)
Response body:  NodeResponse
Status on success: 200
Required scope: tree:reader
OpenAPI tags:   ["Nodes"]
```

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:reader` scope and a `node_id` owned by the authenticated account WHEN `GET /nodes/{node_id}` is called THEN the server returns HTTP 200 with the full `NodeResponse` for that node.
2. GIVEN a valid JWT WHEN `GET /nodes/{node_id}` is called with a `node_id` that does not exist THEN the server returns HTTP 404 with `detail: "Node not found"`.
3. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `GET /nodes/{N.node_id}` THEN the server returns HTTP 404 (not HTTP 403). (CONSTITUTION I.4)
4. GIVEN a valid JWT WHEN `GET /nodes/{node_id}` is called where `node_id` is `"not-a-uuid"` THEN the server returns HTTP 422.
5. GIVEN no Authorization header WHEN `GET /nodes/{node_id}` is called THEN the server returns HTTP 401.

**Definition of Done:**
- 200 with full NodeResponse for owned node
- 404 with `"Node not found"` for missing or cross-account node
- 422 for invalid UUID4 path param
- `account_id` absent from response

---

### Requirement 4: Update Node

**User Story:** As an authenticated writer, I want to update node content or reparent a node, so that I can refine my narrative structure.

**Maps to:** `NodeStorage.update_node(node_id, account_id, updates) -> dict | None` (database.py:930) and `PUT /nodes/{node_id}` handler `update_normalised_node` (api.py:505). (CONSTITUTION I.2, I.5)

**Exact endpoint:**
```
Method:         PUT
Path:           /nodes/{node_id}
Path params:    node_id — UUID4 pattern
Request body:   UpdateNodeRequest (all fields optional)
Response body:  NodeResponse (updated state)
Status on success: 200
Required scope: tree:writer
OpenAPI tags:   ["Nodes"]
```

**Request shape (`UpdateNodeRequest` — all optional, omitted fields unchanged):**
```json
{
  "tag":         "string, optional, 1–200 chars, whitespace stripped",
  "parent_id":   "UUID4 string or null, optional",
  "description": "string, optional, max 2000 chars",
  "text":        "string, optional, max 50000 chars",
  "previous":    "string, optional, max 200 chars",
  "next":        "string, optional, max 200 chars",
  "tags":        ["string array, optional"]
}
```

**Route handler logic for reparenting (do not modify):**
When `parent_id` is present in the update payload:
1. Fetch new parent node — if not found: 404 `"Parent node not found"`
2. Fetch current node — if not found: 404 `"Node not found"`
3. Validate hierarchy: `is_valid_parent_child(parent["node_type"], node["node_type"])` — if invalid: 422 `"Invalid hierarchy: a {node_type} cannot be a child of a {parent_type}"`
4. Check cycle: `would_create_cycle(node_id, new_parent_id, account_id)` — if True: 422 `"Reparenting would create a cycle"`
5. Call `update_node` with updates dict (which includes new `parent_id` and auto-assigned `position` for new parent)

**What `update_node` does when `parent_id` changes (do not modify):**
- Queries siblings at new parent to find max position
- Sets `updates["position"] = max_sibling_position + 1` (or 0 if no siblings)
- Note: the old sibling group is NOT renumbered here — gaps may form. Use reorder for gap-free sequencing.

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:writer` scope and an owned node WHEN `PUT /nodes/{node_id}` is called with `{"tag": "Revised Title"}` THEN the server returns HTTP 200 with a `NodeResponse` where `tag` is `"Revised Title"` and `updated_at` is refreshed.
2. GIVEN a Chapter node with parent Part `P1`, and another Part `P2` WHEN `PUT /nodes/{chapter_id}` is called with `{"parent_id": P2.node_id}` THEN the server returns HTTP 200 and the chapter's `parent_id` is now `P2.node_id`.
3. GIVEN a Part node `A` and a Chapter node `B` (child of `A`) WHEN `PUT /nodes/{A.node_id}` is called with `{"parent_id": B.node_id}` THEN the server returns HTTP 422 with `detail: "Reparenting would create a cycle"`.
4. GIVEN a Part node `P` WHEN `PUT /nodes/{P.node_id}` is called with `{"parent_id": "non-existent-uuid..."}` THEN the server returns HTTP 404 with `detail: "Parent node not found"`.
5. GIVEN a Part node `P` and a Scene node `S` WHEN `PUT /nodes/{P.node_id}` is called with `{"parent_id": S.node_id}` (Part cannot be child of Scene) THEN the server returns HTTP 422 with `detail: "Invalid hierarchy: a part cannot be a child of a scene"`.
6. GIVEN a valid JWT WHEN `PUT /nodes/{node_id}` is called on a non-existent or cross-account node THEN the server returns HTTP 404 with `detail: "Node not found"`.
7. GIVEN a valid JWT with `tree:reader` scope only WHEN `PUT /nodes/{node_id}` is called THEN the server returns HTTP 403.
8. GIVEN a valid JWT WHEN `PUT /nodes/{node_id}` is called with `{"tag": ""}` THEN the server returns HTTP 422.

**Definition of Done:**
- 200 with updated NodeResponse
- `updated_at` refreshed on every update
- Reparenting validates hierarchy and cycle
- Exact error detail strings match spec
- Omitted fields not modified

---

### Requirement 5: Delete Node with Cascade

**User Story:** As an authenticated writer, I want to delete a node and all of its descendants, so that I can remove a story branch completely.

**Maps to:** `NodeStorage.delete_node_cascade(node_id, account_id) -> tuple[bool, int]` (database.py:967) and `DELETE /nodes/{node_id}` handler `delete_normalised_node` (api.py:584). (CONSTITUTION I.1, I.2)

**Exact endpoint:**
```
Method:         DELETE
Path:           /nodes/{node_id}
Path params:    node_id — UUID4 pattern
Response body:  {"detail": "Node deleted. {N} descendant(s) removed."}
Status on success: 200
Required scope: tree:writer
OpenAPI tags:   ["Nodes"]
```

**What `delete_node_cascade` does (do not modify):**
1. `get_node(node_id, account_id)` — returns `(False, 0)` if not found
2. BFS from `node_id` collecting all descendant `node_id` values into `all_ids`
3. Single `delete_many` with `{"account_id": account_id, "node_id": {"$in": all_ids}}`
4. Returns `(True, deleted_count - 1)` where -1 excludes the node itself

**Note:** `DELETE /nodes/{node_id}` currently lacks a `response_model` declaration (pre-existing violation of CONSTITUTION III.2). New delete endpoints MUST declare `response_model`.

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:writer` scope and a Part node with 2 child Chapter nodes, each with 1 Scene WHEN `DELETE /nodes/{part_node_id}` is called THEN the server returns HTTP 200 with `detail: "Node deleted. 4 descendant(s) removed."` and no nodes with that `work_id` subtree remain.
2. GIVEN a leaf Beat node (no children) WHEN `DELETE /nodes/{beat_node_id}` is called THEN the server returns HTTP 200 with `detail: "Node deleted. 0 descendant(s) removed."`.
3. GIVEN a valid JWT WHEN `DELETE /nodes/{node_id}` is called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.
4. GIVEN a valid JWT with `tree:reader` scope only WHEN `DELETE /nodes/{node_id}` is called THEN the server returns HTTP 403.
5. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `DELETE /nodes/{N.node_id}` THEN the server returns HTTP 404.

**Definition of Done:**
- Node and all descendants removed in single `delete_many`
- Response detail matches exact format `"Node deleted. {N} descendant(s) removed."`
- 404 for missing or cross-account node
- BFS traversal collects all descendants before deletion

---

## Non-Functional Requirements

### Requirement 6: Authentication and Scope Enforcement

**User Story:** As a system administrator, I want every Node endpoint to enforce JWT authentication and correct scope, so that unauthenticated clients cannot access narrative data.

**Maps to:** `Security(get_current_active_user_account, scopes=[...])` (CONSTITUTION II.2)

#### Acceptance Criteria

1. GIVEN no `Authorization` header WHEN any Node endpoint is called THEN the server returns HTTP 401.
2. GIVEN a valid JWT with only `tree:reader` scope WHEN a write endpoint (`POST /nodes`, `PUT /nodes/{id}`, `DELETE /nodes/{id}`) is called THEN the server returns HTTP 403.
3. GIVEN a valid JWT with only `tree:writer` scope (and not `tree:reader`) WHEN `GET /nodes/{id}` or `GET /works/{id}/nodes` is called THEN the server returns HTTP 403. (Note: `tree:writer` implies `tree:reader` is also in the standard token — this verifies the scope check is applied.)
4. GIVEN a blacklisted token WHEN any Node endpoint is called THEN the server returns HTTP 401.

---

### Requirement 7: Account Isolation

**User Story:** As a user, I want my nodes to be invisible to other users, so that my narrative content stays private.

**Maps to:** All `NodeStorage` queries include `{"account_id": account_id}` filter (CONSTITUTION I.4)

#### Acceptance Criteria

1. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `GET /nodes/{N.node_id}` THEN the server returns HTTP 404 (not 200, not 403).
2. GIVEN User A owns Work W and User B is authenticated WHEN User B calls `GET /works/{W.work_id}/nodes` THEN the server returns HTTP 404 (the work ownership check fails first).
3. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `PUT /nodes/{N.node_id}` with a valid body THEN the server returns HTTP 404.
4. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `DELETE /nodes/{N.node_id}` THEN the server returns HTTP 404.

---

### Requirement 8: Input Validation

**User Story:** As an API consumer, I want validation errors for malformed node requests, so that I can correct them programmatically.

**Maps to:** `CreateNodeRequest`, `UpdateNodeRequest`, `Path(pattern=UUID_PATTERN)` (CONSTITUTION II.4)

#### Acceptance Criteria

1. GIVEN `POST /nodes` with a `tag` field of 201 characters THEN the server returns HTTP 422.
2. GIVEN `POST /nodes` with `node_type: "volume"` (not in the enum) THEN the server returns HTTP 422.
3. GIVEN `POST /nodes` with a `work_id` that is not UUID4 format THEN the server returns HTTP 422.
4. GIVEN `GET /nodes/{node_id}` where `node_id` contains special characters THEN the server returns HTTP 422.
5. GIVEN `POST /nodes` with `tags` containing 51 items THEN the server returns HTTP 422.
6. GIVEN `POST /nodes` with a `tags` item that is a whitespace-only string `"   "` THEN the server returns HTTP 422.

---

### Requirement 9: Error Message Format

**User Story:** As an API consumer, I want sanitised error messages that reveal no internal state, so that my client code is secure.

**Maps to:** CONSTITUTION II.5, III.6

#### Acceptance Criteria

1. GIVEN any Node endpoint error THEN the response body is exactly `{"detail": "<message>"}` with no stack trace, no `account_id`, no MongoDB `_id`.
2. GIVEN a `ConnectionFailure` from MongoDB WHEN any Node endpoint is called THEN the server returns HTTP 503 with `detail: "Database error"`.
3. GIVEN a hierarchy violation THEN `detail` contains the exact node_type values from the request but no internal IDs.

---

## Correctness Properties

### Property 1: account_id Never Exposed

- **Description:** `account_id` MUST NOT appear in any NodeResponse. The `NodeResponse` Pydantic model excludes it by field selection. (CONSTITUTION I.4)
- **Testable:** Assert `"account_id"` key is absent from every node endpoint response body.

### Property 2: node_id is Always UUID4

- **Description:** Every node document MUST have a `node_id` matching the UUID4 pattern. (CONSTITUTION IV.4)
- **Testable:** After `POST /nodes`, assert `re.match(UUID4_PATTERN, response["node_id"])` is truthy.

### Property 3: position is Non-Negative

- **Description:** `position` MUST be a non-negative integer (>= 0). The first sibling gets `position: 0`, the next gets `position: 1`, and so on. (CONSTITUTION IV.5)
- **Testable:** Query all nodes for a work. Assert all `position` values are >= 0. Assert first node inserted has `position: 0`.

### Property 4: author Copied from Work at Creation

- **Description:** When a node is created, `author` MUST be set to `work_doc.get("author")`, not to any user-supplied value. If the Work has no author, node `author` is `null`. (CONSTITUTION I.7)
- **Testable:** Create a Work with `author: "Alice"`. Create a node in that Work. Assert the node's `author` field is `"Alice"`. Create a Work with no author. Assert the node's `author` is `null`.

### Property 5: Cascade Delete Removes All Descendants

- **Description:** After `DELETE /nodes/{node_id}`, no descendant nodes (at any depth) may remain in `node_collection`. (CONSTITUTION I.2)
- **Testable:** Create a 4-level hierarchy (Part → Chapter → Scene → Beat). Delete the Part. Query `node_collection` with the Part's `node_id` subtree — assert 0 documents remain.

### Property 6: node_type Immutable After Creation

- **Description:** The `node_type` of a node MUST NOT be changed via `PUT /nodes/{node_id}`. `UpdateNodeRequest` does not include `node_type`. The MongoDB validator enforces the enum on inserts only; the application does not expose update of `node_type`. (CONSTITUTION I.5, IV.3)
- **Testable:** Attempt to call `PUT /nodes/{id}` with `{"node_type": "scene"}` — assert the field is not present in `UpdateNodeRequest` (Pydantic rejects extra fields by default, or ignores them; verify `node_type` is unchanged after the call).
