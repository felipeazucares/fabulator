# Feature Specification: Node Reorder

**Implementation status:** COMPLETE — `reorder_siblings` in database.py and the `PUT /nodes/{node_id}/reorder` endpoint in api.py are committed on branch `refactor/normalised-node-model`. This document is authoritative for verification, test authoring, and corrective changes.

**Files in scope:**
- `server/app/database.py` — `NodeStorage.reorder_siblings` (line 897)
- `server/app/api.py` — `reorder_node` handler (line 929)
- `server/app/models.py` — `ReorderRequest`

---

## Introduction

Reordering allows a node to change its position among its siblings without changing its parent. The operation rebuilds the full sibling sequence: the target node is moved to the requested position, and all other siblings are renumbered so positions remain a contiguous zero-based sequence with no gaps. This is distinct from `update_node` (which appends to end when reparenting) — reorder explicitly targets a specific position.

The `position` value in a `ReorderRequest` is the desired 0-based index in the sibling list. Values exceeding the last valid index are clamped to `len(siblings) - 1`. A single-node sibling group clamps to 0. (CONSTITUTION IV.5, DESIGN Part V OD-01)

---

## Glossary

| Term | Definition |
|------|-----------|
| **sibling group** | All nodes sharing the same `{parent_id, work_id, account_id}` — the set that `reorder_siblings` operates on. |
| **position** | Zero-based integer index of a node among its siblings. After reorder, the entire sibling group is renumbered 0, 1, 2, ... with no gaps. |
| **clamping** | If `new_position >= len(siblings)`, it is clamped to `len(siblings) - 1`. If `new_position < 0`, `ReorderRequest` validation rejects it as 422. |
| **ReorderRequest** | Pydantic model in models.py: `{"position": int}`. Validates `position >= 0`. |
| **NodeResponse** | Response model. Contains `position` field reflecting the new position after reorder. |
| **reorder_siblings** | `NodeStorage` async method. Fetches all siblings, inserts the node at the clamped position, renumbers sequentially, returns the updated node. |

---

## Functional Requirements

### Requirement 1: Reorder Node Among Siblings

**User Story:** As an authenticated writer, I want to move a node to a specific position among its siblings, so that I can arrange chapters or scenes in the desired narrative order.

**Maps to:** `NodeStorage.reorder_siblings(node_id, account_id, new_position) -> dict | None` (database.py:1192) — this method is complete. Wrap it in an API endpoint. (CONSTITUTION IV.5, DESIGN OD-01)

**Task ordering:** This is Task 1. No dependencies on other tasks in this spec.

**Exact endpoint to ADD to api.py:**
```
Method:         PUT
Path:           /nodes/{node_id}/reorder
Path params:    node_id — UUID4 pattern via Path(pattern=UUID_PATTERN)
Request body:   ReorderRequest
Response body:  NodeResponse (updated node with new position)
Status on success: 200
Required scope: tree:writer
OpenAPI tags:   ["Nodes"]
```

**Request shape (`ReorderRequest` — already in models.py):**
```json
{
  "position": "integer >= 0"
}
```

**Response:** `NodeResponse` for the moved node, with `position` reflecting the actual new position (may differ from the requested value due to clamping).

**How `reorder_siblings` works (do not modify — database.py:1192–1230):**
1. Fetch the target node via `get_node`. If `None`, return `None`.
2. Fetch all siblings (including the target itself) sorted by `position` ascending via `find({account_id, parent_id, work_id})`.
3. Clamp: `clamped = min(new_position, max(0, len(siblings) - 1))`.
4. Remove the target from the ordered list, then insert it at `clamped`.
5. Renumber all items: `for i, s in enumerate(ordered): update_one({node_id: s["node_id"]}, {$set: {position: i}})`.
6. Return the updated target node via `get_node`.

**Exact function signature to insert in api.py:**
```python
@app.put(
    "/nodes/{node_id}/reorder",
    response_model=NodeResponse,
    summary="Reorder a node among its siblings",
    description=(
        "Move the specified node to a new zero-based position among its siblings. "
        "All siblings are renumbered to maintain a contiguous sequence. "
        "Positions exceeding the maximum sibling index are clamped to the last valid index. "
        "Returns 404 if the node does not exist or belongs to a different account."
    ),
    tags=["Nodes"],
)
async def reorder_node(
    node_id: str = Path(..., pattern=UUID_PATTERN),
    request: ReorderRequest = Body(...),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:writer"]),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> dict:
    logger.debug(f"reorder_node({node_id}, position={request.position}) called")
    try:
        result = await node_storage.reorder_siblings(
            node_id=node_id,
            account_id=account_id,
            new_position=request.position,
        )
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error in reorder_node for {node_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if result is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return result
```

**Insertion point in api.py:** Insert anywhere in the Node CRUD section (after the existing 5 node handlers, before the authentication functions). The route path `/nodes/{node_id}/reorder` is distinct from `/nodes/{node_id}` — FastAPI will not confuse them because `reorder` is a literal 4th path segment.

**Imports required:** `ReorderRequest` is already imported in api.py (line 52). `Body` is already imported (line 7). No new imports needed.

**What MUST NOT be changed:** `NodeStorage.reorder_siblings`, `ReorderRequest`, any existing node handler.

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:writer` scope and 3 sibling Chapter nodes at positions 0, 1, 2 WHEN `PUT /nodes/{chapter_2_id}/reorder` is called with `{"position": 0}` THEN the server returns HTTP 200 with a NodeResponse where `position` is 0, and the other two chapters are renumbered to positions 1 and 2.
2. GIVEN a valid JWT and 3 sibling Chapter nodes at positions 0, 1, 2 WHEN `PUT /nodes/{chapter_0_id}/reorder` is called with `{"position": 2}` THEN the server returns HTTP 200 with a NodeResponse where `position` is 2.
3. GIVEN a valid JWT and 3 sibling nodes WHEN `PUT /nodes/{node_id}/reorder` is called with `{"position": 100}` (exceeds maximum) THEN the server returns HTTP 200 with a NodeResponse where `position` is 2 (clamped to last valid index).
4. GIVEN a valid JWT and a node that is the only child of its parent WHEN `PUT /nodes/{node_id}/reorder` is called with `{"position": 5}` THEN the server returns HTTP 200 with a NodeResponse where `position` is 0 (single item clamps to 0).
5. GIVEN a valid JWT WHEN `PUT /nodes/{node_id}/reorder` is called with `{"position": -1}` THEN the server returns HTTP 422 (negative position rejected by ReorderRequest validator).
6. GIVEN a valid JWT WHEN `PUT /nodes/{node_id}/reorder` is called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.
7. GIVEN no Authorization header WHEN `PUT /nodes/{node_id}/reorder` is called THEN the server returns HTTP 401.
8. GIVEN a valid JWT with `tree:reader` scope only WHEN `PUT /nodes/{node_id}/reorder` is called THEN the server returns HTTP 403 with `detail: "Insufficient permissions to complete action"`.
9. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `PUT /nodes/{N.node_id}/reorder` with a valid body THEN the server returns HTTP 404.

**Definition of Done:**
- Function `reorder_node` exists in api.py
- `response_model=NodeResponse` declared
- `summary`, `description`, `tags=["Nodes"]` declared
- Negative `position` returns 422 (Pydantic ReorderRequest validation)
- Clamping is performed by `reorder_siblings` — API does not need additional clamping logic
- After the call, all siblings of the target node have contiguous 0-based positions
- 404 for missing/cross-account node

---

### Requirement 2: Sibling Renumbering After Reorder

**User Story:** As a system, I want all siblings to be renumbered after every reorder, so that `position` values are always a contiguous zero-based sequence.

**Maps to:** Renumbering loop in `NodeStorage.reorder_siblings` (database.py:1219–1229). Application-level invariant. (CONSTITUTION IV.5)

#### Acceptance Criteria

1. GIVEN 4 sibling nodes at positions 0, 1, 2, 3 WHEN `reorder_siblings` is called to move position 3 to position 0 THEN all 4 nodes are renumbered to positions 0, 1, 2, 3 respectively (no gaps remain).
2. GIVEN 3 sibling nodes WHEN ANY reorder is performed THEN querying `node_collection` for those siblings and sorting by `position` yields consecutive integers starting from 0.

**Definition of Done:**
- After any reorder call, querying sibling documents in `node_collection` yields positions `0, 1, 2, ..., N-1` with no gaps and no duplicates.

---

## Non-Functional Requirements

### Requirement 3: Authentication and Scope Enforcement

**User Story:** As a system administrator, I want the reorder endpoint to enforce `tree:writer` scope, so that readers cannot rearrange the narrative structure.

**Maps to:** `Security(get_current_active_user_account, scopes=["tree:writer"])` (CONSTITUTION II.2)

#### Acceptance Criteria

1. GIVEN no `Authorization` header WHEN `PUT /nodes/{node_id}/reorder` is called THEN the server returns HTTP 401.
2. GIVEN a token with only `tree:reader` scope WHEN `PUT /nodes/{node_id}/reorder` is called THEN the server returns HTTP 403.
3. GIVEN a blacklisted token WHEN `PUT /nodes/{node_id}/reorder` is called THEN the server returns HTTP 401.

---

### Requirement 4: Account Isolation

**User Story:** As a user, I want reorder to be account-isolated so that I cannot reorder another user's nodes.

**Maps to:** `reorder_siblings` calls `get_node(node_id, account_id)` which filters by `account_id` (CONSTITUTION I.4)

#### Acceptance Criteria

1. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `PUT /nodes/{N.node_id}/reorder` THEN the server returns HTTP 404 (not 403).

---

### Requirement 5: Input Validation

**User Story:** As an API consumer, I want position validation to reject negative integers immediately.

**Maps to:** `ReorderRequest.validate_position` validator in models.py (CONSTITUTION II.4)

#### Acceptance Criteria

1. GIVEN `PUT /nodes/{node_id}/reorder` is called with `{"position": -1}` THEN the server returns HTTP 422.
2. GIVEN `PUT /nodes/{node_id}/reorder` is called with `{"position": "abc"}` (non-integer) THEN the server returns HTTP 422.
3. GIVEN `PUT /nodes/{node_id}/reorder` is called with no body THEN the server returns HTTP 422.
4. GIVEN a `node_id` path parameter that is not a valid UUID4 THEN the server returns HTTP 422.

---

### Requirement 6: Error Message Format

**User Story:** As an API consumer, I want reorder errors to use sanitised messages.

**Maps to:** CONSTITUTION II.5, III.6

#### Acceptance Criteria

1. GIVEN a 404 error from the reorder endpoint THEN `detail` is exactly `"Node not found"`.
2. GIVEN a database failure WHEN `PUT /nodes/{node_id}/reorder` is called THEN HTTP 503 with `detail: "Database error"`.

---

## Correctness Properties

### Property 1: Contiguous Zero-Based Positions After Reorder

- **Description:** After every call to `reorder_siblings`, the sibling group MUST have positions `0, 1, 2, ..., N-1` with no gaps and no duplicate values. This is guaranteed by the renumbering loop in `reorder_siblings`. (CONSTITUTION IV.5)
- **Testable:** After any reorder call, query `node_collection` for `{account_id, parent_id, work_id}`, sort by position, assert positions form a consecutive sequence starting at 0.

### Property 2: Position Clamped to Valid Range

- **Description:** The actual `position` assigned to the moved node MUST be in `[0, len(siblings) - 1]`. Requesting a position beyond this range MUST result in the node being placed last. Requesting position 0 for a single-node group results in position 0. (CONSTITUTION IV.5)
- **Testable:** Request `position: 999` for a 3-sibling group. Assert resulting `position` is 2. Request `position: 5` for a single-node group. Assert resulting `position` is 0.

### Property 3: Node Stays in Same Work After Reorder

- **Description:** Reordering MUST NOT change a node's `work_id`, `parent_id`, `node_type`, `tag`, or content fields. Only `position` and `updated_at` are changed. (CONSTITUTION I.2)
- **Testable:** Record all fields before reorder. Assert all fields except `position` and `updated_at` are unchanged after reorder.
