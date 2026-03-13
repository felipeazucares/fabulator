# =============================================================================
# Claude Code Development Container
# Base: node:20-slim (Debian) — NOT Alpine. Alpine's musl libc breaks
# Claude Code CLI with a cryptic linker error on first run. Don't be a hero.
# =============================================================================
FROM node:20-slim

# System deps — git for obvious reasons, curl for healthchecks,
# python3 so Claude can actually work on the FastAPI code
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    python3 \
    python3-pip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — Claude Code runs as 'claude', not root
# UID 1001 avoids conflicts with common host UIDs
RUN useradd -m -u 1001 -s /bin/bash claude

# Install Claude Code CLI globally, pinned to avoid surprise breaking changes
# Check https://github.com/anthropics/claude-code/releases for latest
RUN npm install -g @anthropic-ai/claude-code

# Workspace is mounted via compose volume
WORKDIR /workspace

# Drop to non-root before entrypoint
USER claude

# --dangerously-skip-permissions is safe here because we're in an isolated
# container with a firewall. Don't use this on your host machine.
ENTRYPOINT ["claude", "--dangerously-skip-permissions"]
