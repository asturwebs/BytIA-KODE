#!/usr/bin/env bash
# Instalación canónica de BytIA KODE (AST-22): el paquete vive en PyPI.
#   curl -fsSL https://raw.githubusercontent.com/asturwebs/BytIA-KODE/main/install.sh | bash
# Camino: bootstrap de uv → uv tool install bytia-kode (PyPI) → config ~/.bytia-kode
# git clone queda SOLO para desarrollo (ver docs/DEVELOPMENT.md).
set -euo pipefail

KODE_HOME="$HOME/.bytia-kode"
BIN_DIR="$HOME/.local/bin"
PINNED_VERSION="${BYTIA_KODE_VERSION:-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()  { printf "${CYAN}  info ${RESET}%s\n" "$*"; }
ok()    { printf "${GREEN}   ok ${RESET}%s\n" "$*"; }
warn()  { printf "${YELLOW} warn ${RESET}%s\n" "$*"; }
error() { printf "${RED}error ${RESET}%s\n" "$*" >&2; exit 1; }

banner() {
    echo ""
    printf "${BOLD}${CYAN}  ╔══════════════════════════════════════╗${RESET}\n"
    printf "${BOLD}${CYAN}  ║     BytIA KODE — Installer          ║${RESET}\n"
    printf "${BOLD}${CYAN}  ╚══════════════════════════════════════╝${RESET}\n"
    echo ""
}

# Pregunta sí/no por /dev/tty: bajo `curl | bash` el stdin es el propio
# script, así que `read` a secas se comería las líneas siguientes.
ask() {
    local prompt="$1" answer=""
    if [ -r /dev/tty ]; then
        read -p "$prompt" answer < /dev/tty || true
    fi
    [[ "$answer" =~ ^[Yy]$ ]]
}

banner

# ── Dependencies ──────────────────────────────────────────────

info "Checking dependencies..."

if ! command -v curl &>/dev/null; then
    error "curl not found. Install it first: sudo apt install curl"
fi
ok "curl"

if ! command -v uv &>/dev/null; then
    info "uv not found — installing..."
    curl -fsSL https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! command -v uv &>/dev/null; then
        error "uv installation failed. Install manually: https://docs.astral.sh/uv/"
    fi
fi
ok "uv $(uv --version 2>/dev/null | head -1)"

# ── Install from PyPI ─────────────────────────────────────────

if [ -n "$PINNED_VERSION" ]; then
    SPEC="bytia-kode==${PINNED_VERSION}"
    info "Installing ${SPEC} from PyPI..."
else
    SPEC="bytia-kode"
    info "Installing bytia-kode (latest) from PyPI..."
fi

# --upgrade hace el flujo idempotente: instala si falta, actualiza si existe.
# (No se ejecuta `bytia-kode` aquí: el entry point arranca la TUI.)
if ! uv tool install --upgrade "$SPEC"; then
    error "uv tool install failed. Check connectivity to PyPI and try again," \
          "or install manually: pip install bytia-kode"
fi
INSTALLED_VERSION="$(uv tool list 2>/dev/null | awk '$1 == "bytia-kode" {print $2}')"
ok "bytia-kode ${INSTALLED_VERSION:-installed} → $BIN_DIR/bytia-kode"

export PATH="$BIN_DIR:$PATH"

# ── Config (~/.bytia-kode) ────────────────────────────────────

mkdir -p "$KODE_HOME"

if [ ! -f "$KODE_HOME/.env" ]; then
    cat > "$KODE_HOME/.env" << 'ENVEOF'
# BytIA KODE Configuration (global)
# See README.md for all options. A project-level .env (CWD) takes precedence.

PROVIDER_BASE_URL=http://localhost:8080/v1
PROVIDER_API_KEY=not-needed
PROVIDER_MODEL=auto

# Fallback provider (cloud API):
# FALLBACK_BASE_URL=https://your-api-endpoint/v1
# FALLBACK_API_KEY=your-api-key
# FALLBACK_MODEL=your-model

# Telegram bot:
# TELEGRAM_BOT_TOKEN=your-bot-token
# TELEGRAM_ALLOWED_USERS=your-user-id
ENVEOF
    warn "$KODE_HOME/.env created with defaults — EDIT IT with your provider config"
else
    ok "$KODE_HOME/.env already exists (preserved)"
fi

# ── Skills Setup ──────────────────────────────────────────────

info "Setting up skills..."

SKILLS_HOME="$KODE_HOME/skills"
mkdir -p "$SKILLS_HOME/vendor"
mkdir -p "$SKILLS_HOME/user"

ok "Skills directory structure ready"
info "Vendor skills are seeded automatically on first launch of bytia-kode"

# ── BytIA Ecosystem Integration ─────────────────────────────

if [ -d "$HOME/bytia/skills" ]; then
    echo ""
    info "BytIA ecosystem detected at ~/bytia/"
    echo ""
    echo "  BytIA-KODE can integrate with your BytIA skills ecosystem."
    echo "  This allows you to share skills between BytIA-KODE and other"
    echo "  AI assistants (Claude Code, Kimi, Gemini, etc.)."
    echo ""
    if ask "  Create symlink to ~/bytia/skills? [y/N]: "; then
        ln -sfn "$HOME/bytia/skills" "$SKILLS_HOME/bytia"
        ok "Linked to ~/bytia/skills/"
    else
        info "Skipped. You can link manually later:"
        info "  ln -s ~/bytia/skills ~/.bytia-kode/skills/bytia"
    fi
else
    info "No BytIA ecosystem found (normal for new users)"
fi

# ── PATH check ────────────────────────────────────────────────

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in your PATH"
    echo ""
    echo "  Add this to your ~/.zshrc or ~/.bashrc:"
    echo ""
    printf "    ${GREEN}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}\n"
    echo ""
fi

# ── Done ──────────────────────────────────────────────────────

echo ""
printf "${GREEN}${BOLD}  ✓ BytIA KODE installed successfully${RESET}\n"
echo ""
echo "  Commands:"
echo ""
printf "    ${CYAN}bytia-kode${RESET}              Start TUI\n"
printf "    ${CYAN}uv tool upgrade bytia-kode${RESET}   Update to the latest release\n"
echo ""
printf "  Config: ${YELLOW}$KODE_HOME/.env${RESET}\n"
printf "  Skills: ${YELLOW}$SKILLS_HOME${RESET}\n"
echo ""
echo "  Skills layers:"
echo "    vendor/  — Bundled with KODE (read-only, seeded on first launch)"
echo "    user/    — Your custom skills (writable)"
echo "    bytia/   — BytIA ecosystem (if linked)"
echo ""
printf "  Docs:   ${CYAN}https://github.com/asturwebs/BytIA-KODE#readme${RESET}\n"
printf "  PyPI:   ${CYAN}https://pypi.org/project/bytia-kode/${RESET}\n"
echo ""
