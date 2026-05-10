#!/usr/bin/env bash
#MISE description="Symlink home/.gitconfig into $HOME and seed ~/.gitconfig.local"
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.config/dotfiles}"
REPO_GITCONFIG="$DOTFILES_DIR/home/.gitconfig"
REPO_LOCAL_EXAMPLE="$DOTFILES_DIR/home/.gitconfig.local.example"
HOME_GITCONFIG="$HOME/.gitconfig"
HOME_LOCAL="$HOME/.gitconfig.local"

if [[ ! -f "$REPO_GITCONFIG" ]]; then
    echo "FAIL: $REPO_GITCONFIG missing — repo is incomplete" >&2
    exit 1
fi

# --- ~/.gitconfig ---
if [[ -L "$HOME_GITCONFIG" ]]; then
    current_target="$(readlink "$HOME_GITCONFIG")"
    if [[ "$current_target" == "$REPO_GITCONFIG" ]]; then
        echo "OK: ~/.gitconfig already points to repo"
    else
        echo "WARN: ~/.gitconfig symlinked to $current_target — replacing"
        ln -sfn "$REPO_GITCONFIG" "$HOME_GITCONFIG"
        echo "OK: ~/.gitconfig → $REPO_GITCONFIG"
    fi
elif [[ -e "$HOME_GITCONFIG" ]]; then
    backup="$HOME_GITCONFIG.bak.$(date +%Y%m%d-%H%M%S)"
    cp "$HOME_GITCONFIG" "$backup"
    # If the existing file has [user] but no .local file exists, seed local
    # from existing user identity rather than discarding it.
    if [[ ! -e "$HOME_LOCAL" ]] && grep -q '^\[user\]' "$HOME_GITCONFIG"; then
        {
            echo "# Migrated from ~/.gitconfig on $(date -Iseconds)"
            git config --file "$HOME_GITCONFIG" --get-regexp '^user\.' \
                | awk 'NR==1 {print "[user]"} {sub("^user\\.",""); split($0, p, " "); printf "\t%s = %s\n", p[1], substr($0, length(p[1])+2)}'
        } > "$HOME_LOCAL"
        echo "OK: extracted [user] from existing ~/.gitconfig → ~/.gitconfig.local"
    fi
    mv "$HOME_GITCONFIG" "$HOME_GITCONFIG.bak.$(date +%Y%m%d-%H%M%S).orig"
    ln -s "$REPO_GITCONFIG" "$HOME_GITCONFIG"
    echo "OK: backed up + symlinked"
else
    ln -s "$REPO_GITCONFIG" "$HOME_GITCONFIG"
    echo "OK: ~/.gitconfig → $REPO_GITCONFIG (no prior file)"
fi

# --- ~/.gitconfig.local ---
if [[ -e "$HOME_LOCAL" ]]; then
    echo "OK: ~/.gitconfig.local already exists (left untouched)"
elif [[ -f "$REPO_LOCAL_EXAMPLE" ]]; then
    cp "$REPO_LOCAL_EXAMPLE" "$HOME_LOCAL"
    echo "OK: seeded ~/.gitconfig.local from example — edit it with your identity"
fi

# --- sanity ---
if git config --file "$HOME_GITCONFIG" --list >/dev/null 2>&1; then
    echo "OK: ~/.gitconfig parses cleanly"
else
    echo "WARN: ~/.gitconfig failed to parse"
fi

if [[ -z "$(git config --get user.email 2>/dev/null)" ]]; then
    echo "WARN: user.email is empty — edit ~/.gitconfig.local"
fi
