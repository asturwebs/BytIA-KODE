#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/asturwebs/BytIA-KODE.git"
INSTALL_DIR="${INSTALL_DIR:-$HOME/BytIA-KODE}"
BIN_DIR="$HOME/.local/bin"
KODE_HOME="$HOME/.bytia-kode"

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

banner

# ── Dependencies ──────────────────────────────────────────────

info "Checking dependencies..."

if ! command -v git &>/dev/null; then
    error "git not found. Install it first: sudo apt install git"
fi
ok "git"

if ! command -v uv &>/dev/null; then
    info "uv not found — installing..."
    curl -fsSL https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! command -v uv &>/dev/null; then
        error "uv installation failed. Install manually: https://docs.astral.sh/uv/"
    fi
fi
ok "uv $(uv --version 2>/dev/null | head -1)"

if ! command -v python3 &>/dev/null; then
    error "python3 not found. Install it first: sudo apt install python3"
fi
ok "python3 $(python3 --version)"

# ── Clone / Update ────────────────────────────────────────────

if [ -d "$INSTALL_DIR/.git" ]; then
    info "Existing installation found at $INSTALL_DIR"
    info "Updating..."
    cd "$INSTALL_DIR"
    git pull --ff-only || warn "Could not pull — local changes may exist. Continuing with current state."
else
    info "Cloning into $INSTALL_DIR..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone "$REPO" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi
ok "Repository ready"

# ── Python environment ────────────────────────────────────────

info "Setting up Python environment..."
uv sync --quiet
ok "Virtual environment (.venv)"

# ── Config ───────────────────────────────────────────────────

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        warn ".env created from .env.example — EDIT IT with your provider config"
    else
        cat > .env << 'ENVEOF'
# BytIA KODE Configuration
# See README.md for all options

PROVIDER_BASE_URL=http://localhost:8080/v1
PROVIDER_API_KEY=not-needed
PROVIDER_MODEL=auto

# Uncomment and configure for cloud fallback:
# FALLBACK_BASE_URL=https://your-api-endpoint/v1
# FALLBACK_API_KEY=your-api-key
# FALLBACK_MODEL=your-model

# Uncomment for Telegram bot:
# TELEGRAM_BOT_TOKEN=your-bot-token
# TELEGRAM_ALLOWED_USERS=your-user-id
ENVEOF
        warn ".env created with defaults — EDIT IT with your provider config"
    fi
else
    ok ".env already exists (preserved)"
fi

# ── Skills Setup ──────────────────────────────────────────────

info "Setting up skills..."

SKILLS_VENDOR="$INSTALL_DIR/src/bytia_kode/vendor/skills"
SKILLS_HOME="$KODE_HOME/skills"

mkdir -p "$SKILLS_HOME"
mkdir -p "$SKILLS_HOME/vendor"
mkdir -p "$SKILLS_HOME/user"

if [ -d "$SKILLS_VENDOR" ]; then
    for skill_dir in "$SKILLS_VENDOR"/*/; do
        [ -d "$skill_dir" ] || continue
        skill_name=$(basename "$skill_dir")
        dest="$SKILLS_HOME/vendor/$skill_name"
        
        if [ -d "$dest" ] && [ ! -L "$dest" ]; then
            mv "$dest" "$dest.backup.$(date +%s)" 2>/dev/null || true
        fi
        
        rm -rf "$dest"
        cp -r "$skill_dir" "$dest"
        ok "vendor skill: $skill_name"
    done
else
    info "No vendor skills found in package (skipping)"
fi

ok "Skills directory structure ready"

# ── BytIA Ecosystem Integration ─────────────────────────────

if [ -d "$HOME/bytia/skills" ]; then
    echo ""
    info "BytIA ecosystem detected at ~/bytia/"
    echo ""
    echo "  BytIA-KODE can integrate with your BytIA skills ecosystem."
    echo "  This allows you to share skills between BytIA-KODE and other"
    echo "  AI assistants (Claude Code, Kimi, Gemini, etc.)."
    echo ""
    read -p "  Create symlink to ~/bytia/skills? [y/N]: " BYTIA_LINK
    
    if [[ "$BYTIA_LINK" =~ ^[Yy]$ ]]; then
        ln -sfn "$HOME/bytia/skills" "$SKILLS_HOME/bytia"
        ok "Linked to ~/bytia/skills/"
    else
        info "Skipped. You can link manually later:"
        info "  ln -s ~/bytia/skills ~/.bytia-kode/skills/bytia"
    fi
else
    info "No BytIA ecosystem found (normal for new users)"
fi

# ── Wrapper script ────────────────────────────────────────────

mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/bytia-kode" << WRAPPER
#!/usr/bin/env bash
set -euo pipefail
cd "$INSTALL_DIR"
exec uv run python -m bytia_kode.tui "\$@"
WRAPPER
chmod +x "$BIN_DIR/bytia-kode"
ok "Wrapper installed → $BIN_DIR/bytia-kode"

# ── PATH check ────────────────────────────────────────────────

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR is not in your PATH"
    echo ""
    echo "  Add this to your ~/.zshrc or ~/.bashrc:"
    echo ""
    printf "    ${GREEN}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}\n"
    echo ""
fi

# ── Git hooks ─────────────────────────────────────────────────

if [ -d ".githooks" ]; then
    git config core.hooksPath .githooks
    ok "Git hooks configured"
fi

# ── Done ──────────────────────────────────────────────────────

echo ""
printf "${GREEN}${BOLD}  ✓ BytIA KODE installed successfully${RESET}\n"
echo ""
echo "  Commands:"
echo ""
printf "    ${CYAN}bytia-kode${RESET}          Start TUI\n"
printf "    ${CYAN}bkode${RESET}               (add alias: alias bkode='bytia-kode')\n"
printf "    ${CYAN}bytia-kode --bot${RESET}    Start Telegram bot\n"
echo ""
printf "  Config: ${YELLOW}$INSTALL_DIR/.env${RESET}\n"
printf "  Skills: ${YELLOW}$SKILLS_HOME${RESET}\n"
echo ""
echo "  Skills layers:"
echo "    vendor/  — Bundled with KODE (read-only)"
echo "    user/    — Your custom skills (writable)"
echo "    bytia/   — BytIA ecosystem (if linked)"
echo ""
printf "  Docs:   ${CYAN}https://github.com/asturwebs/BytIA-KODE#readme${RESET}\n"
echo ""
