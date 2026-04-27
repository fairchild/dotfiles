#!/usr/bin/env bash
#MISE description="Symlink home/zsh fragments into $HOME and seed ~/.zshrc.local"
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.config/dotfiles}"
REPO_ZSHRC="$DOTFILES_DIR/home/.zshrc"
REPO_LOCAL_EXAMPLE="$DOTFILES_DIR/home/.zshrc.local.example"
HOME_ZSHRC="$HOME/.zshrc"
HOME_LOCAL="$HOME/.zshrc.local"

if [[ ! -f "$REPO_ZSHRC" ]]; then
    echo "FAIL: $REPO_ZSHRC missing — repo is incomplete" >&2
    exit 1
fi

# --- ~/.zshrc ---
if [[ -L "$HOME_ZSHRC" ]]; then
    current_target="$(readlink "$HOME_ZSHRC")"
    if [[ "$current_target" == "$REPO_ZSHRC" ]]; then
        echo "OK: ~/.zshrc already points to repo"
    else
        echo "WARN: ~/.zshrc symlinked to $current_target — replacing"
        ln -sfn "$REPO_ZSHRC" "$HOME_ZSHRC"
        echo "OK: ~/.zshrc → $REPO_ZSHRC"
    fi
elif [[ -e "$HOME_ZSHRC" ]]; then
    backup="$HOME_ZSHRC.bak.$(date +%Y%m%d-%H%M%S)"
    mv "$HOME_ZSHRC" "$backup"
    ln -s "$REPO_ZSHRC" "$HOME_ZSHRC"
    echo "OK: backed up old ~/.zshrc → $backup; symlinked to repo"
else
    ln -s "$REPO_ZSHRC" "$HOME_ZSHRC"
    echo "OK: ~/.zshrc → $REPO_ZSHRC (no prior file)"
fi

# --- ~/.zshrc.local ---
if [[ -e "$HOME_LOCAL" ]]; then
    echo "OK: ~/.zshrc.local already exists (left untouched)"
elif [[ -f "$REPO_LOCAL_EXAMPLE" ]]; then
    cp "$REPO_LOCAL_EXAMPLE" "$HOME_LOCAL"
    echo "OK: seeded ~/.zshrc.local from example"
else
    echo "WARN: $REPO_LOCAL_EXAMPLE missing; skipped seeding ~/.zshrc.local"
fi

# --- sanity ---
if zsh -n "$HOME_ZSHRC" 2>/dev/null; then
    echo "OK: ~/.zshrc parses cleanly"
else
    echo "WARN: ~/.zshrc failed syntax check (zsh -n)"
fi
