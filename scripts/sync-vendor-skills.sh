#!/bin/bash
# =============================================================================
# BytIA-KODE Vendor Skills Sync
# =============================================================================
# Copia skills desde ~/bytia/skills/ a src/bytia_kode/vendor/skills/
# Transforma automáticamente de format agentskills.io (metadata:) a flat format.
#
# Usage:
#   ./scripts/sync-vendor-skills.sh              # Sync todos
#   ./scripts/sync-vendor-skills.sh --list       # List skills a sincronizar
#   ./scripts/sync-vendor-skills.sh --sync       # Sync todos
#   ./scripts/sync-vendor-skills.sh <skill>      # Sync skill específico
#
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
BYTIA_SKILLS="$HOME/bytia/skills"
VENDOR_SKILLS="$REPO_ROOT/src/bytia_kode/vendor/skills"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

SYNCABLE_SKILLS=(
    "bytia-constitution"
    "bytia-memory"
    "graphify"
    "skills-manager"
)

log_info() { printf "${BLUE}[INFO]${NC} %s\n" "$1"; }
log_success() { printf "${GREEN}[SUCCESS]${NC} %s\n" "$1"; }
log_error() { printf "${RED}[ERROR]${NC} %s\n" "$1"; }

transform_skill() {
    local source="$1"
    local dest="$2"
    local source_file="$source/SKILL.md"
    local dest_file="$dest/SKILL.md"

    mkdir -p "$dest"

    python3 - "$source_file" "$dest_file" << 'PYEOF'
import sys

source_file = sys.argv[1]
dest_file = sys.argv[2]

with open(source_file, 'r') as f:
    lines = f.readlines()

in_frontmatter = False
in_metadata = False
skip_block = False
output = []
i = 0

while i < len(lines):
    line = lines[i]
    stripped = line.strip()
    leading = len(line) - len(line.lstrip())

    if stripped == '---':
        if not in_frontmatter:
            in_frontmatter = True
            output.append(line)
        elif output and output[-1].strip() == '---':
            in_frontmatter = False
            output.append(line)
        i += 1
        continue

    if in_frontmatter and output and output[-1].strip() != '---':
        if stripped == 'metadata:':
            in_metadata = True
            i += 1
            continue

        if in_metadata:
            if leading < 2:
                in_metadata = False
            elif leading >= 2 and ':' in stripped:
                parts = stripped.split(':', 1)
                key = parts[0].lstrip()
                val = parts[1].strip() if len(parts) > 1 else ''
                if key in ('author', 'version', 'scope', 'auto_invoke', 'allowed-tools'):
                    output.append(key + ': ' + val + '\n')
            i += 1
            continue

        if stripped.startswith('description: >'):
            output.append('description:')
            skip_block = True
            i += 1
            continue

        if skip_block:
            if leading >= 2:
                text = stripped
                if text and not text.startswith('#'):
                    output.append('  ' + text + '\n')
                i += 1
                continue
            else:
                skip_block = False

        if leading >= 2:
            i += 1
            continue

        output.append(line)
    else:
        output.append(line)
    i += 1

with open(dest_file, 'w') as f:
    f.writelines(output)
PYEOF
}

sync_skill() {
    local skill_name="$1"
    local source="$BYTIA_SKILLS/$skill_name"
    local dest="$VENDOR_SKILLS/$skill_name"
    
    if [ ! -d "$source" ]; then
        log_error "Skill '$skill_name' no encontrado en ~/bytia/skills/"
        return 1
    fi
    
    if [ ! -f "$source/SKILL.md" ]; then
        log_error "Skill '$skill_name' no tiene SKILL.md"
        return 1
    fi
    
    log_info "Sincronizando $skill_name..."
    
    if [ -d "$dest" ]; then
        local backup="${dest}.backup.$(date +%s)"
        mv "$dest" "$backup"
        log_info "Backup: $backup"
    fi
    
    mkdir -p "$(dirname "$dest")"
    
    if head -20 "$source/SKILL.md" | grep -q "^metadata:"; then
        log_info "Transformando format agentskills.io -> flat"
        transform_skill "$source" "$dest"
    else
        cp -r "$source" "$dest"
    fi
    
    log_success "$skill_name sincronizado"
}

list_skills() {
    echo ""
    echo "Skills a sincronizar:"
    echo ""
    
    for skill in "${SYNCABLE_SKILLS[@]}"; do
        local source="$BYTIA_SKILLS/$skill"
        if [ -d "$source" ] && [ -f "$source/SKILL.md" ]; then
            echo -e "  ${GREEN}*${NC} $skill"
        else
            echo -e "  ${RED}x${NC} $skill (no encontrado)"
        fi
    done
    echo ""
}

sync_all() {
    log_info "Sincronizando todos los skills..."
    echo ""
    
    local synced=0
    local failed=0
    
    for skill in "${SYNCABLE_SKILLS[@]}"; do
        if sync_skill "$skill"; then
            ((synced++)) || true
        else
            ((failed++)) || true
        fi
    done
    
    echo ""
    log_success "Sincronizados: $synced | Fallidos: $failed"
}

main() {
    if [ ! -d "$BYTIA_SKILLS" ]; then
        log_error "~/bytia/skills/ no existe"
        exit 1
    fi
    
    if [ ! -d "$VENDOR_SKILLS" ]; then
        log_error "vendor/skills/ no existe en el repo"
        exit 1
    fi
    
    if [ $# -eq 0 ]; then
        list_skills
        sync_all
        return
    fi
    
    case "$1" in
        --list|-l)
            list_skills
            ;;
        --sync|-s)
            sync_all
            ;;
        *)
            sync_skill "$1"
            ;;
    esac
}

main "$@"
