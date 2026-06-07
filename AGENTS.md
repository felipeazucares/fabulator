## Phase 8 Orchestration — api.py Cleanup

When asked to execute Phase 8, follow this exact sequence:

### Wave 1 — Parallel (run simultaneously)
Invoke all three at the same time:
- @import-cleaner — removes dead imports, get_tree_storage(), initialise_tree()
- @endpoint-remover — removes old tree/node/saves endpoints
- @user-endpoint-refactor — refactors user endpoints off RoutesHelper

Wait for all three to confirm completion before proceeding.

### Wave 2 — Sequential (only after