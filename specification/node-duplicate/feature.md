# Feature Specification: Node Duplicate

**Implementation status:** PARTIALLY COMPLETE. `NodeStorage.duplicate_shallow` and `NodeStorage.duplicate_deep` are committed in database.py (lines 1232–1376). Both include a Beat guard that returns `None` for Beat nodes. **The API endpoints do NOT yet exist in api.py.** This spec describes exactly what to add.

**Files to modify:**
- `server/app/api.py` — add 1 new route handler function that handles both shallow and deep duplication via a query parameter

**Files NOT to modify:**
- `server/app/database.py` — `duplicate_shallow` and `duplicate_deep` are complete; do not touch
- `server/app/models.py` — all necessary models exist; do not touch

---

## Introduction

Node duplication creates a copy of a node (and optionally its entire subtree) as a new sibling immediately after the original. The operation assigns fresh UUIDs to all copied documents. The root copy's tag gets a `" (copy)"` suffix; child copies in a deep duplicate preserve original tags.

Beat nodes (the terminal leaf type) MUST NOT be duplicated — they represent atomic story beats that cannot be meaningfully branched. The Beat guard is enforced at both the DB layer (returns `None`) and the API layer (returns HTTP 400 before calling DB methods).

One endpoint covers both shallow and deep: `POST /nodes/{node_id}/duplicate` with an optional `?deep=true` query parameter. (CONSTITUTION Part X Tier 1, DESIGN Part X OD-02)

---

## Glossary

| Term | Definition |
|------|-----------|
| **shallow duplicate** | Copy of a node with no children. New `node_id` (UUID4), tag gets `" (copy)"` suffix, position is `original.position + 1`. Siblings after the original shift up by 1. |
| **deep duplicate** | Recursive copy of a node and all its descendants. Root copy gets `" (copy)"` suffix; child copies keep original tags. All copied nodes get fresh UUID4 `node_id` values. |
| **Beat guard** | Check that prevents duplication of Beat nodes. Applied FIRST in the API handler (before calling DB methods) — returns HTTP 400 with `detail: "Beat nodes cannot be duplicated"` if `node_type == "beat"`. |
| **sibling shift** | Before inserting the copy, `duplicate_shallow/deep` increments `position` by 1 for all siblings whose position > original's position. This makes room for the copy at `original.position + 1`. |
| **fresh UUID** | All copies get `node_id = str(uuid.uuid4())`. The original node's `node_id` is never reused or carried over. |
| **_is_root_call** | Internal parameter to `duplicate_deep`. `True` for the first call (applies sibling shift, adds `" (copy)"` suffix). `False` for recursive child calls (no shift, no suffix). Do not set this in the API handler — use the default. |

---

## Functional Requirements

### Requirement 1: Shallow Duplicate a Node

**User Story:** As an authenticated writer, I want to create a copy of a node (without its children) as the next sibling, so that I can quickly create a structural variant.

**Maps to:** `NodeStorage.duplicate_shallow(node_id, account_id) -> dict | None` (database.py:1232). (CONSTITUTION Part X Tier 1)

**Task ordering:** Task 1. No dependencies on other tasks.

**Exact endpoint to ADD to api.py (handles both shallow and deep via `deep` query param):**
```
Method:         POST
Path:           /nodes/{node_id}/duplicate
Path params:    node_id — UUID4 pattern via Path(pattern=UUID_PATTERN)
Query params:   deep — optional bool, default False
Request body:   none
Response body:  NodeResponse (the new copy)
Status on success: 201
Required scope: tree:writer
OpenAPI tags:   ["Nodes"]
```

**What `duplicate_shallow` does (do not modify — database.py:1232–1285):**
1. Fetches the source node via `get_node`. Returns `None` if not found.
2. If `node["node_type"] == "beat"` → returns `None` (Beat guard). The API handler must check before calling — see below.
3. Increments `position` of all siblings with `position > source.position` by 1.
4. Creates new doc with: new `node_id` (UUID4), tag = `"{source.tag} (copy)"`, `position = source.position + 1`, all other fields copied from source, fresh `created_at`/`updated_at`.
5. Inserts into `node_collection`.
6. Returns new doc with `_id` stripped.

**What `duplicate_deep` does (do not modify — database.py:1287–1376):**
1. Same Beat guard and not-found check.
2. On root call (`_is_root_call=True`): shifts siblings, tag gets `" (copy)"`, position = `source.position + 1`.
3. Inserts new doc with fresh `node_id`.
4. Recursively calls itself for each child of the source (passing `_new_parent_id=new_node_id`, `_is_root_call=False`).
5. Returns the root new doc.

**CRITICAL — Beat guard handling in the API:** Because both DB methods return `None` both when the source is not found AND when the source is a Beat, the API handler MUST check node existence and type BEFORE calling the DB method:
1. Call `get_node(node_id, account_id)` first.
2. If `None` → HTTP 404, `detail: "Node not found"`.
3. If `node["node_type"] == "beat"` → HTTP 400, `detail: "Beat nodes cannot be duplicated"`.
4. Otherwise → call `duplicate_shallow` or `duplicate_deep`.

**Exact function signature to insert in api.py:**
```python
@app.post(
    "/nodes/{node_id}/duplicate",
    response_model=NodeResponse,
    status_code=201,
    summary="Duplicate a node",
    description=(
        "Create a copy of the specified node as the next sibling. "
        "The copy receives a new UUID and a '(copy)' suffix on its tag. "
        "Pass ?deep=true to recursively copy all descendants with fresh UUIDs. "
        "Beat nodes cannot be duplicated. "
        "Returns 404 if the node does not exist or belongs to a different account. "
        "Returns 400 if the node is a Beat."
    ),
    tags=["Nodes"],
)
async def duplicate_node(
    node_id: str = Path(..., pattern=UUID_PATTERN),
    deep: bool = False,
    account_id: str = Security(get_current_active_user_account, scopes=["tree:writer"]),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> dict:
    logger.debug(f"duplicate_node({node_id}, deep={deep}) called")
    # Existence and Beat-guard check BEFORE calling DB duplicate methods.
    try:
        source = await node_storage.get_node(node_id=node_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error checking node in duplicate_node for {node_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if source is None:
        raise HTTPException(status_code=404, detail="Node not found")
    if source["node_type"] == "beat":
        raise HTTPException(status_code=400, detail="Beat nodes cannot be duplicated")

    try:
        if deep:
            result = await node_storage.duplicate_deep(
                node_id=node_id, account_id=account_id
            )
        else:
            result = await node_storage.duplicate_shallow(
                node_id=node_id, account_id=account_id
            )
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error in duplicate_node for {node_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if result is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return result
```

**Insertion point in api.py:** Insert after the `delete_normalised_node` handler (after line 609) and before the authentication helper functions. The path `/nodes/{node_id}/duplicate` is distinct from `/nodes/{node_id}` — FastAPI will not confuse them.

**Imports required:** No new imports needed. `NodeResponse` is already imported. `Body` is not needed (no request body for this endpoint). `bool` and `False` are Python builtins.

**What MUST NOT be changed:** `NodeStorage.duplicate_shallow`, `NodeStorage.duplicate_deep`, any existing node handler, `NodeResponse`.

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:writer` scope and a Chapter node `C` at position 1 with siblings at positions 0 and 2 WHEN `POST /nodes/{C.node_id}/duplicate` is called (no query params) THEN the server returns HTTP 201 with a NodeResponse where `tag` is `"{C.tag} (copy)"`, `position` is 2, and the former position-2 sibling is now at position 3.
2. GIVEN a valid JWT and a Chapter node `C` at position 0 with no children WHEN `POST /nodes/{C.node_id}/duplicate` (shallow) is called THEN the result has no children (verified by calling `GET /nodes/{new_id}/children` → empty list).
3. GIVEN a valid JWT and a Part node `P` with 2 child Chapters, each with 1 Scene WHEN `POST /nodes/{P.node_id}/duplicate?deep=true` is called THEN the server returns HTTP 201 with a NodeResponse for the Part copy, and the copy has 2 Chapter children each with 1 Scene child (all with new `node_id` values).
4. GIVEN a valid JWT WHEN `POST /nodes/{beat_id}/duplicate` is called on a Beat node THEN the server returns HTTP 400 with `detail: "Beat nodes cannot be duplicated"`.
5. GIVEN a valid JWT WHEN `POST /nodes/{beat_id}/duplicate?deep=true` is called on a Beat node THEN the server returns HTTP 400 with `detail: "Beat nodes cannot be duplicated"`.
6. GIVEN a valid JWT WHEN `POST /nodes/{node_id}/duplicate` is called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.
7. GIVEN no Authorization header WHEN `POST /nodes/{node_id}/duplicate` is called THEN the server returns HTTP 401.
8. GIVEN a valid JWT with `tree:reader` scope only WHEN `POST /nodes/{node_id}/duplicate` is called THEN the server returns HTTP 403.
9. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `POST /nodes/{N.node_id}/duplicate` THEN the server returns HTTP 404.

**Definition of Done:**
- Function `duplicate_node` exists in api.py
- `response_model=NodeResponse` and `status_code=201` declared
- `summary`, `description`, `tags=["Nodes"]` declared
- Beat guard check runs BEFORE calling DB methods
- `deep=False` uses `duplicate_shallow`; `deep=True` uses `duplicate_deep`
- Beat nodes return HTTP 400 with exact detail string
- Missing/cross-account nodes return HTTP 404
- Shallow copy has no children
- Deep copy replicates full subtree with fresh UUIDs

---

### Requirement 2: Deep Duplicate Preserves Subtree

**User Story:** As an authenticated writer, I want a deep copy to recursively copy all descendants, so that I can branch an entire story section.

**Maps to:** `NodeStorage.duplicate_deep` recursive implementation (database.py:1287–1376). (CONSTITUTION Part X Tier 1)

**This requirement describes verification criteria for the already-implemented `duplicate_deep` method — no code changes needed.**

#### Acceptance Criteria

1. GIVEN a Part node `P` with 2 Chapter children (`C1`, `C2`), each with 2 Scene children WHEN `duplicate_deep(P.node_id, ...)` is called THEN the result has 2 Chapter children (new UUIDs), each with 2 Scene children (new UUIDs) — 6 new nodes total.
2. GIVEN a Part copy from deep duplicate THEN the root copy's `tag` ends with `" (copy)"` but child copies have unmodified original tags.
3. GIVEN a Part with 3 Chapter children WHEN deep duplicated THEN the 3 Chapter copies preserve their original positions (0, 1, 2 within the new parent).
4. GIVEN a Part `P` at position 2 among siblings WHEN deep duplicated THEN the copy is at position 3, and the former sibling at position 3 is now at position 4.
5. GIVEN any deep duplicate operation THEN all newly created node `node_id` values are UUID4 strings distinct from the originals.

**Definition of Done:**
- `duplicate_deep` method unchanged from committed version
- All 5 acceptance criteria pass against the existing implementation
- Integration test `T-DUP-01` (or equivalent) verifies full subtree

---

## Non-Functional Requirements

### Requirement 3: Authentication and Scope Enforcement

**User Story:** As a system administrator, I want the duplicate endpoint to require `tree:writer` scope, so that readers cannot create copies.

**Maps to:** `Security(get_current_active_user_account, scopes=["tree:writer"])` (CONSTITUTION II.2)

#### Acceptance Criteria

1. GIVEN no `Authorization` header WHEN `POST /nodes/{node_id}/duplicate` is called THEN the server returns HTTP 401.
2. GIVEN a token with only `tree:reader` scope WHEN `POST /nodes/{node_id}/duplicate` is called THEN the server returns HTTP 403.
3. GIVEN a blacklisted token WHEN `POST /nodes/{node_id}/duplicate` is called THEN the server returns HTTP 401.

---

### Requirement 4: Account Isolation

**User Story:** As a user, I want duplication to be account-isolated so that I cannot copy another user's nodes.

**Maps to:** `get_node` and all `NodeStorage` methods filter by `account_id` (CONSTITUTION I.4)

#### Acceptance Criteria

1. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `POST /nodes/{N.node_id}/duplicate` THEN the server returns HTTP 404 (not 403).
2. GIVEN a deep duplicate, all copied nodes MUST have `account_id` equal to the authenticated user's `account_id`. (Enforced by `duplicate_deep` copying `node["account_id"]` from the source.)

---

### Requirement 5: Beat Guard Enforcement

**User Story:** As a system, I want Beat nodes to be rejected before any write occurs, so that the terminal-leaf constraint is enforced at the API boundary.

**Maps to:** API-layer Beat check (before DB call) and DB-layer Beat guard (CONSTITUTION I.5, DESIGN Part X OD-02)

#### Acceptance Criteria

1. GIVEN a Beat node `B` WHEN `POST /nodes/{B.node_id}/duplicate` is called THEN the server returns HTTP 400 with `detail: "Beat nodes cannot be duplicated"` and NO document is written to `node_collection`.
2. GIVEN a Beat node `B` WHEN `POST /nodes/{B.node_id}/duplicate?deep=true` is called THEN the server returns HTTP 400 with `detail: "Beat nodes cannot be duplicated"` and NO document is written to `node_collection`.
3. GIVEN the API handler returns HTTP 400 for a Beat THEN the DB method `duplicate_shallow` or `duplicate_deep` MUST NOT have been called (the check in the API handler precedes the DB call).

---

### Requirement 6: Error Message Format

**User Story:** As an API consumer, I want duplicate errors to use sanitised messages.

**Maps to:** CONSTITUTION II.5, III.6

#### Acceptance Criteria

1. GIVEN a 404 from the duplicate endpoint THEN `detail` is exactly `"Node not found"`.
2. GIVEN a 400 from the duplicate endpoint THEN `detail` is exactly `"Beat nodes cannot be duplicated"`.
3. GIVEN a database failure WHEN `POST /nodes/{node_id}/duplicate` is called THEN HTTP 503 with `detail: "Database error"`.

---

## Correctness Properties

### Property 1: All Copies Have Fresh UUID4 node_ids

- **Description:** Every document inserted by `duplicate_shallow` or `duplicate_deep` MUST have `node_id = str(uuid.uuid4())`. The original `node_id` MUST NOT appear in any copy. (CONSTITUTION IV.4)
- **Testable:** Collect all `node_id` values returned by a deep duplicate. Assert none match the original source's `node_id` or any original child's `node_id`.

### Property 2: Copy is Inserted at original.position + 1

- **Description:** The shallow/deep root copy MUST be placed at `original.position + 1`. Siblings previously at positions `> original.position` MUST be incremented by 1. (CONSTITUTION IV.5)
- **Testable:** Record sibling positions before duplicate. Assert copy is at `original.position + 1`. Assert all former successors are incremented by exactly 1.

### Property 3: Root Copy Tag Ends with " (copy)"

- **Description:** The root copy's `tag` MUST be `f"{source.tag} (copy)"`. Child copies in a deep duplicate MUST NOT have `" (copy)"` appended (they keep original tags). (DESIGN OD-02)
- **Testable:** After shallow duplicate, assert `result["tag"] == f"{source_tag} (copy)"`. After deep duplicate on a Part with Chapter children, assert child copies have `tag == original_child_tag` (no " (copy)").

### Property 4: Beat Nodes Cannot Be Duplicated

- **Description:** The API MUST return HTTP 400 for Beat nodes before calling any DB method. No document MUST be inserted into `node_collection` when the source is a Beat. (CONSTITUTION I.5, DESIGN OD-02)
- **Testable:** Count documents in `node_collection` before and after a Beat duplicate attempt. Assert the count is unchanged. Assert HTTP 400 was returned.
