# Feature Specification: Node Navigation

**Implementation status:** COMPLETE — all 7 navigation endpoints and all `NodeStorage` navigation methods are committed on branch `refactor/normalised-node-model`. This document is authoritative for verification, test authoring, and corrective changes.

**Files in scope:**
- `server/app/database.py` — `NodeStorage` methods: `get_children` (line 710), `get_parent` (line 725), `get_ancestors` (line 740), `get_siblings` (line 770), `get_roots` (line 792), `get_leaves` (line 807), `get_stats` (line 826)
- `server/app/api.py` — 7 navigation route handlers (lines 530–765)
- `server/app/models.py` — `NodeResponse`, `AncestorsResponse`, `WorkStatsResponse`

---

## Introduction

Node Navigation endpoints expose the parent-child and sibling relationships stored in the adjacency-list model (`parent_id` pointers). They are read-only, require `tree:reader` scope, and delegate entirely to the already-implemented `NodeStorage` methods. These endpoints are the second Tier-2 priority after core CRUD and are required before any frontend tree visualisation can be built. (CONSTITUTION Part X, Tier 2)

The 7 endpoints to implement are:
1. `GET /nodes/{node_id}/children` — direct children, ordered by `position`
2. `GET /nodes/{node_id}/parent` — single parent node (null for Part roots)
3. `GET /nodes/{node_id}/ancestors` — root-to-parent chain
4. `GET /nodes/{node_id}/siblings` — nodes sharing same `parent_id`, excluding self
5. `GET /works/{work_id}/nodes/root` — all Part nodes for a Work
6. `GET /works/{work_id}/nodes/leaves` — all Beat nodes for a Work
7. `GET /works/{work_id}/stats` — type counts and max depth for a Work

---

## Glossary

| Term | Definition |
|------|-----------|
| **children** | Nodes whose `parent_id` equals the given `node_id`. Ordered by `position` ascending. |
| **parent** | The node whose `node_id` equals the given node's `parent_id`. `null` for Part (root) nodes. |
| **ancestors** | The ordered chain from the root Part down to the immediate parent of the given node. Returns `[]` for Part nodes (which have no ancestors). Ordered root-first (index 0 = root). |
| **siblings** | Nodes sharing the same `parent_id` as the given node, excluding the given node itself. Ordered by `position` ascending. |
| **root nodes** | All Part nodes (`node_type == "part"`, `parent_id == null`) for a given Work. Ordered by `position` ascending. |
| **leaf nodes** | All Beat nodes (`node_type == "beat"`) for a given Work. Ordered by `position` ascending. |
| **stats** | Aggregate counts of nodes by type plus the maximum depth of the hierarchy. See `WorkStatsResponse`. |
| **AncestorsResponse** | Pydantic model in models.py: `{"ancestors": [NodeResponse, ...]}`. Wraps the list returned by `get_ancestors`. |
| **WorkStatsResponse** | Pydantic model: `{"work_id": str, "total_nodes": int, "by_type": {"part": int, "chapter": int, "scene": int, "beat": int}, "max_depth": int}`. |
| **max_depth** | BFS from all root nodes. Root nodes are at depth 0. Their children at depth 1, etc. Returns the maximum depth reached. |

---

## Functional Requirements

### Requirement 1: Get Children

**User Story:** As an authenticated reader, I want to retrieve the direct children of a node, so that I can navigate down the hierarchy one level.

**Maps to:** `NodeStorage.get_children(node_id, account_id) -> list[dict]` (database.py:1005). (CONSTITUTION Part X Tier 2)

**Task ordering:** This is Task 1. No dependencies on other tasks in this spec.

**Exact endpoint to ADD to api.py:**
```
Method:         GET
Path:           /nodes/{node_id}/children
Path params:    node_id — UUID4 pattern via Path(pattern=UUID_PATTERN)
Response body:  list[NodeResponse]
Status on success: 200
Required scope: tree:reader
OpenAPI tags:   ["Nodes"]
```

**Exact function signature to insert:**
```python
@app.get(
    "/nodes/{node_id}/children",
    response_model=list[NodeResponse],
    summary="Get children of a node",
    description=(
        "Return the direct children of the specified node, ordered by position ascending. "
        "Returns an empty list if the node has no children. "
        "Returns 404 if the node does not exist or belongs to a different account."
    ),
    tags=["Nodes"],
)
async def get_node_children(
    node_id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> list[dict]:
    logger.debug(f"get_node_children({node_id}) called")
    try:
        node = await node_storage.get_node(node_id=node_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error in get_node_children for {node_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    try:
        children = await node_storage.get_children(node_id=node_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error fetching children of {node_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    return children
```

**Insertion point in api.py:** Insert ABOVE the existing `get_normalised_node` function (currently at line 466). FastAPI resolves longer paths first, but placing more specific routes earlier is the conventional pattern.

**What MUST NOT be changed:** `get_normalised_node`, `NodeStorage.get_children`.

#### Acceptance Criteria

1. GIVEN a valid JWT with `tree:reader` scope and a Part node `P` with 2 Chapter children WHEN `GET /nodes/{P.node_id}/children` is called THEN the server returns HTTP 200 with a list of 2 `NodeResponse` objects ordered by `position` ascending.
2. GIVEN a valid JWT and a Beat node (leaf, no children) WHEN `GET /nodes/{beat_id}/children` is called THEN the server returns HTTP 200 with an empty list `[]`.
3. GIVEN a valid JWT WHEN `GET /nodes/{node_id}/children` is called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.
4. GIVEN a valid JWT WHEN `GET /nodes/{node_id}/children` is called with a `node_id` that is not UUID4 format THEN the server returns HTTP 422.
5. GIVEN no Authorization header WHEN `GET /nodes/{node_id}/children` is called THEN the server returns HTTP 401.
6. GIVEN a valid JWT with only `tree:writer` scope (and not `tree:reader`) WHEN `GET /nodes/{node_id}/children` is called THEN the server returns HTTP 403. (Note: standard token scopes include both; test with a token that explicitly lacks `tree:reader`.)
7. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `GET /nodes/{N.node_id}/children` THEN the server returns HTTP 404.

**Definition of Done:**
- Function `get_node_children` exists in api.py
- `response_model=list[NodeResponse]` declared
- `summary`, `description`, `tags=["Nodes"]` declared
- 200 with ordered list for valid node
- Empty list for leaf nodes
- 404 for missing or cross-account node

---

### Requirement 2: Get Parent

**User Story:** As an authenticated reader, I want to retrieve the parent of a node, so that I can navigate up the hierarchy.

**Maps to:** `NodeStorage.get_parent(node_id, account_id) -> dict | None` (database.py:1020). (CONSTITUTION Part X Tier 2)

**Task ordering:** Task 2. No dependency on Task 1.

**Exact endpoint to ADD to api.py:**
```
Method:         GET
Path:           /nodes/{node_id}/parent
Path params:    node_id — UUID4 pattern
Response body:  NodeResponse or null
Status on success: 200
Required scope: tree:reader
OpenAPI tags:   ["Nodes"]
```

**Exact function signature to insert:**
```python
@app.get(
    "/nodes/{node_id}/parent",
    response_model=Optional[NodeResponse],
    summary="Get parent of a node",
    description=(
        "Return the parent node of the specified node. "
        "Returns null if the node is a root Part (no parent). "
        "Returns 404 if the node does not exist or belongs to a different account."
    ),
    tags=["Nodes"],
)
async def get_node_parent(
    node_id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> dict | None:
    logger.debug(f"get_node_parent({node_id}) called")
    try:
        node = await node_storage.get_node(node_id=node_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error checking node existence in get_node_parent for {node_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    try:
        parent = await node_storage.get_parent(node_id=node_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error fetching parent of {node_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    return parent
```

**Import note:** `Optional` is already imported in api.py (`from typing import Optional`). Verify this before inserting.

**What `get_parent` returns:** the parent node dict, or `None` if the node has `parent_id == null` (i.e. it is a Part root). When the handler returns `None`, FastAPI serializes it as JSON `null`.

**What MUST NOT be changed:** `get_normalised_node`, `NodeStorage.get_parent`.

#### Acceptance Criteria

1. GIVEN a valid JWT and a Chapter node `C` with parent Part `P` WHEN `GET /nodes/{C.node_id}/parent` is called THEN the server returns HTTP 200 with the `NodeResponse` for `P`.
2. GIVEN a valid JWT and a Part node (root, `parent_id == null`) WHEN `GET /nodes/{part_id}/parent` is called THEN the server returns HTTP 200 with a JSON body of `null`.
3. GIVEN a valid JWT WHEN `GET /nodes/{node_id}/parent` is called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.
4. GIVEN no Authorization header WHEN `GET /nodes/{node_id}/parent` is called THEN the server returns HTTP 401.
5. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `GET /nodes/{N.node_id}/parent` THEN the server returns HTTP 404.

**Definition of Done:**
- Function `get_node_parent` exists in api.py
- `response_model=Optional[NodeResponse]` declared
- Returns NodeResponse for non-root nodes
- Returns null (HTTP 200 with null body) for Part root nodes
- Returns 404 for missing/cross-account node

---

### Requirement 3: Get Ancestors

**User Story:** As an authenticated reader, I want to retrieve the full ancestor chain of a node from root to parent, so that I can display breadcrumb navigation.

**Maps to:** `NodeStorage.get_ancestors(node_id, account_id) -> list[dict]` (database.py:1035). (CONSTITUTION Part X Tier 2)

**Task ordering:** Task 3. No dependency on previous tasks.

**Exact endpoint to ADD to api.py:**
```
Method:         GET
Path:           /nodes/{node_id}/ancestors
Path params:    node_id — UUID4 pattern
Response body:  AncestorsResponse
Status on success: 200
Required scope: tree:reader
OpenAPI tags:   ["Nodes"]
```

**What `get_ancestors` returns:** `list[dict]` ordered from root to immediate parent (index 0 = root/Part, last index = immediate parent). Returns `[]` for Part nodes (no ancestors).

**AncestorsResponse model (already in models.py — do not add):**
```python
class AncestorsResponse(BaseModel):
    ancestors: list[NodeResponse]
```

**Exact function signature to insert:**
```python
@app.get(
    "/nodes/{node_id}/ancestors",
    response_model=AncestorsResponse,
    summary="Get ancestors of a node",
    description=(
        "Return the ancestor chain from the root Part down to the immediate parent of the "
        "specified node. The list is ordered root-first (index 0 = root Part). "
        "Returns an empty ancestors list for Part nodes (which have no ancestors). "
        "Returns 404 if the node does not exist or belongs to a different account."
    ),
    tags=["Nodes"],
)
async def get_node_ancestors(
    node_id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> dict:
    logger.debug(f"get_node_ancestors({node_id}) called")
    try:
        node = await node_storage.get_node(node_id=node_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error checking node in get_node_ancestors for {node_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    try:
        ancestors = await node_storage.get_ancestors(node_id=node_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error fetching ancestors of {node_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    return {"ancestors": ancestors}
```

**What MUST NOT be changed:** `get_normalised_node`, `NodeStorage.get_ancestors`, `AncestorsResponse`.

#### Acceptance Criteria

1. GIVEN a valid JWT and a Beat node `B` with ancestors Part `P` → Chapter `C` → Scene `S` WHEN `GET /nodes/{B.node_id}/ancestors` is called THEN the server returns HTTP 200 with `{"ancestors": [P, C, S]}` (root-first order, B's immediate parent last).
2. GIVEN a valid JWT and a Part node (root) WHEN `GET /nodes/{part_id}/ancestors` is called THEN the server returns HTTP 200 with `{"ancestors": []}`.
3. GIVEN a valid JWT and a Chapter node `C` with parent Part `P` WHEN `GET /nodes/{C.node_id}/ancestors` is called THEN the server returns HTTP 200 with `{"ancestors": [P]}`.
4. GIVEN a valid JWT WHEN `GET /nodes/{node_id}/ancestors` is called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.
5. GIVEN no Authorization header WHEN `GET /nodes/{node_id}/ancestors` is called THEN the server returns HTTP 401.

**Definition of Done:**
- Function `get_node_ancestors` exists in api.py
- `response_model=AncestorsResponse` declared
- Returns `{"ancestors": [...]}` with root-first ordering
- Returns `{"ancestors": []}` for Part nodes
- 404 for missing/cross-account node

---

### Requirement 4: Get Siblings

**User Story:** As an authenticated reader, I want to retrieve the siblings of a node (nodes sharing the same parent), so that I can navigate the hierarchy laterally.

**Maps to:** `NodeStorage.get_siblings(node_id, account_id) -> list[dict]` (database.py:1065). (CONSTITUTION Part X Tier 2)

**Task ordering:** Task 4. No dependency on previous tasks.

**Exact endpoint to ADD to api.py:**
```
Method:         GET
Path:           /nodes/{node_id}/siblings
Path params:    node_id — UUID4 pattern
Response body:  list[NodeResponse]
Status on success: 200
Required scope: tree:reader
OpenAPI tags:   ["Nodes"]
```

**What `get_siblings` returns:** List of nodes sharing the same `parent_id` as the given node, excluding the node itself. Ordered by `position` ascending. Returns `[]` if the node is the only child (no siblings).

**Exact function signature to insert:**
```python
@app.get(
    "/nodes/{node_id}/siblings",
    response_model=list[NodeResponse],
    summary="Get siblings of a node",
    description=(
        "Return nodes that share the same parent as the specified node, excluding the node itself. "
        "Results are ordered by position ascending. "
        "Returns an empty list if the node has no siblings. "
        "Returns 404 if the node does not exist or belongs to a different account."
    ),
    tags=["Nodes"],
)
async def get_node_siblings(
    node_id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> list[dict]:
    logger.debug(f"get_node_siblings({node_id}) called")
    try:
        node = await node_storage.get_node(node_id=node_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error checking node in get_node_siblings for {node_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    try:
        siblings = await node_storage.get_siblings(node_id=node_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error fetching siblings of {node_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    return siblings
```

**What MUST NOT be changed:** `NodeStorage.get_siblings`.

#### Acceptance Criteria

1. GIVEN a valid JWT and 3 Chapter nodes under Part `P` at positions 0, 1, 2 WHEN `GET /nodes/{chapter1_id}/siblings` is called THEN the server returns HTTP 200 with the other 2 Chapter nodes ordered by `position` ascending (chapter1 itself is excluded).
2. GIVEN a valid JWT and a Chapter node `C` that is the only child of its parent WHEN `GET /nodes/{C.node_id}/siblings` is called THEN the server returns HTTP 200 with an empty list `[]`.
3. GIVEN a valid JWT WHEN `GET /nodes/{node_id}/siblings` is called with a non-existent or cross-account `node_id` THEN the server returns HTTP 404 with `detail: "Node not found"`.
4. GIVEN no Authorization header WHEN `GET /nodes/{node_id}/siblings` is called THEN the server returns HTTP 401.
5. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `GET /nodes/{N.node_id}/siblings` THEN the server returns HTTP 404.

**Definition of Done:**
- Function `get_node_siblings` exists in api.py
- Self excluded from result (verified via `"node_id": {"$ne": node_id}` in `get_siblings`)
- Ordered by `position` ascending
- Empty list for sole child
- 404 for missing/cross-account node

---

### Requirement 5: Get Root Nodes

**User Story:** As an authenticated reader, I want to retrieve all root (Part) nodes for a Work, so that I can render the top level of the hierarchy.

**Maps to:** `NodeStorage.get_roots(work_id, account_id) -> list[dict]` (database.py:1087). (CONSTITUTION Part X Tier 2)

**Task ordering:** Task 5. No dependency on previous tasks.

**ROUTING WARNING:** The path `/works/{work_id}/nodes/root` must be registered BEFORE the path `/works/{work_id}/nodes` in api.py. If they share a prefix and FastAPI resolves them in order, the more-specific 4-segment path would normally take precedence. However, since `root` is a literal path segment (not a parameter), and `/works/{work_id}/nodes` has 3 segments vs `/works/{work_id}/nodes/root` has 4, FastAPI will correctly prefer the longer match. Still, define this function ABOVE `list_normalised_nodes` in api.py as a safety measure.

**Exact endpoint to ADD to api.py:**
```
Method:         GET
Path:           /works/{work_id}/nodes/root
Path params:    work_id — UUID4 pattern
Response body:  list[NodeResponse]
Status on success: 200
Required scope: tree:reader
OpenAPI tags:   ["Nodes"]
```

**Exact function signature to insert:**
```python
@app.get(
    "/works/{work_id}/nodes/root",
    response_model=list[NodeResponse],
    summary="Get root nodes for a work",
    description=(
        "Return all Part (root) nodes for the specified Work, ordered by position ascending. "
        "A Work may have multiple root Part nodes. "
        "Returns 404 if the Work does not exist or belongs to a different account."
    ),
    tags=["Nodes"],
)
async def get_work_root_nodes(
    work_id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    work_storage: WorkStorage = Depends(get_work_storage),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> list[dict]:
    logger.debug(f"get_work_root_nodes({work_id}) called")
    try:
        work = await work_storage.get_work(work_id=work_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error fetching work in get_work_root_nodes for {work_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    try:
        roots = await node_storage.get_roots(work_id=work_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error fetching roots for work {work_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    return roots
```

**What MUST NOT be changed:** `NodeStorage.get_roots`, `list_normalised_nodes`.

#### Acceptance Criteria

1. GIVEN a valid JWT and a Work with 2 Part nodes at positions 0 and 1 WHEN `GET /works/{work_id}/nodes/root` is called THEN the server returns HTTP 200 with the 2 Part nodes ordered by `position` ascending.
2. GIVEN a valid JWT and a Work with no nodes WHEN `GET /works/{work_id}/nodes/root` is called THEN the server returns HTTP 200 with an empty list `[]`.
3. GIVEN a valid JWT WHEN `GET /works/{work_id}/nodes/root` is called with a non-existent or cross-account `work_id` THEN the server returns HTTP 404 with `detail: "Work not found"`.
4. GIVEN no Authorization header WHEN `GET /works/{work_id}/nodes/root` is called THEN the server returns HTTP 401.
5. GIVEN User A has Work W and User B is authenticated WHEN User B calls `GET /works/{W.work_id}/nodes/root` THEN the server returns HTTP 404.

**Definition of Done:**
- Function `get_work_root_nodes` exists in api.py
- Registered before `list_normalised_nodes` in the file
- Work ownership check performed before fetching roots
- Returns only Part nodes (enforced by `get_roots` query `{parent_id: None}`)

---

### Requirement 6: Get Leaf Nodes

**User Story:** As an authenticated reader, I want to retrieve all leaf (Beat) nodes for a Work, so that I can find story endpoints.

**Maps to:** `NodeStorage.get_leaves(work_id, account_id) -> list[dict]` (database.py:1102). (CONSTITUTION Part X Tier 2)

**Task ordering:** Task 6. No dependency on previous tasks.

**Exact endpoint to ADD to api.py:**
```
Method:         GET
Path:           /works/{work_id}/nodes/leaves
Path params:    work_id — UUID4 pattern
Response body:  list[NodeResponse]
Status on success: 200
Required scope: tree:reader
OpenAPI tags:   ["Nodes"]
```

**Exact function signature to insert:**
```python
@app.get(
    "/works/{work_id}/nodes/leaves",
    response_model=list[NodeResponse],
    summary="Get leaf nodes for a work",
    description=(
        "Return all Beat (leaf) nodes for the specified Work, ordered by position ascending. "
        "Beats are the terminal narrative units and have no children. "
        "Returns 404 if the Work does not exist or belongs to a different account."
    ),
    tags=["Nodes"],
)
async def get_work_leaf_nodes(
    work_id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    work_storage: WorkStorage = Depends(get_work_storage),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> list[dict]:
    logger.debug(f"get_work_leaf_nodes({work_id}) called")
    try:
        work = await work_storage.get_work(work_id=work_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error fetching work in get_work_leaf_nodes for {work_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    try:
        leaves = await node_storage.get_leaves(work_id=work_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error fetching leaves for work {work_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    return leaves
```

**What MUST NOT be changed:** `NodeStorage.get_leaves`.

#### Acceptance Criteria

1. GIVEN a valid JWT and a Work with 3 Beat nodes WHEN `GET /works/{work_id}/nodes/leaves` is called THEN the server returns HTTP 200 with the 3 Beat nodes ordered by `position` ascending.
2. GIVEN a valid JWT and a Work with no Beat nodes WHEN `GET /works/{work_id}/nodes/leaves` is called THEN the server returns HTTP 200 with an empty list `[]`.
3. GIVEN a valid JWT WHEN `GET /works/{work_id}/nodes/leaves` is called with a non-existent or cross-account `work_id` THEN the server returns HTTP 404 with `detail: "Work not found"`.
4. GIVEN no Authorization header WHEN `GET /works/{work_id}/nodes/leaves` is called THEN the server returns HTTP 401.

**Definition of Done:**
- Function `get_work_leaf_nodes` exists in api.py
- Returns only Beat nodes (enforced by `get_leaves` query `{node_type: "beat"}`)
- Work ownership check performed before fetching leaves

---

### Requirement 7: Get Work Statistics

**User Story:** As an authenticated reader, I want to see aggregate statistics for a Work (node counts by type and maximum depth), so that I can understand the scale of my narrative.

**Maps to:** `NodeStorage.get_stats(work_id, account_id) -> dict` (database.py:1121). (CONSTITUTION Part X Tier 2)

**Task ordering:** Task 7. No dependency on previous tasks.

**Exact endpoint to ADD to api.py:**
```
Method:         GET
Path:           /works/{work_id}/stats
Path params:    work_id — UUID4 pattern
Response body:  WorkStatsResponse
Status on success: 200
Required scope: tree:reader
OpenAPI tags:   ["Works"]
```

**WorkStatsResponse model (already in models.py — do not add):**
```python
class WorkStatsResponse(BaseModel):
    work_id: str
    total_nodes: int
    by_type: dict[str, int]   # keys: "part", "chapter", "scene", "beat"
    max_depth: int
```

**Exact function signature to insert:**
```python
@app.get(
    "/works/{work_id}/stats",
    response_model=WorkStatsResponse,
    summary="Get statistics for a work",
    description=(
        "Return aggregate statistics for the specified Work: total node count, "
        "counts by node type (part/chapter/scene/beat), and the maximum hierarchy depth. "
        "Depth is 0-indexed at root Part nodes. "
        "Returns 404 if the Work does not exist or belongs to a different account."
    ),
    tags=["Works"],
)
async def get_work_stats(
    work_id: str = Path(..., pattern=UUID_PATTERN),
    account_id: str = Security(get_current_active_user_account, scopes=["tree:reader"]),
    work_storage: WorkStorage = Depends(get_work_storage),
    node_storage: NodeStorage = Depends(get_node_storage),
) -> dict:
    logger.debug(f"get_work_stats({work_id}) called")
    try:
        work = await work_storage.get_work(work_id=work_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error fetching work in get_work_stats for {work_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    if work is None:
        raise HTTPException(status_code=404, detail="Work not found")
    try:
        stats = await node_storage.get_stats(work_id=work_id, account_id=account_id)
    except (pymongo.errors.ConnectionFailure, pymongo.errors.OperationFailure):
        logger.error(f"Database error fetching stats for work {work_id}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database error")
    return stats
```

**What MUST NOT be changed:** `NodeStorage.get_stats`, `NodeStorage._calculate_max_depth`, `WorkStatsResponse`.

#### Acceptance Criteria

1. GIVEN a valid JWT and a Work with 1 Part, 2 Chapters, 2 Scenes, 2 Beats WHEN `GET /works/{work_id}/stats` is called THEN the server returns HTTP 200 with `{"work_id": "...", "total_nodes": 7, "by_type": {"part": 1, "chapter": 2, "scene": 2, "beat": 2}, "max_depth": 3}`.
2. GIVEN a valid JWT and a Work with no nodes WHEN `GET /works/{work_id}/stats` is called THEN the server returns HTTP 200 with `{"work_id": "...", "total_nodes": 0, "by_type": {"part": 0, "chapter": 0, "scene": 0, "beat": 0}, "max_depth": 0}`.
3. GIVEN a valid JWT WHEN `GET /works/{work_id}/stats` is called with a non-existent or cross-account `work_id` THEN the server returns HTTP 404 with `detail: "Work not found"`.
4. GIVEN no Authorization header WHEN `GET /works/{work_id}/stats` is called THEN the server returns HTTP 401.
5. GIVEN a Work with only a single Part node (depth 0) WHEN `GET /works/{work_id}/stats` is called THEN `max_depth` is 0.

**Definition of Done:**
- Function `get_work_stats` exists in api.py
- `response_model=WorkStatsResponse` declared
- Work ownership check performed before fetching stats
- `by_type` dict always contains all four keys even when count is 0
- `max_depth` is 0 for an empty or single-node Work

---

## Non-Functional Requirements

### Requirement 8: Authentication and Scope Enforcement

**User Story:** As a system administrator, I want all navigation endpoints to require `tree:reader` scope, so that unauthenticated clients cannot traverse node relationships.

**Maps to:** `Security(get_current_active_user_account, scopes=["tree:reader"])` on each handler (CONSTITUTION II.2)

#### Acceptance Criteria

1. GIVEN no `Authorization` header WHEN any navigation endpoint is called THEN the server returns HTTP 401.
2. GIVEN a token without `tree:reader` scope WHEN any navigation endpoint is called THEN the server returns HTTP 403.
3. GIVEN a blacklisted token WHEN any navigation endpoint is called THEN the server returns HTTP 401.

---

### Requirement 9: Account Isolation (404 not 403)

**User Story:** As a user, I want cross-account resource access to return 404, so that the existence of other users' data is not revealed.

**Maps to:** CONSTITUTION I.4 — all queries include `account_id` filter

#### Acceptance Criteria

1. GIVEN User A owns Node N and User B is authenticated WHEN User B calls `GET /nodes/{N.node_id}/children` THEN the server returns HTTP 404 (the parent node check fails with 404).
2. GIVEN User A has Work W and User B is authenticated WHEN User B calls `GET /works/{W.work_id}/nodes/root` THEN the server returns HTTP 404 (work ownership check fails first).
3. GIVEN User A has Work W and User B is authenticated WHEN User B calls `GET /works/{W.work_id}/stats` THEN the server returns HTTP 404.

---

### Requirement 10: Path Parameter Validation

**User Story:** As an API consumer, I want invalid path parameters to return 422 immediately, so that I receive fast feedback on malformed requests.

**Maps to:** `Path(..., pattern=UUID_PATTERN)` on all path parameters (CONSTITUTION II.4)

#### Acceptance Criteria

1. GIVEN `GET /nodes/not-a-uuid/children` is called THEN the server returns HTTP 422.
2. GIVEN `GET /works/not-a-uuid/nodes/root` is called THEN the server returns HTTP 422.
3. GIVEN `GET /works/not-a-uuid/stats` is called THEN the server returns HTTP 422.

---

### Requirement 11: Error Message Format

**User Story:** As an API consumer, I want navigation errors to use sanitised messages with no internal state.

**Maps to:** CONSTITUTION II.5, III.6

#### Acceptance Criteria

1. GIVEN a 404 from a node-scoped navigation endpoint THEN `detail` is exactly `"Node not found"`.
2. GIVEN a 404 from a work-scoped navigation endpoint THEN `detail` is exactly `"Work not found"`.
3. GIVEN a database failure WHEN any navigation endpoint is called THEN `detail` is exactly `"Database error"` with HTTP 503.

---

## Correctness Properties

### Property 1: Children Ordered by Position Ascending

- **Description:** `GET /nodes/{id}/children` MUST return children in `position` ascending order (0 first). This ordering is enforced by `sort=[("position", 1)]` in `NodeStorage.get_children`. (CONSTITUTION IV.5)
- **Testable:** Create 3 children under a node. Assert response list `position` values are `[0, 1, 2]`.

### Property 2: Ancestors Ordered Root-First

- **Description:** `GET /nodes/{id}/ancestors` MUST return the root Part at index 0 and the immediate parent at the last index. This is enforced by `ancestors.reverse()` in `NodeStorage.get_ancestors`. (DESIGN Part V context)
- **Testable:** For a Beat node at depth 3, assert ancestors list has 3 items, first is a Part, last is a Scene.

### Property 3: Self Excluded from Siblings

- **Description:** `GET /nodes/{id}/siblings` MUST NOT include the queried node itself. This is enforced by `"node_id": {"$ne": node_id}` in `NodeStorage.get_siblings`. (CONSTITUTION IV.5)
- **Testable:** Assert the queried `node_id` does not appear in the siblings response array.

### Property 4: Root Nodes are Always Parts

- **Description:** `GET /works/{id}/nodes/root` MUST only return nodes with `node_type == "part"` and `parent_id == null`. (CONSTITUTION I.5)
- **Testable:** Assert every item in the roots response has `node_type: "part"` and `parent_id: null`.

### Property 5: Leaf Nodes are Always Beats

- **Description:** `GET /works/{id}/nodes/leaves` MUST only return nodes with `node_type == "beat"`. (CONSTITUTION I.5)
- **Testable:** Assert every item in the leaves response has `node_type: "beat"`.
