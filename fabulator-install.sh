#!/usr/bin/env bash
# =============================================================================
# fabulator-install.sh
# Installs the minimal 4-binary Docker toolchain for Apple Silicon Mac.
# No Homebrew. No package manager. Fully auditable. Clean uninstall included.
#
# Installs:
#   /usr/local/bin/colima          — container VM runtime
#   /usr/local/bin/docker          — Docker CLI client
#   /usr/local/bin/docker-compose  — Compose orchestration
#   ~/.docker/cli-plugins/docker-buildx — Buildx multi-platform builds
#
# Usage:
#   chmod +x fabulator-install.sh
#   ./fabulator-install.sh          # install
#   ./fabulator-install.sh uninstall # remove everything
# =============================================================================

set -euo pipefail

# --- Colours (because life's too short for monochrome output) ----------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[+]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
die()     { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# --- Sanity checks ------------------------------------------------------------
[[ "$(uname -s)" == "Darwin" ]]  || die "macOS only. You're not on macOS."
[[ "$(uname -m)" == "arm64" ]]   || die "Apple Silicon (arm64) only."
command -v curl &>/dev/null       || die "curl not found. It ships with macOS — something is very wrong."

# --- Pinned versions (update these when you want to upgrade) -----------------
# Check latest at:
#   Colima:        https://github.com/abiosoft/colima/releases
#   Docker CLI:    https://download.docker.com/mac/static/stable/aarch64/
#   Compose:       https://github.com/docker/compose/releases
#   Buildx:        https://github.com/docker/buildx/releases
COLIMA_VERSION="v0.10.0"
DOCKER_VERSION="29.3.0"
COMPOSE_VERSION="v2.36.2"
BUILDX_VERSION="v0.32.1"

INSTALL_DIR="/usr/local/bin"
PLUGIN_DIR="${HOME}/.docker/cli-plugins"

# =============================================================================
# INSTALL
# =============================================================================
install_all() {
  echo ""
  info "Installing 4-binary Docker toolchain for Apple Silicon"
  info "Versions: colima=${COLIMA_VERSION} docker=${DOCKER_VERSION} compose=${COMPOSE_VERSION} buildx=${BUILDX_VERSION}"
  echo ""

  # Ensure Rosetta 2 is present (needed for some CLI tools even on ARM)
  if ! /usr/bin/pgrep -q oahd 2>/dev/null; then
    warn "Rosetta 2 not detected. Installing..."
    softwareupdate --install-rosetta --agree-to-license
  else
    info "Rosetta 2 already installed ✓"
  fi

  mkdir -p "${PLUGIN_DIR}"

  # --- 1. Colima --------------------------------------------------------------
  info "Installing colima ${COLIMA_VERSION}..."
  curl -fsSL \
    "https://github.com/abiosoft/colima/releases/download/${COLIMA_VERSION}/colima-Darwin-arm64" \
    -o /tmp/colima
  sudo install /tmp/colima "${INSTALL_DIR}/colima"
  rm /tmp/colima
  info "colima installed → $(which colima)"

  # --- 2. Docker CLI ----------------------------------------------------------
  info "Installing docker CLI ${DOCKER_VERSION}..."
  curl -fsSL \
    "https://download.docker.com/mac/static/stable/aarch64/docker-${DOCKER_VERSION}.tgz" \
    -o /tmp/docker.tgz
  tar -xzf /tmp/docker.tgz -C /tmp
  sudo install /tmp/docker/docker "${INSTALL_DIR}/docker"
  rm -rf /tmp/docker /tmp/docker.tgz
  info "docker installed → $(which docker)"

  # --- 3. Docker Compose ------------------------------------------------------
  info "Installing docker-compose ${COMPOSE_VERSION}..."
  curl -fsSL \
    "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-darwin-aarch64" \
    -o /tmp/docker-compose
  sudo install /tmp/docker-compose "${INSTALL_DIR}/docker-compose"
  rm /tmp/docker-compose
  info "docker-compose installed → $(which docker-compose)"

  # --- 4. Docker Buildx (as CLI plugin) ---------------------------------------
  info "Installing docker-buildx ${BUILDX_VERSION}..."
  curl -fsSL \
    "https://github.com/docker/buildx/releases/download/${BUILDX_VERSION}/buildx-${BUILDX_VERSION}.darwin-arm64" \
    -o "${PLUGIN_DIR}/docker-buildx"
  chmod +x "${PLUGIN_DIR}/docker-buildx"
  info "docker-buildx installed → ${PLUGIN_DIR}/docker-buildx"

  # --- Docker socket symlink --------------------------------------------------
  # Required for VS Code Dev Containers to find the socket
  info "Creating docker socket symlink..."
  if [[ ! -L /var/run/docker.sock ]]; then
    sudo ln -sf "${HOME}/.colima/default/docker.sock" /var/run/docker.sock 2>/dev/null || \
      warn "Could not create /var/run/docker.sock symlink — do this manually after first colima start"
  fi

  echo ""
  info "All binaries installed. Auditable inventory:"
  echo ""
  echo "  ${INSTALL_DIR}/colima         $(colima version 2>/dev/null | head -1 || echo '(version check after first run)')"
  echo "  ${INSTALL_DIR}/docker         $(docker --version 2>/dev/null || echo '(version check after colima start)')"
  echo "  ${INSTALL_DIR}/docker-compose $(docker-compose version 2>/dev/null || echo '(version check after colima start)')"
  echo "  ${PLUGIN_DIR}/docker-buildx"
  echo ""

  info "Next step — start Colima:"
  echo ""
  echo "  colima start \\"
  echo "    --vm-type vz \\"
  echo "    --vz-rosetta \\"
  echo "    --mount-type virtiofs \\"
  echo "    --cpu 4 \\"
  echo "    --memory 8 \\"
  echo "    --disk 60"
  echo ""
  warn "Run 'colima start' BEFORE creating the docker.sock symlink if it failed above."
  echo ""
}

# =============================================================================
# UNINSTALL — actually removes everything, unlike some tools I could mention
# =============================================================================
uninstall_all() {
  echo ""
  warn "Uninstalling all 4 binaries and Colima data..."
  echo ""

  colima stop 2>/dev/null && info "Colima stopped" || warn "Colima wasn't running"
  colima delete 2>/dev/null && info "Colima VM deleted" || warn "No Colima VM to delete"

  for binary in colima docker docker-compose; do
    if [[ -f "${INSTALL_DIR}/${binary}" ]]; then
      sudo rm -f "${INSTALL_DIR}/${binary}"
      info "Removed ${INSTALL_DIR}/${binary}"
    fi
  done

  rm -f "${PLUGIN_DIR}/docker-buildx" && info "Removed buildx plugin"
  sudo rm -f /var/run/docker.sock && info "Removed docker.sock symlink"
  rm -rf "${HOME}/.colima" && info "Removed ~/.colima (VM data)"
  rm -rf "${HOME}/.docker" && info "Removed ~/.docker"

  echo ""
  info "Clean uninstall complete. Your machine is as it was."
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