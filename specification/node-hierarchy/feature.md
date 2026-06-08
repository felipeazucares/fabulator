# Feature Specification: Node Hierarchy

**Implementation status:** COMPLETE — `is_valid_parent_child`, `would_create_cycle`, `_VALID_CHILD` map, and MongoDB JSON Schema validator are all committed on branch `refactor/normalised-node-model`. Hierarchy enforcement is wired into `create_normalised_node` and `update_normalised_node` in api.py. This document is authoritative for verification and test authoring.

**Files in scope:**
- `server/app/database.py` — `_VALID_CHILD` dict (line 617), `is_valid_parent_child` function (line 626), `NodeStorage.would_create_cycle` method (line 1166), `_NODE_VALIDATOR` dict (line 654)
- `server/app/api.py` — hierarchy checks in `create_normalised_node` (lines 389–410) and `update_normalised_node` (lines 516–570)

---

## Introduction

Fabulator enforces a strict five-tier narrative hierarchy: Work → Part → Chapter → Scene → Beat. This is NOT an arbitrary constraint — it is a core modelling decision that ensures the tree always reflects a well-formed narrative structure. Hierarchy enforcement operates at three levels:

1. **Application level (create):** `is_valid_parent_child(parent_type, child_type)` is called before `create_node`. A Part with no parent is the only valid root.
2. **Application level (reparent):** The same check is applied when `parent_id` appears in a `PUT /nodes/{id}` body.
3. **Cycle detection (reparent):** `would_create_cycle` walks the `parent_id` chain from the proposed new parent up to the root, returning `True` if the node being reparented is found in that chain.
4. **MongoDB schema level:** The `_NODE_VALIDATOR` JSON Schema enforces `node_type` is one of `["part", "chapter", "scene", "beat"]` and rejects inserts that violate this.

(CONSTITUTION I.5)

---

## Glossary

| Term | Definition |
|------|-----------|
| **Hierarchy** | The fixed type chain: `null → part → chapter → scene → beat`. Each level has exactly one valid child type. |
| **_VALID_CHILD** | `dict[str | None, str | None]` in database.py: `{None: "part", "part": "chapter", "chapter": "scene", "scene": "beat", "beat": None}`. Encodes the complete hierarchy. |
| **is_valid_parent_child(parent_type, child_type)** | `bool`. Returns `True` if `_VALID_CHILD.get(parent_type) == child_type`. Module-level function in database.py. |
| **would_create_cycle(node_id, new_parent_id, account_id)** | `async bool`. Walks from `new_parent_id` up to root via `parent_id` pointers. Returns `True` if `node_id` is encountered (would create a cycle). |
| **Root node** | A Part node with `parent_id == null`. Only `"part"` nodes may be root. |
| **Beat** | Leaf node type. Cannot have children. Cannot be reparented to have children (hierarchy enforced). Cannot be duplicated (Beat guard in duplicate methods). |
| **Reparent** | Moving a node to a new parent via `PUT /nodes/{node_id}` with a new `parent_id`. Subject to both hierarchy and cycle validation. |
| **Cycle** | A situation where following `parent_id` pointers from a node eventually returns to that same node. Caused by setting a node's parent to one of its own descendants. |

---

## Functional Requirements

### Requirement 1: Valid Parent-Child Enforcement

**User Story:** As an authenticated writer, I want the API to reject invalid parent-child combinations, so that my narrative hierarchy always forms a correct Part → Chapter → Scene → Beat structure.

**Maps to:** `is_valid_parent_child(parent_type, child_type)` in database.py (line 626) called from `create_normalised_node` (api.py:399) and `update_normalised_node` (api.py:545). (CONSTITUTION I.5)

**`_VALID_CHILD` lookup table (do not modify):**
```python
{
    None:      "part",     # root level: only part may have no parent
    "part":    "chapter",  # part's only valid child is chapter
    "chapter": "scene",    # chapter's only valid child is scene
    "scene":   "beat",     # scene's only valid child is beat
    "beat":    None,       # beat is a leaf — no valid children
}
```

**`is_valid_parent_child` function signature (do not modify):**
```python
def is_valid_parent_child(parent_type: str | None, child_type: str) -> bool:
    return _VALID_CHILD.get(parent_type) == child_type
```

#### Acceptance Criteria

1. GIVEN `is_valid_parent_child(None, "part")` is called THEN it returns `True`.
2. GIVEN `is_valid_parent_child("part", "chapter")` is called THEN it returns `True`.
3. GIVEN `is_valid_parent_child("chapter", "scene")` is called THEN it returns `True`.
4. GIVEN `is_valid_parent_child("scene", "beat")` is called THEN it returns `True`.
5. GIVEN `is_valid_parent_child(None, "chapter")` is called THEN it returns `False`.
6. GIVEN `is_valid_parent_child(None, "scene")` is called THEN it returns `False`.
7. GIVEN `is_valid_parent_child(None, "beat")` is called THEN it returns `False`.
8. GIVEN `is_valid_parent_child("part", "scene")` is called THEN it returns `False`.
9. GIVEN `is_valid_parent_child("part", "beat")` is called THEN it returns `False`.
10. GIVEN `is_valid_parent_child("beat", "beat")` is called THEN it returns `False` (Beat is a leaf).
11. GIVEN a valid JWT WHEN `POST /nodes` is called with `node_type: "scene"` and a Part `parent_id` THEN the server returns HTTP 422 with `detail: "A scene cannot be a child of a part"`.
12. GIVEN a valid JWT WHEN `POST /nodes` is called with `node_type: "part"` and no `parent_id` THEN the server returns HTTP 201 (only valid root type).
13. GIVEN a valid JWT WHEN `POST /nodes` is called with `node_type: "chapter"` and no `parent_id` THEN the server returns HTTP 422 with `detail: "Only 'part' nodes may have no parent"`.
14. GIVEN a valid JWT WHEN `POST /nodes` is called with `node_type: "beat"` and no `parent_id` THEN the server returns HTTP 422 with `detail: "Only 'part' nodes may have no parent"`.
15. GIVEN a Scene node `S` WHEN `PUT /nodes/{P.node_id}` is called with `{"parent_id": S.node_id}` where `P` is a Part node THEN the server returns HTTP 422 with `detail: "Invalid hierarchy: a part cannot be a child of a scene"`.

**Definition of Done:**
- All 15 acceptance criteria pass
- `is_valid_parent_child` function unchanged from committed version
- The `_VALID_CHILD` dict unchanged

---

### Requirement 2: Root-Only Constraint for Part Nodes

**User Story:** As an authenticated writer, I want the API to ensure only Part nodes can be root-level (no parent), so that the hierarchy starts correctly at Part level.

**Maps to:** `is_valid_parent_child(None, child_type)` check in `create_normalised_node` (api.py:406–410). (CONSTITUTION I.5)

**Code location (do not modify, api.py:404–410):**
```python
else:
    # No parent: only "part" may be a root node.
    if not is_valid_parent_child(None, request.node_type):
        raise HTTPException(
            status_code=422,
            detail="Only 'part' nodes may have no parent",
        )
```

#### Acceptance Criteria

1. GIVEN a valid JWT WHEN `POST /nodes` is called with `{"node_type": "part", ...}` and no `parent_id` THEN the server returns HTTP 201.
2. GIVEN a valid JWT WHEN `POST /nodes` is called with `{"node_type": "chapter", ...}` and no `parent_id` THEN the server returns HTTP 422 with exact `detail: "Only 'part' nodes may have no parent"`.
3. GIVEN a valid JWT WHEN `POST /nodes` is called with `{"node_type": "scene", ...}` and no `parent_id` THEN the server returns HTTP 422 with exact `detail: "Only 'part' nodes may have no parent"`.
4. GIVEN a valid JWT WHEN `POST /nodes` is called with `{"node_type": "beat", ...}` and no `parent_id` THEN the server returns HTTP 422 with exact `detail: "Only 'part' nodes may have no parent"`.

**Definition of Done:**
- All four acceptance criteria pass
- Error detail is exactly `"Only 'part' nodes may have no parent"` (no trailing period, exact case)

---

### Requirement 3: Cycle Detection on Reparent

**User Story:** As an authenticated writer, I want the API to prevent reparenting a node to one of its own descendants, so that the hierarchy never contains circular references.

**Maps to:** `NodeStorage.would_create_cycle(node_id, new_parent_id, account_id) -> bool` (database.py:1166) called from `update_normalised_node` (api.py:554–570). (CONSTITUTION I.5)

**`would_create_cycle` algorithm (do not modify):**
1. Start at `current_id = new_parent_id`
2. Walk up `parent_id` chain: for each node, fetch `{parent_id: 1}` from `node_collection`
3. If `current_id == node_id` at any step → return `True` (cycle detected)
4. Track `visited` set to break on existing cycles in the current data
5. If `current_id` is `None` (reached a root) → return `False` (no cycle)

**Error message on detection (api.py:568–570):**
```python
raise HTTPException(
    status_code=422,
    detail="Reparenting would create a cycle",
)
```

#### Acceptance Criteria

1. GIVEN a Part node `A` with Chapter child `B` WHEN `PUT /nodes/{A.node_id}` is called with `{"parent_id": B.node_id}` (making A a child of its own descendant) THEN the server returns HTTP 422 with `detail: "Reparenting would create a cycle"`.
2. GIVEN a Part → Chapter → Scene chain WHEN `PUT /nodes/{part_id}` is called with `{"parent_id": scene_id}` THEN the server returns HTTP 422 with `detail: "Reparenting would create a cycle"`.
3. GIVEN a Part node `P` and an unrelated Part node `Q` WHEN `PUT /nodes/{Q.node_id}` is called with `{"parent_id": P.node_id}` — this is also invalid because Part cannot be child of Part (hierarchy check fires first), so the server returns HTTP 422 with the hierarchy error, not the cycle error.
4. GIVEN `would_create_cycle(node_id="A", new_parent_id="A", account_id=...)` is called (self-loop) THEN it returns `True`.
5. GIVEN `would_create_cycle(node_id="A", new_parent_id="B", account_id=...)` where `B` has no ancestors THEN it returns `False`.
6. GIVEN `would_create_cycle(node_id="A", new_parent_id="C", account_id=...)` where `C`'s ancestor chain is `C → B → A` THEN it returns `True`.

**Definition of Done:**
- `would_create_cycle` method unchanged from committed version
- All 6 acceptance criteria pass
- Cycle check runs AFTER hierarchy check in `update_normalised_node`

---

### Requirement 4: MongoDB JSON Schema Validator for node_type

**User Story:** As a system administrator, I want the MongoDB schema validator to enforce `node_type` values, so that invalid data cannot be written to `node_collection` even if application validation is bypassed.

**Maps to:** `_NODE_VALIDATOR` dict (database.py:654) applied to `node_collection` via `setup_collections`. (CONSTITUTION I.5, IV.3, IV.7)

**Enforced constraints in `_NODE_VALIDATOR` (do not modify):**
```python
"node_type": {
    "bsonType": "string",
    "enum": ["part", "chapter", "scene", "beat"]
}
```

#### Acceptance Criteria

1. GIVEN `node_collection` is created or has its validator updated by `setup_collections` WHEN a document is inserted directly (bypassing the API) with `node_type: "volume"` THEN MongoDB rejects the insert with a validation error.
2. GIVEN `node_collection` validator is active WHEN a document is inserted with `node_type: "part"` THEN the insert succeeds.
3. GIVEN `setup_collections` is called on a database where `node_collection` already exists THEN the validator is updated via `collMod` without data loss.

**Definition of Done:**
- `_NODE_VALIDATOR` contains `enum: ["part", "chapter", "scene", "beat"]` on the `node_type` field
- `setup_collections` applies the validator on both new and existing collections

---

## Non-Functional Requirements

### Requirement 5: Hierarchy Errors Return HTTP 422

**User Story:** As an API consumer, I want hierarchy violations to return 422 (not 400 or 500), so that my client can distinguish validation errors from other errors.

**Maps to:** CONSTITUTION III.5 (HTTP 422 for validation errors)

#### Acceptance Criteria

1. GIVEN any invalid parent-child combination WHEN `POST /nodes` is called THEN the status code is exactly 422.
2. GIVEN any hierarchy violation on reparent WHEN `PUT /nodes/{id}` is called THEN the status code is exactly 422.
3. GIVEN a cycle detection result WHEN `PUT /nodes/{id}` is called THEN the status code is exactly 422.

---

### Requirement 6: Hierarchy Error Messages are Sanitised

**User Story:** As a security reviewer, I want hierarchy error messages to include only node type names, not internal IDs or account data.

**Maps to:** CONSTITUTION II.5

#### Acceptance Criteria

1. GIVEN `detail: "A scene cannot be a child of a part"` THEN the detail contains only `node_type` values from the request — no `node_id`, no `account_id`, no MongoDB `_id`.
2. GIVEN `detail: "Reparenting would create a cycle"` THEN the detail is a static string with no dynamic values.
3. GIVEN `detail: "Invalid hierarchy: a part cannot be a child of a scene"` THEN the detail contains only type names.

---

### Requirement 7: Hierarchy Check Precedes Cycle Check

**User Story:** As an API consumer, I want consistent ordering of validation — hierarchy checked before cycle — so that error messages are predictable.

**Maps to:** Order of checks in `update_normalised_node` (api.py:516–570) (CONSTITUTION III.5)

#### Acceptance Criteria

1. GIVEN a reparent request that violates both hierarchy and would create a cycle WHEN `PUT /nodes/{id}` is called THEN the server returns the hierarchy error (422) NOT the cycle error. The hierarchy check runs first because `is_valid_parent_child` is checked at api.py:545 before `would_create_cycle` is called at api.py:554.

---

## Correctness Properties

### Property 1: Strict Hierarchy Invariant

- **Description:** At every moment, every non-Part node MUST have a `parent_id` that points to a node of the correct parent type. The hierarchy chain root→part→chapter→scene→beat MUST be enforceable by traversing `parent_id` pointers. No skipped levels are permitted. (CONSTITUTION I.5)
- **Testable:** For each node in `node_collection`, fetch its parent and assert `_VALID_CHILD[parent_type] == node_type`. Test against a fully populated work.

### Property 2: Part is the Only Valid Root

- **Description:** A node with `parent_id == null` MUST have `node_type == "part"`. (CONSTITUTION I.5)
- **Testable:** Query `node_collection` for `{parent_id: null}`. Assert every result has `node_type: "part"`.

### Property 3: No Cycles in parent_id Chain

- **Description:** Following `parent_id` from any node MUST eventually reach a node with `parent_id == null` (a Part), without revisiting any node. (CONSTITUTION I.5)
- **Testable:** For a representative sample of nodes, walk the `parent_id` chain using a `visited` set. Assert the chain terminates without repeating any node.

### Property 4: Beat Has No Children

- **Description:** Because only `_VALID_CHILD["beat"] == None`, no node may have `parent_id` pointing to a Beat node via the API. The MongoDB validator does not enforce child constraints directly, but the application layer enforces it on every create. (CONSTITUTION I.5)
- **Testable:** Attempt `POST /nodes` with `parent_id = beat_node_id` and any `node_type`. Assert HTTP 422 is returned. Query `node_collection` for `{parent_id: beat_node_id}` and assert empty result.
