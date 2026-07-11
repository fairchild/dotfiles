#!/usr/bin/env bash
#MISE description="Cross-check installed state against repo expectations"
set -u

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.config/dotfiles}"
worst=0   # 0=OK, 1=WARN, 2=FAIL

ok()   { printf '\033[32mOK\033[0m:   %s\n' "$*"; }
warn() { printf '\033[33mWARN\033[0m: %s\n' "$*"; worst=$(( worst > 1 ? worst : 1 )); }
fail() { printf '\033[31mFAIL\033[0m: %s\n' "$*"; worst=2; }

realpath_py() {
    python3 - "$1" <<'PY'
import os, sys
print(os.path.realpath(os.path.expanduser(sys.argv[1])))
PY
}

# --- ~/.zshrc symlink ---
expected_zshrc="$DOTFILES_DIR/home/.zshrc"
if [[ -L "$HOME/.zshrc" ]] && [[ "$(readlink "$HOME/.zshrc")" == "$expected_zshrc" ]]; then
    ok "$HOME/.zshrc -> $expected_zshrc"
else
    warn "$HOME/.zshrc is not a symlink to the repo (run \`mise run install:zsh\`)"
fi

# --- private ~/.gitconfig loader ---
expected_gitconfig="$DOTFILES_DIR/home/.gitconfig"
if [[ -f "$HOME/.gitconfig" && ! -L "$HOME/.gitconfig" ]]; then
    ok "$HOME/.gitconfig is a private mutable loader"
else
    fail "$HOME/.gitconfig is missing or linked into public source (run \`mise run install:git\`)"
fi

public_include_count="$(git config --file "$HOME/.gitconfig" --get-all include.path 2>/dev/null | grep -Fxc "$expected_gitconfig" || true)"
local_include_count="$(git config --file "$HOME/.gitconfig" --get-all include.path 2>/dev/null | grep -Fxc "$HOME/.gitconfig.local" || true)"
if [[ "$public_include_count" == "1" && "$local_include_count" == "1" ]]; then
    ok "private Git loader includes public base and local overlay exactly once"
else
    fail "private Git loader include topology is incomplete or duplicated"
fi

if git -C "$DOTFILES_DIR" diff --quiet -- home/.gitconfig \
    && git -C "$DOTFILES_DIR" diff --cached --quiet -- home/.gitconfig; then
    ok "public Git base has no local write-through changes"
else
    fail "public Git base changed locally; inspect before publishing"
fi

# --- generated agent runtime ---
expected_agents="$HOME/.agents"
if [[ -d "$expected_agents" && ! -L "$expected_agents" ]]; then
    ok "$HOME/.agents is a real generated runtime directory"
else
    warn "$HOME/.agents is not a real generated runtime directory (run \`mise run install:agents\`)"
fi

for public_asset in prompts scripts; do
    expected_source="$DOTFILES_DIR/agents/shared/$public_asset"
    runtime_asset="$expected_agents/$public_asset"
    if [[ -L "$runtime_asset" ]] && [[ "$(realpath_py "$runtime_asset")" == "$(realpath_py "$expected_source")" ]]; then
        ok "$HOME/.agents/$public_asset links to public source"
    else
        warn "$HOME/.agents/$public_asset is not linked to public source"
    fi
done

if [[ -d "$expected_agents/skills" && ! -L "$expected_agents/skills" ]]; then
    skills_real="$(realpath_py "$expected_agents/skills")"
    dotfiles_real="$(realpath_py "$DOTFILES_DIR")"
    case "$skills_real" in
        "$dotfiles_real"/*) fail "generated skill runtime is inside the public checkout: $skills_real" ;;
        *) ok "generated skill runtime is outside the public checkout" ;;
    esac
else
    warn "$HOME/.agents/skills is not a real generated runtime directory"
fi

for legacy_runtime in "$DOTFILES_DIR/agents/shared/skills" "$DOTFILES_DIR/agents/shared/runtime-backups"; do
    if [[ -e "$legacy_runtime" || -L "$legacy_runtime" ]]; then
        warn "legacy generated runtime remains inside checkout: $legacy_runtime"
    fi
done

for local_overlay in "$HOME/.zshrc.local" "$HOME/.gitconfig.local"; do
    if [[ -f "$local_overlay" && ! -L "$local_overlay" ]]; then
        ok "$local_overlay is private local state"
    else
        warn "$local_overlay is missing or linked; private overlays must be real local files"
    fi
done

# --- pi shared skills topology ---
expected_pi_skills="$HOME/.agents/skills"
if [[ -L "$HOME/.pi/agent/skills" ]] && [[ "$(readlink "$HOME/.pi/agent/skills")" == "$expected_pi_skills" ]]; then
    ok "$HOME/.pi/agent/skills -> $HOME/.agents/skills"
else
    warn "$HOME/.pi/agent/skills is not a symlink to $HOME/.agents/skills (run \`mise run install:agents\`)"
fi

# --- materialized shared skill inventory ---
if "$DOTFILES_DIR/scripts/restore-shared-skills.sh" --check >/dev/null 2>&1; then
    ok "shared skill runtime matches first-party sources and third-party lock"
else
    warn "shared skill runtime is incomplete (run \`mise run install:skills\`)"
fi

# --- git identity present ---
# Plain `git config` follows the private loader's public and local includes.
git_email="$(git config user.email 2>/dev/null || true)"
git_name="$(git config user.name 2>/dev/null || true)"
if [[ -n "$git_email" && -n "$git_name" ]]; then
    ok "git identity: $git_name <$git_email>"
elif [[ -z "$git_email" ]]; then
    fail "git user.email is empty (edit ~/.gitconfig.local)"
else
    warn "git user.name is empty (edit ~/.gitconfig.local)"
fi

# --- repo working tree clean ---
if git -C "$DOTFILES_DIR" diff --quiet && git -C "$DOTFILES_DIR" diff --cached --quiet; then
    ok "$DOTFILES_DIR working tree clean"
else
    warn "$DOTFILES_DIR has uncommitted changes"
fi

# --- repo on master ---
branch="$(git -C "$DOTFILES_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
case "$branch" in
    master|main) ok "$DOTFILES_DIR on $branch" ;;
    "")          fail "$DOTFILES_DIR is not a git checkout" ;;
    *)           warn "$DOTFILES_DIR on '$branch' (not master/main)" ;;
esac

# --- mise version matches pin ---
pinned="$(awk -F'"' '/^version/ {print $2; exit}' "$DOTFILES_DIR/install/pins.toml" 2>/dev/null || true)"
running="v$(mise --version 2>/dev/null | awk '{print $1}' || true)"
if [[ -z "$pinned" ]]; then
    warn "could not read pinned mise version from install/pins.toml"
elif [[ "$running" == "$pinned" ]]; then
    ok "mise on pinned version $pinned"
elif [[ "$running" > "$pinned" ]]; then
    warn "mise $running is ahead of pinned $pinned (local install is newer; bump install/pins.toml if this version is desired)"
else
    warn "mise $running is behind pinned $pinned (run \`./install.sh\` to install the pinned version)"
fi

# --- shell can find core tools ---
for cmd in starship fzf rg fd jq gh; do
    if command -v "$cmd" &>/dev/null; then
        ok "found $cmd"
    else
        warn "$cmd not on PATH (\`mise run install:brew\`?)"
    fi
done

case "$worst" in
    0) printf '\n\033[32mAll OK.\033[0m\n' ;;
    1) printf '\n\033[33mDoctor finished with warnings.\033[0m\n' ;;
    2) printf '\n\033[31mDoctor finished with failures.\033[0m\n' ;;
esac
exit "$worst"
