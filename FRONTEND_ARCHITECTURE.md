# Fabulator — Frontend Architecture
## React Web App (v1) → React Native (v2)
### Millie Kovacs, March 2026

---

## Overview

A React single-page application consuming the Fabulator FastAPI backend. Primary interaction is narrative tree navigation and node annotation — not text editing. iOS (React Native) is a post-web roadmap item; component architecture must anticipate this from day one.

---

## Known Risks & Failure Modes

Address these before writing a line of code.

### Critical

| Risk | Detail | Mitigation |
|------|--------|------------|
| D3 + React DOM conflict | D3 mutates the DOM directly; React owns the DOM. They will fight. | Give D3 a single `useRef` container and keep React out of it entirely. Never let React re-render inside the D3 SVG. |
| JWT token expiry UX | Tokens expire after 30 mins (per `.env`). Silent expiry mid-session is jarring. | Intercept 401 responses globally in an Axios/fetch wrapper. Redirect to login with a clear message. |
| Tree size performance | Large narrative trees (200+ nodes) will bog down D3 on re-render. | Implement collapse-by-default. Only render visible subtree. Virtualise if needed. |
| Redis token blacklist on logout | Logout blacklists the token server-side. Client must also clear local storage or the user appears logged in. | Clear token from state AND localStorage on logout. |
| CORS in dev | API runs on port 8000, React dev server on 3000. Will hit CORS immediately. | Proxy via Vite config in dev. Ensure `CORS_ORIGINS` env var is set correctly in FastAPI for prod. Note: current API has a known critical CORS issue (all methods/headers allowed with credentials — see `CODEBASE_ASSESSMENT.md`). |
| React Native D3 incompatibility | D3 uses browser SVG APIs unavailable in React Native. | Isolate all D3 code behind a `TreeVisualiser` component with a clean props interface. For React Native, swap this component for `react-native-svg` + a lightweight tree layout — the rest of the app is unaffected. |

### Medium Priority

| Risk | Detail | Mitigation |
|------|--------|------------|
| Auth scope granularity | API uses fine-grained scopes (`tree:reader`, `tree:writer` etc). UI must reflect what the user can actually do. | Build a `usePermissions()` hook that reads scopes from the decoded JWT and gates UI actions accordingly. |
| Node update race conditions | User edits node detail, clicks another node before save completes. | Debounce saves. Show dirty state indicator. Warn on navigation if unsaved. |
| `passlib` crypt deprecation | Will break on Python 3.13 (known, flagged in test run). | Not a frontend issue but will break auth. Add to backend backlog. |

---

## Tech Stack

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Framework | React 18 | React Native compatibility |
| Build tool | Vite | Fast HMR, simple config, no CRA baggage |
| Tree visualisation | D3 v7 | Actively maintained, collapsible tree well-documented |
| State management | Zustand | Lightweight, no boilerplate, works in RN |
| Routing | React Router v6 | Standard, RN equivalent exists (`react-navigation`) |
| HTTP client | Axios | Interceptors for 401 handling, cleaner than fetch |
| Styling | CSS Modules | Scoped styles, no runtime overhead, RN uses StyleSheet anyway |
| Auth | JWT in memory + httpOnly cookie | Security: avoid localStorage for tokens |

**Deliberately excluded:**
- Redux — overkill for a single-user app
- React Query — adds complexity; Zustand + Axios is sufficient here
- Styled Components / Tailwind — CSS Modules keeps the RN migration simpler

---

## Component Architecture

```
src/
├── main.jsx                    # Entry point
├── App.jsx                     # Router, auth guard
│
├── api/
│   ├── client.js               # Axios instance, base URL, interceptors
│   ├── auth.js                 # login(), logout(), getToken()
│   ├── nodes.js                # getNodes(), createNode(), updateNode(), deleteNode()
│   ├── trees.js                # getRoot(), getSubtree(), graftSubtree()
│   └── saves.js                # listSaves(), loadSave(), deleteSaves()
│
├── store/
│   ├── authStore.js            # JWT token, user, scopes
│   ├── treeStore.js            # Current tree, selected node, dirty state
│   └── undoStore.js            # Command pattern undo stack (50 ops max)
│
├── hooks/
│   ├── usePermissions.js       # Derives allowed actions from JWT scopes
│   ├── useTree.js              # Fetches + transforms tree data for D3
│   ├── useNodeDetail.js        # Selected node CRUD operations
│   ├── useAutoSave.js          # Debounced save (2-3s), dirty state management
│   └── useUndoStack.js         # Command pattern, 50 op limit
│
├── pages/
│   ├── LoginPage.jsx           # Auth form
│   └── WorkspacePage.jsx       # Main app shell
│
└── components/
    ├── layout/
    │   ├── AppShell.jsx        # Top nav, layout grid
    │   └── Toolbar.jsx         # Collapse all, reset view, save controls
    │
    ├── tree/
    │   ├── TreeVisualiser.jsx  # D3 boundary component — owns the SVG ref
    │   ├── useD3Tree.js        # D3 logic hook (update, collapse, zoom)
    │   └── TreeControls.jsx    # Zoom in/out, reset, collapse all
    │
    ├── node/
    │   ├── NodeDetailPanel.jsx # Right panel shell
    │   ├── NodeHeader.jsx      # Name, ID, depth, dirty indicator dot
    │   ├── NodeFields.jsx      # Description, text (textarea 3-4 rows), previous/next
    │   ├── NodePicker.jsx      # Search/select node for previous/next links
    │   ├── NodeTags.jsx        # Tag display + edit
    │   └── NodeActions.jsx     # Add child, delete, duplicate (gated by permissions)
    │
    └── common/
        ├── AuthGuard.jsx       # Redirects to login if no token
        ├── LoadingSpinner.jsx
        └── ErrorBoundary.jsx
```

---

## Data Flow

```
FastAPI (port 8000)
    ↓  Axios (with JWT header)
api/ layer  (pure async functions, no React)
    ↓
Zustand stores  (treeStore, authStore)
    ↓
Custom hooks  (useTree, usePermissions, useNodeDetail)
    ↓
Page components  (WorkspacePage)
    ↓
TreeVisualiser ←→ NodeDetailPanel
(D3 owns SVG)      (React owns panel)
```

**Key principle:** D3 and React never share DOM territory. `TreeVisualiser` is the hard boundary. Everything inside the SVG ref is D3's. Everything outside is React's.

---

## Authentication Flow

```
1. LoginPage → POST /get_token → JWT stored in memory (authStore)
2. Axios interceptor attaches JWT to every request header
3. On 401 → clear store → redirect to LoginPage with message
4. On logout → GET /logout (blacklists token server-side) → clear store
5. Page refresh loses token (memory) → redirect to login
```

**Note on token storage:** Storing JWT in memory (not localStorage) is more secure but means refresh = re-login. This is acceptable for a solo writing tool. If it becomes annoying, consider httpOnly cookie auth — but that requires FastAPI changes.

---

## React → React Native Migration Path

The following components are **web-only** and need RN equivalents:

| Web component | RN replacement |
|---------------|----------------|
| `TreeVisualiser.jsx` (D3 SVG) | `TreeVisualiserNative.jsx` (`react-native-svg` + custom layout) |
| CSS Modules | React Native `StyleSheet` |
| React Router | React Navigation |
| Browser `localStorage` | `AsyncStorage` |

Everything else — stores, hooks, api layer, business logic — is portable with zero or minimal changes. This is why the D3 isolation boundary matters so much.

---

## Todo List

### Phase 1 — Foundation
- [ ] Scaffold Vite + React project in `/client` directory
- [ ] Configure Vite proxy for `/api` → `http://localhost:8000` in dev
- [ ] Set up Axios client with JWT interceptor and 401 handler
- [ ] Implement `authStore` (Zustand) — token, user, scopes
- [ ] Build `LoginPage` — POST `/get_token`, store JWT, redirect
- [ ] Build `AuthGuard` — protect all routes
- [ ] Add `ErrorBoundary` at app root

### Phase 2 — Tree Visualisation
- [ ] Implement `useTree` hook — fetch nodes, transform to D3 hierarchy
- [ ] Build `TreeVisualiser` with D3 collapsible tree (from mockup spike)
- [ ] Implement collapse/expand, zoom, pan
- [ ] Wire node click → `treeStore.selectedNode`
- [ ] Add `TreeControls` (collapse all, reset view)

### Phase 3 — Node Detail
- [ ] Build `NodeDetailPanel` — reads from `treeStore.selectedNode`
- [ ] Implement `useNodeDetail` — PUT `/nodes/{id}` on field change (debounced)
- [ ] Build `NodeTags` — add/remove tags
- [ ] Build `usePermissions` — gate `NodeActions` by JWT scopes
- [ ] Add child node creation — POST `/nodes/{name}` with parent
- [ ] Add node deletion with confirmation

### Phase 4 — Saves
- [ ] List saves panel — GET `/saves`
- [ ] Load save — GET `/loads/{save_id}`
- [ ] Delete all saves with confirmation

### Phase 5 — Polish & Hardening
- [ ] Dirty state indicator + unsaved changes warning
- [ ] Loading states throughout
- [ ] Error messages (API down, 403, 404)
- [ ] Add `pytest` equivalent — Vitest + React Testing Library
- [ ] Dockerfile for client container
- [ ] Add `fabulator-client` service to `docker-compose.yml`

---

## Out of Scope (v1)

The following are in the API roadmap but not the v1 frontend:

- Full-text node search
- Node duplication
- Sibling/ancestor navigation endpoints (API not yet built)
- Export (PDF, Markdown, DOCX)
- Character tracking
- Multi-user / tree sharing

---

## Design Decisions (resolved)

| Question | Decision |
|----------|----------|
| **Node text field** | Synopsis/treatment — writer's shorthand for the scene ("Elara walks into the lighthouse. The door is already open."). Prominent inline textarea, 3-4 rows, not a full editor. |
| **Previous/next links** | Manually set by the writer — narrative order can differ from tree position. Needs a node picker (search/select) not free text. A story branch may loop back or skip forward. |
| **Save UX** | Auto-save on debounce (2-3s after last keystroke). Dirty indicator while unsaved — subtle dot on tree node + toolbar status. Client-side undo stack (command pattern, 50 operations deep). **Note:** API has no revision history endpoint (Tier 5 roadmap) — undo is entirely a frontend concern for v1. |

---

*Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>*
