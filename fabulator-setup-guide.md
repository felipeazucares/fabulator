# Fabulator — Complete Setup Guide
## Containerised Dev Environment on Apple Silicon (M5)
### Millie Kovacs, March 2026

---

## Architecture Overview

```
Native macOS (M5)
├── /usr/local/bin/colima          ← VM runtime
├── /usr/local/bin/docker          ← Docker CLI
├── /usr/local/bin/docker-compose  ← Compose (standalone + CLI plugin)
├── /usr/local/bin/qemu-img        ← symlink → /opt/homebrew/bin/qemu-img
└── ~/.docker/cli-plugins/
    ├── docker-buildx              ← Multi-platform builds
    └── docker-compose             ← symlink (enables `docker compose` plugin style)

[Homebrew — single package]
└── qemu                          ← Required by Lima/Colima for VM disk creation.
                                    No standalone macOS binary alternative exists.

Inside Colima VM (Linux/ARM64, VZ + virtiofs)
└── Docker daemon
    ├── fabulator-api  (python:3.12-slim-bookworm / FastAPI + MongoDB + Redis)
    └── claude-code    (node:20-slim / Claude Code CLI) [dev profile only]
```

**Key design decisions:**
- Minimal Homebrew footprint — only `qemu` (unavoidable system dependency)
- `node:20-slim` not Alpine — Alpine's musl libc crashes Claude Code on first run
- `python:3.12-slim-bookworm` — ARM64 native, no emulation overhead
- Claude Code auth via `CLAUDE_CODE_OAUTH_TOKEN` env var — no keychain, no OAuth browser redirect inside container
- Claude Code behind `dev` profile — won't accidentally start in production
- Atlas + Redis Cloud — no local DB containers needed

---

## Project Structure

```
fabulator/                       ← project root
├── .devcontainer/
│   ├── Dockerfile               ← Claude Code container (node:20-slim)
│   └── devcontainer.json        ← VS Code Dev Containers config
├── server/
│   ├── app/                     ← FastAPI application package
│   │   ├── api.py
│   │   ├── authentication.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── helpers.py
│   │   └── models.py
│   ├── main.py
│   └── Dockerfile               ← FastAPI container (python:3.12-slim-bookworm)
├── docker-compose.yml
├── requirements.txt             ← Python deps (build context root)
├── .env                         ← secrets (never commit)
├── .env.example
├── fabulator-install.sh         ← toolchain install/uninstall script
└── .gitignore
```

---

## Phase 0: Prerequisites

### Step 0.1 — Rosetta 2
```bash
softwareupdate --install-rosetta --agree-to-license
```

### Step 0.2 — Xcode Command Line Tools
```bash
xcode-select --install
```

---

## Phase 1: Install the Toolchain

Run the provided `fabulator-install.sh` script:

```bash
chmod +x fabulator-install.sh
./fabulator-install.sh
```

This installs (versions pinned at top of script):
- **Homebrew** — only if not present; only used for qemu
- **qemu** (via Homebrew) — Lima/Colima needs `qemu-img` to create VM disk images. No standalone binary exists for macOS. Symlinked to `/usr/local/bin/qemu-img` so Colima can find it regardless of shell PATH.
- **Lima v1.0.7** — VM template manager. Colima shells out to `limactl` at runtime. **Must be v1.x** — Colima v0.10.0 generates `vmOpts` YAML that Lima v0.23.x doesn't understand (causes FATA on start).
- **Colima v0.10.0** — Container VM runtime
- **Docker CLI 29.3.0** — Client only; daemon runs inside Colima VM
- **Docker Compose v2.36.2** — Installed as standalone binary AND symlinked as Docker CLI plugin (enables both `docker-compose` and `docker compose` invocation styles)
- **Docker Buildx v0.32.1** — Multi-platform builds

**To uninstall everything cleanly:**
```bash
./fabulator-install.sh uninstall
```

### Step 1.1 — Verify
```bash
colima version
docker --version
docker compose version
docker buildx version
```

---

## Phase 2: Start Colima

### Step 2.1 — First start
```bash
colima start \
  --vm-type vz \
  --vz-rosetta \
  --mount-type virtiofs \
  --cpu 4 \
  --memory 8 \
  --disk 60
```

**Flags:**
- `--vm-type vz` — Apple's native Virtualization Framework. Faster than QEMU.
- `--vz-rosetta` — Rosetta 2 for x86 images inside the VM. Essentially free, enable it.
- `--mount-type virtiofs` — Fast host↔VM file sharing. Required for hot reload.
- `--disk 60` — Docker images accumulate fast. Can increase later, cannot decrease without rebuilding VM.

First start takes 1-2 minutes (downloading Linux kernel image). Subsequent starts ~5 seconds.

**Known non-fatal warning on start:**
```
stat: cannot statx '/proc/sys/fs/binfmt_misc/rosetta': No such file or directory
WARN: unable to enable rosetta: exit status 1
```
This is a known issue with Colima v0.10.0 + Lima v1.x binfmt handling. The VM starts correctly. We build native arm64 images so Rosetta inside the VM is irrelevant.

### Step 2.2 — Docker socket symlink

Colima creates its socket at `~/.colima/default/docker.sock`.
VS Code Dev Containers expects it at `/var/run/docker.sock`.

```bash
sudo ln -sf ~/.colima/default/docker.sock /var/run/docker.sock
```

**Must be run AFTER `colima start`** — the socket doesn't exist until the VM is running.
**Must be re-run after reboot** — Colima does NOT autostart on reboot.

### Step 2.3 — Verify Docker
```bash
docker info
docker run --rm hello-world
```

---

## Phase 3: Environment Configuration

### Step 3.1 — .env file

```bash
cp .env.example .env
```

Required variables in `.env`:

```
# FastAPI / Atlas / Redis
MONGO_DETAILS=mongodb+srv://...
REDISHOST=redis://...
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# For fabulator-api container only
ANTHROPIC_API_KEY=sk-ant-api03-...

# For claude-code container — generate with: claude setup-token
# Valid for 1 year. DO NOT also set ANTHROPIC_API_KEY in the claude-code service.
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...
```

### Step 3.2 — Generate Claude Code OAuth token

This is the correct way to authenticate Claude Code in a container. The standard
OAuth browser flow does not work headlessly, and credentials are stored in the
macOS keychain (not a file), so volume mounting `~/.claude` does not work.

**On your Mac (where you have a browser):**
```bash
claude setup-token
```

This outputs a `sk-ant-oat01-...` token valid for **1 year**.
**Copy it immediately — you won't see it again.**
Store in your password manager AND in `.env` as `CLAUDE_CODE_OAUTH_TOKEN`.

**Calendar reminder:** Run `claude setup-token` again in ~11 months to refresh.

**DO NOT** set both `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_API_KEY` in the same
container — Claude Code will warn about an auth conflict. The compose file passes
`CLAUDE_CODE_OAUTH_TOKEN` to `claude-code` and `ANTHROPIC_API_KEY` to `fabulator-api`
only. Keep them separate.

---

## Phase 4: First Build and Boot

### Step 4.1 — Build images
```bash
docker compose --profile dev build
```

First build pulls base images and installs all dependencies. Expect 3-5 minutes.
Subsequent builds use Docker layer cache — fast unless requirements.txt changes.

### Step 4.2 — Start API only (verify it works first)
```bash
docker compose up
```

Watch for:
- uvicorn startup message
- healthcheck passing: `GET /health HTTP/1.1" 200 OK`

```bash
curl http://localhost:8000/health
curl http://localhost:8000/docs    # Swagger UI in browser
```

### Step 4.3 — Start with Claude Code
```bash
docker compose down
docker compose --profile dev up
```

Or for an interactive one-shot Claude Code session:
```bash
docker compose up -d              # API in background
docker compose --profile dev run --rm -it claude-code
```

---

## Phase 5: VS Code Dev Containers

### Step 5.1 — Install VS Code extension
- **Dev Containers** (ms-vscode-remote.remote-containers)

### Step 5.2 — Open in container
`CMD+SHIFT+P` → "Dev Containers: Reopen in Container"

VS Code reads `.devcontainer/devcontainer.json`, which points at the `claude-code`
service in `docker-compose.yml`. It starts the full compose stack and attaches to
the claude-code container.

**Failure mode — hangs on "Connecting to Dev Container":**
The `claude-code` service has `depends_on: fabulator-api: condition: service_healthy`.
If the API healthcheck is failing, VS Code will wait indefinitely.
Fix: run `docker compose up` first in a terminal, verify API is healthy, then reopen in container.

**Failure mode — "fabulator-claude-code image not found":**
The compose file specifies `image: fabulator-claude-code`. Build it first:
```bash
docker compose --profile dev build claude-code
```

---

## Phase 6: Validation Checklist

```bash
# 1. Colima running
colima status

# 2. API healthy
curl http://localhost:8000/health

# 3. Claude Code container auth working
docker compose --profile dev run --rm -it --entrypoint bash claude-code
# Inside container:
claude  # should show welcome screen with your org name, no auth prompt
```

---

## Day-to-Day Commands

```bash
# Start of dev session
colima start  # if not already running
sudo ln -sf ~/.colima/default/docker.sock /var/run/docker.sock
docker compose up -d              # API in background
docker compose --profile dev run --rm -it claude-code  # Claude Code session

# API only
docker compose up

# View logs
docker compose logs -f

# Rebuild after dependency changes
docker compose --profile dev build
docker compose --profile dev up

# Stop everything
docker compose down

# Nuclear reset (keeps source code, wipes containers + images)
docker compose down --rmi all
colima stop

# Full teardown including VM
./fabulator-install.sh uninstall
```

---

## Upgrade Path

**Toolchain binaries** — update version pins at top of `fabulator-install.sh`, re-run.

**Claude Code OAuth token** — expires after 1 year:
```bash
claude setup-token   # on Mac, generates new sk-ant-oat01-... token
# Update CLAUDE_CODE_OAUTH_TOKEN in .env
docker compose --profile dev build claude-code  # rebuild with new token baked into .claude.json
```

Wait — the token comes from the env var, not baked in. Just update `.env` and restart.
No rebuild needed for token rotation.

**Colima/Lima compatibility:** Lima must be v1.x with Colima v0.10.0. Lima v2.x
compatibility with Colima v0.10.0 is unverified — check release notes before upgrading.

---

## Known Issues and Limitations

1. **Colima doesn't autostart on reboot.** Run `colima start` and recreate the
   docker.sock symlink at the start of each dev session.

2. **Rosetta binfmt warning on `colima start`.** Non-fatal. Known issue with
   Colima v0.10.0 + Lima v1.x. Ignore it.

3. **virtiofs mount loss after reboot.** Symptom: empty `/workspace` inside containers.
   Fix: `colima stop && colima start`.

4. **`docker compose` vs `docker-compose`** — both work. The install script symlinks
   docker-compose as a CLI plugin so the plugin form (`docker compose`) works too.

5. **Claude Code OAuth token in .env is plaintext.** Treat `.env` like a password file.
   It's in `.gitignore`. Keep it there.

6. **`--dangerously-skip-permissions` in the Claude Code container.** Safe here because
   the container only has access to the explicit volume mounts defined in compose.
   Never use this flag outside a container.

7. **Claude Code OAuth token expires in 1 year.** Set a calendar reminder.
   Run `claude setup-token` on your Mac and update `CLAUDE_CODE_OAUTH_TOKEN` in `.env`.

---

## Lessons Learned (for future reference)

- **Lima version matters:** Colima v0.10.0 requires Lima v1.x. Lima v0.23.x causes
  FATA on start due to `vmOpts` YAML incompatibility.
- **qemu-img must be on PATH:** Homebrew installs to `/opt/homebrew/bin` which isn't
  always on PATH in non-login shells. Symlink to `/usr/local/bin`.
- **Claude Code auth in containers:** Standard OAuth browser flow doesn't work headlessly.
  Keychain-stored tokens can't be volume-mounted. `claude setup-token` is the correct
  solution — generates a 1-year portable token for `CLAUDE_CODE_OAUTH_TOKEN`.
- **`~/.claude.json` required to skip onboarding:** Even with a valid OAuth token,
  Claude Code shows the onboarding UI without a minimal `~/.claude.json`. Bake it
  into the Dockerfile with `hasCompletedOnboarding: true` and `oauthAccount` fields.
- **`docker compose` plugin form:** Requires compose to be installed as a CLI plugin
  in `~/.docker/cli-plugins/`. Symlink from `/usr/local/bin/docker-compose`.
