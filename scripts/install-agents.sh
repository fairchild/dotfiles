#!/usr/bin/env bash
#MISE description="Symlink ~/.agents to the repo-managed shared agent assets"
set -euo pipefail

DOTFILES_DIR="${DOTFILES_DIR:-$HOME/.config/dotfiles}"
REPO_AGENTS="$DOTFILES_DIR/agents/shared"
HOME_AGENTS="$HOME/.agents"

if [[ ! -d "$REPO_AGENTS" ]]; then
    echo "FAIL: $REPO_AGENTS missing — repo is incomplete" >&2
    exit 1
fi

if [[ -L "$HOME_AGENTS" ]]; then
    current_target="$(readlink "$HOME_AGENTS")"
    if [[ "$current_target" == "$REPO_AGENTS" ]]; then
        echo "OK: ~/.agents already points to repo"
    else
        echo "WARN: ~/.agents symlinked to $current_target — replacing"
        ln -sfn "$REPO_AGENTS" "$HOME_AGENTS"
        echo "OK: ~/.agents → $REPO_AGENTS"
    fi
elif [[ -e "$HOME_AGENTS" ]]; then
    backup="$HOME_AGENTS.bak.$(date +%Y%m%d-%H%M%S)"
    mv "$HOME_AGENTS" "$backup"
    ln -s "$REPO_AGENTS" "$HOME_AGENTS"
    echo "OK: backed up old ~/.agents → $backup; symlinked to repo"
else
    ln -s "$REPO_AGENTS" "$HOME_AGENTS"
    echo "OK: ~/.agents → $REPO_AGENTS (no prior directory)"
fi

# Pi should consume the shared skill store through ~/.agents.
PI_SKILLS="$HOME/.pi/agent/skills"
EXPECTED_PI_SKILLS="$HOME_AGENTS/skills"
mkdir -p "$(dirname "$PI_SKILLS")"
if [[ -L "$PI_SKILLS" ]]; then
    current_target="$(readlink "$PI_SKILLS")"
    if [[ "$current_target" == "$EXPECTED_PI_SKILLS" ]]; then
        echo "OK: ~/.pi/agent/skills → ~/.agents/skills"
    else
        echo "WARN: ~/.pi/agent/skills symlinked to $current_target — replacing"
        ln -sfn "$EXPECTED_PI_SKILLS" "$PI_SKILLS"
        echo "OK: ~/.pi/agent/skills → ~/.agents/skills"
    fi
elif [[ -e "$PI_SKILLS" ]]; then
    echo "WARN: ~/.pi/agent/skills exists as a real path; leaving untouched"
else
    ln -s "$EXPECTED_PI_SKILLS" "$PI_SKILLS"
    echo "OK: ~/.pi/agent/skills → ~/.agents/skills"
fi

if [[ -x "$HOME_AGENTS/scripts/check-shared-skills.sh" ]]; then
    "$HOME_AGENTS/scripts/check-shared-skills.sh" >/dev/null
    echo "OK: shared skills audit completed"
else
    echo "WARN: shared skills audit script missing or not executable"
fi
