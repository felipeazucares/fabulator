#!/usr/bin/env bash
# =============================================================================
# fabulator-install.sh
# Installs the minimal Docker toolchain for Apple Silicon Mac.
#
# Native dependencies (via direct binary download):
#   /usr/local/bin/limactl          — Lima VM manager (Colima dependency)
#   /usr/local/bin/lima             — Lima shell helper
#   /usr/local/share/lima/          — Lima templates (required by limactl at runtime)
#   /usr/local/bin/colima           — Colima container VM runtime
#   /usr/local/bin/docker           — Docker CLI client
#   /usr/local/bin/docker-compose   — Compose orchestration
#   ~/.docker/cli-plugins/docker-buildx — Buildx multi-platform builds
#
# Homebrew dependency (no standalone binary alternative exists on macOS):
#   qemu  — Required by Lima/Colima to create VM disk images (qemu-img).
#            Homebrew installs to /opt/homebrew/bin on Apple Silicon.
#            We symlink qemu-img to /usr/local/bin so Colima can find it
#            regardless of shell PATH configuration.
#
# Compatibility notes (learned the hard way):
#   - Colima v0.10.0 requires Lima v1.x — it generates vmOpts YAML that only
#     Lima v1.0+ understands. Lima v0.23.x causes FATA on colima start.
#   - Lima v2.x has breaking changes (pluggable VM drivers, template format).
#     Unverified with Colima v0.10.0 — avoid until confirmed.
#   - Homebrew on Apple Silicon installs to /opt/homebrew/bin, not /usr/local/bin.
#     Colima shells out to qemu-img and needs it on a predictable PATH —
#     symlink to /usr/local/bin guarantees findability regardless of shell config.
#   - Rosetta 2 binfmt warning ("cannot statx /proc/sys/fs/binfmt_misc/rosetta")
#     is a known non-fatal issue with Colima v0.10.0 + Lima v1.x. VM still
#     starts correctly. We build native arm64 images so this doesn't affect us.
#   - docker.sock symlink must be created AFTER colima start — the socket file
#     doesn't exist until Colima is running.
#   - Colima does NOT autostart on reboot. Run 'colima start' each session.
#
# Usage:
#   chmod +x fabulator-install.sh
#   ./fabulator-install.sh            # install everything
#   ./fabulator-install.sh uninstall  # remove everything cleanly
#
# Check for latest versions at:
#   Lima:     https://github.com/lima-vm/lima/releases
#   Colima:   https://github.com/abiosoft/colima/releases
#   Docker:   https://download.docker.com/mac/static/stable/aarch64/
#   Compose:  https://github.com/docker/compose/releases
#   Buildx:   https://github.com/docker/buildx/releases
# =============================================================================

set -euo pipefail

# --- Colours ------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
die()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# --- Sanity checks ------------------------------------------------------------
[[ "$(uname -s)" == "Darwin" ]] || die "macOS only."
[[ "$(uname -m)" == "arm64"  ]] || die "Apple Silicon (arm64) only."
command -v curl &>/dev/null      || die "curl not found — it ships with macOS, something is very wrong."

# --- Pinned versions ----------------------------------------------------------
LIMA_VERSION="v1.0.7"       # https://github.com/lima-vm/lima/releases
COLIMA_VERSION="v0.10.0"    # https://github.com/abiosoft/colima/releases
DOCKER_VERSION="29.3.0"     # https://download.docker.com/mac/static/stable/aarch64/
COMPOSE_VERSION="v2.36.2"   # https://github.com/docker/compose/releases
BUILDX_VERSION="v0.32.1"    # https://github.com/docker/buildx/releases

INSTALL_DIR="/usr/local/bin"
SHARE_DIR="/usr/local/share"
PLUGIN_DIR="${HOME}/.docker/cli-plugins"

# =============================================================================
# INSTALL
# =============================================================================
install_all() {
  echo ""
  info "Installing Docker toolchain for Apple Silicon (M-series Mac)"
  info "Lima:    ${LIMA_VERSION}"
  info "Colima:  ${COLIMA_VERSION}"
  info "Docker:  ${DOCKER_VERSION}"
  info "Compose: ${COMPOSE_VERSION}"
  info "Buildx:  ${BUILDX_VERSION}"
  echo ""

  # --- Rosetta 2 --------------------------------------------------------------
  if /usr/bin/pgrep -q oahd 2>/dev/null; then
    info "Rosetta 2 already installed ✓"
  else
    warn "Rosetta 2 not detected. Installing..."
    softwareupdate --install-rosetta --agree-to-license
  fi

  # --- Homebrew + qemu --------------------------------------------------------
  # qemu-img is required by Lima/Colima to create VM disk images.
  # No standalone macOS binary exists — Homebrew is the only practical path.
  # We install Homebrew only if absent, then qemu only. Nothing else via brew.
  if ! command -v brew &>/dev/null; then
    info "Installing Homebrew (required for qemu)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
  else
    info "Homebrew already installed ✓"
  fi

  if brew list qemu &>/dev/null 2>&1; then
    info "qemu already installed ✓ ($(qemu-img --version | head -1))"
  else
    info "Installing qemu via Homebrew..."
    brew install qemu
  fi

  # Symlink qemu-img to /usr/local/bin so Colima can find it in all contexts.
  # Homebrew on Apple Silicon installs to /opt/homebrew/bin which is not
  # always on PATH in non-login shells or scripts.
  if [[ -f "/opt/homebrew/bin/qemu-img" ]]; then
    sudo ln -sf /opt/homebrew/bin/qemu-img "${INSTALL_DIR}/qemu-img"
    info "qemu-img symlinked → ${INSTALL_DIR}/qemu-img ✓"
  else
    warn "qemu-img not found at /opt/homebrew/bin/qemu-img — Homebrew install may have failed"
  fi

  mkdir -p "${PLUGIN_DIR}"

  # --- Lima -------------------------------------------------------------------
  # Lima tarball contains:
  #   bin/lima      — shell helper
  #   bin/limactl   — main CLI (Colima shells out to this at runtime)
  #   share/lima/   — VM templates (NOT optional; required at runtime)
  #
  # tar --no-same-owner suppresses "Can't restore time" warnings on macOS /tmp.
  # xattr strip required — Gatekeeper quarantines curl-downloaded binaries.
  info "Installing lima ${LIMA_VERSION}..."
  curl -fsSL \
    "https://github.com/lima-vm/lima/releases/download/${LIMA_VERSION}/lima-${LIMA_VERSION#v}-Darwin-arm64.tar.gz" \
    -o /tmp/lima.tar.gz

  rm -rf /tmp/lima-extract && mkdir -p /tmp/lima-extract
  tar -xzf /tmp/lima.tar.gz -C /tmp/lima-extract --no-same-owner 2>/dev/null || true

  sudo install /tmp/lima-extract/bin/lima    "${INSTALL_DIR}/lima"
  sudo install /tmp/lima-extract/bin/limactl "${INSTALL_DIR}/limactl"
  sudo rm -rf   "${SHARE_DIR}/lima"
  sudo cp -r /tmp/lima-extract/share/lima "${SHARE_DIR}/lima"

  sudo xattr -dr com.apple.quarantine \
    "${INSTALL_DIR}/lima" \
    "${INSTALL_DIR}/limactl" \
    "${SHARE_DIR}/lima" 2>/dev/null || true

  rm -rf /tmp/lima.tar.gz /tmp/lima-extract
  info "lima installed → $(limactl --version)"

  # --- Colima -----------------------------------------------------------------
  info "Installing colima ${COLIMA_VERSION}..."
  curl -fsSL \
    "https://github.com/abiosoft/colima/releases/download/${COLIMA_VERSION}/colima-Darwin-arm64" \
    -o /tmp/colima
  sudo install /tmp/colima "${INSTALL_DIR}/colima"
  sudo xattr -dr com.apple.quarantine "${INSTALL_DIR}/colima" 2>/dev/null || true
  rm /tmp/colima
  info "colima installed → $(colima version | head -1)"

  # --- Docker CLI -------------------------------------------------------------
  info "Installing docker CLI ${DOCKER_VERSION}..."
  curl -fsSL \
    "https://download.docker.com/mac/static/stable/aarch64/docker-${DOCKER_VERSION}.tgz" \
    -o /tmp/docker.tgz
  rm -rf /tmp/docker-extract && mkdir -p /tmp/docker-extract
  tar -xzf /tmp/docker.tgz -C /tmp/docker-extract --no-same-owner 2>/dev/null || true
  sudo install /tmp/docker-extract/docker/docker "${INSTALL_DIR}/docker"
  sudo xattr -dr com.apple.quarantine "${INSTALL_DIR}/docker" 2>/dev/null || true
  rm -rf /tmp/docker.tgz /tmp/docker-extract
  info "docker installed → ${INSTALL_DIR}/docker"

  # --- Docker Compose ---------------------------------------------------------
  info "Installing docker-compose ${COMPOSE_VERSION}..."
  curl -fsSL \
    "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-darwin-aarch64" \
    -o /tmp/docker-compose
  sudo install /tmp/docker-compose "${INSTALL_DIR}/docker-compose"
  sudo xattr -dr com.apple.quarantine "${INSTALL_DIR}/docker-compose" 2>/dev/null || true
  rm /tmp/docker-compose
  info "docker-compose installed → ${INSTALL_DIR}/docker-compose"

  # Symlink compose as a Docker CLI plugin so both invocation styles work:
  #   docker-compose (standalone)  ← already installed above
  #   docker compose (CLI plugin)  ← requires this symlink
  ln -sf "${INSTALL_DIR}/docker-compose" "${PLUGIN_DIR}/docker-compose"
  info "docker-compose plugin symlinked → ${PLUGIN_DIR}/docker-compose ✓"

  # --- Docker Buildx ----------------------------------------------------------
  info "Installing docker-buildx ${BUILDX_VERSION}..."
  curl -fsSL \
    "https://github.com/docker/buildx/releases/download/${BUILDX_VERSION}/buildx-${BUILDX_VERSION}.darwin-arm64" \
    -o "${PLUGIN_DIR}/docker-buildx"
  chmod +x "${PLUGIN_DIR}/docker-buildx"
  xattr -dr com.apple.quarantine "${PLUGIN_DIR}/docker-buildx" 2>/dev/null || true
  info "docker-buildx installed → ${PLUGIN_DIR}/docker-buildx"

  # --- Summary ----------------------------------------------------------------
  echo ""
  info "═══════════════════════════════════════════"
  info " Installation complete — auditable inventory"
  info "═══════════════════════════════════════════"
  echo ""
  printf "  %-14s %s\n" "[homebrew]"  "qemu: $(qemu-img --version 2>/dev/null | head -1)"
  printf "  %-14s %s\n" "qemu-img"   "→ $(readlink ${INSTALL_DIR}/qemu-img 2>/dev/null || echo 'symlink missing')"
  printf "  %-14s %s\n" "limactl"    "$(limactl --version 2>/dev/null)"
  printf "  %-14s %s\n" "colima"     "$(colima version 2>/dev/null | head -1)"
  printf "  %-14s %s\n" "docker"     "at ${INSTALL_DIR}/docker (version requires colima running)"
  printf "  %-14s %s\n" "compose"    "at ${INSTALL_DIR}/docker-compose"
  printf "  %-14s %s\n" "buildx"     "${PLUGIN_DIR}/docker-buildx"
  printf "  %-14s %s\n" "lima share" "${SHARE_DIR}/lima/"
  echo ""
  info "═══════════════════════════════════════════"
  info " Next steps"
  info "═══════════════════════════════════════════"
  echo ""
  echo "  1. Start Colima:"
  echo ""
  echo "     colima start \\"
  echo "       --vm-type vz \\"
  echo "       --vz-rosetta \\"
  echo "       --mount-type virtiofs \\"
  echo "       --cpu 4 \\"
  echo "       --memory 8 \\"
  echo "       --disk 60"
  echo ""
  echo "  2. Create docker socket symlink (AFTER colima start):"
  echo ""
  echo "     sudo ln -sf ~/.colima/default/docker.sock /var/run/docker.sock"
  echo ""
  echo "  3. Verify:"
  echo ""
  echo "     docker info"
  echo "     docker run --rm hello-world"
  echo ""
  warn "Colima does NOT autostart on reboot."
  warn "Run 'colima start ...' at the start of each dev session."
  warn "The Rosetta binfmt warning during start is a known non-fatal issue."
  echo ""
}

# =============================================================================
# UNINSTALL — removes everything this script installed, cleanly
# =============================================================================
uninstall_all() {
  echo ""
  warn "This will remove the Docker toolchain AND all Colima/container data."
  read -r -p "Are you sure? [y/N] " confirm
  [[ "${confirm}" =~ ^[Yy]$ ]] || { info "Aborted."; exit 0; }
  echo ""

  # Stop and delete Colima VM first
  if command -v colima &>/dev/null; then
    colima stop   2>/dev/null && info "Colima stopped"  || warn "Colima wasn't running"
    colima delete 2>/dev/null && info "Colima VM deleted" || warn "No Colima VM to delete"
  fi

  # Remove direct-installed binaries (including qemu-img symlink)
  for binary in lima limactl colima docker docker-compose qemu-img; do
    if [[ -f "${INSTALL_DIR}/${binary}" ]]; then
      sudo rm -f "${INSTALL_DIR}/${binary}"
      info "Removed ${INSTALL_DIR}/${binary}"
    fi
  done

  # Remove Lima VM templates
  if [[ -d "${SHARE_DIR}/lima" ]]; then
    sudo rm -rf "${SHARE_DIR}/lima"
    info "Removed ${SHARE_DIR}/lima"
  fi

  # Remove buildx plugin
  if [[ -f "${PLUGIN_DIR}/docker-compose" ]]; then
    rm -f "${PLUGIN_DIR}/docker-compose"
    info "Removed compose plugin symlink"
  fi

  if [[ -f "${PLUGIN_DIR}/docker-buildx" ]]; then
    rm -f "${PLUGIN_DIR}/docker-buildx"
    info "Removed buildx plugin"
  fi

  # Remove docker socket symlink
  sudo rm -f /var/run/docker.sock
  info "Removed /var/run/docker.sock"

  # Remove runtime data
  rm -rf "${HOME}/.colima" && info "Removed ~/.colima"
  rm -rf "${HOME}/.lima"   && info "Removed ~/.lima"
  rm -rf "${HOME}/.docker" && info "Removed ~/.docker"

  # Remove qemu via Homebrew
  if command -v brew &>/dev/null; then
    if brew list qemu &>/dev/null 2>&1; then
      info "Uninstalling qemu via Homebrew..."
      brew uninstall qemu
      info "qemu removed ✓"
    else
      warn "qemu not in Homebrew — skipping"
    fi
  else
    warn "Homebrew not found — qemu may need manual removal"
  fi

  echo ""
  info "Clean uninstall complete."
  warn "Homebrew itself has NOT been removed."
  warn "To remove Homebrew entirely:"
  warn "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/uninstall.sh)\""
  echo ""
}

# =============================================================================
# ENTRYPOINT
# =============================================================================
case "${1:-install}" in
  install)   install_all ;;
  uninstall) uninstall_all ;;
  *)         die "Usage: $0 [install|uninstall]" ;;
esac
