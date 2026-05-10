# 20-aliases.zsh — interactive shortcuts.
# Folded from the live ~/.zshrc. Mathiasbynens-vintage .aliases is in legacy/
# and not sourced; resurrect entries here case-by-case if still useful.

# Development shortcuts.
alias va="source .venv/bin/activate"
alias be='bundle exec'
alias k=kubectl
alias python=python3
alias tree='tree -C --gitignore'
alias ll='ls -l'
alias demo='mask --maskfile README.md'
alias g='git'

# Docker.
alias c='docker compose'
alias run='docker-compose run --rm'

# AI teammates (provided by dotclaude skills).
alias team='~/.claude/skills/team-memory/scripts/launch.sh'
alias scout='~/.claude/skills/team-memory/scripts/launch.sh --persona scout'
