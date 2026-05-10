#!/usr/bin/env bash
#MISE description="Cross-check installed state against repo expectations"
set -u

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.config/dotfiles}"
worst=0   # 0=OK, 1=WARN, 2=FAIL

ok()   { printf '\033[32mOK\033[0m:   %s\n' "$*"; }
warn() { printf '\033[33mWARN\033[0m: %s\n' "$*"; worst=$(( worst > 1 ? worst : 1 )); }
fail() { printf '\033[31mFAIL\033[0m: %s\n' "$*"; worst=2; }

# --- ~/.zshrc symlink ---
expected_zshrc="$DOTFILES_DIR/home/.zshrc"
if [[ -L "$HOME/.zshrc" ]] && [[ "$(readlink "$HOME/.zshrc")" == "$expected_zshrc" ]]; then
    ok "~/.zshrc → $expected_zshrc"
else
    warn "~/.zshrc is not a symlink to the repo (run \`mise run install:zsh\`)"
fi

# --- ~/.gitconfig symlink ---
expected_gitconfig="$DOTFILES_DIR/home/.gitconfig"
if [[ -L "$HOME/.gitconfig" ]] && [[ "$(readlink "$HOME/.gitconfig")" == "$expected_gitconfig" ]]; then
    ok "~/.gitconfig → $expected_gitconfig"
else
    warn "~/.gitconfig is not a symlink to the repo (run \`mise run install:git\`)"
fi

# --- git identity present ---
# Use plain `git config` (no --global) so [include]ed files like
# ~/.gitconfig.local are followed. `git config --global --list` only reads
# the literal $HOME/.gitconfig file and won't surface included entries.
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
    warn "mise $running is ahead of pinned $pinned (bumper PR likely landed; run \`mise run sync\`)"
else
    warn "mise $running is behind pinned $pinned (run \`./install.sh\` to re-pin)"
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
