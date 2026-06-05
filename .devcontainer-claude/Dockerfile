# =============================================================================
# Claude Code Development Container
# Base: node:20-slim (Debian) — NOT Alpine. Alpine's musl libc breaks
# Claude Code CLI with a cryptic linker error on first run. Don't be a hero.
#
# Auth: CLAUDE_CODE_OAUTH_TOKEN env var (set in docker-compose, sourced from .env)
# DO NOT set ANTHROPIC_API_KEY in this container — causes auth conflict.
# =============================================================================
FROM node:20-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    python3 \
    python3-pip \
    nano \
    sudo \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN echo "claude ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

COPY server/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt --break-system-packages

# Non-root user — Claude Code runs as 'claude', not root
RUN useradd -m -u 1001 -s /bin/bash claude

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Bake in minimal ~/.claude.json to bypass onboarding loop.
# oauthAccount tells Claude Code this session is already set up.
# The actual auth token comes from CLAUDE_CODE_OAUTH_TOKEN env var at runtime.
RUN mkdir -p /home/claude/.claude && \
    echo '{ \
      "hasCompletedOnboarding": true, \
      "lastOnboardingVersion": "2.1.75", \
      "oauthAccount": { \
        "accountUuid": "64b79603-26c7-4966-acb5-500a11df0357", \
        "emailAddress": "passpam@icloud.com", \
        "organizationUuid": "3c855726-f143-465a-936d-4e01100161f6", \
        "organizationName": "passpam@icloud.com'\''s Organization" \
      } \
    }' > /home/claude/.claude.json && \
    ln -sf /home/claude/.claude.json /home/claude/.claude/.claude.json && \
    chown -R claude:claude /home/claude/.claude /home/claude/.claude.json

WORKDIR /workspace

USER claude

ENTRYPOINT ["claude", "--dangerously-skip-permissions"]
