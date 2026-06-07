#!/usr/bin/env bash
# Backlog dispatch entrypoint. Detects backend from backlog/AGENTS.md and
# delegates to the matching implementation. The `setup` subcommand is special:
# it runs here because AGENTS.md doesn't exist yet.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
. "$script_dir/lib.sh"

usage() {
  cat <<EOF
backlog — task tracker shaped like a maildir

Usage:
  backlog setup [--backend=maildir-git|maildir-shared|github-issues|jira]
  backlog add <slug> [category]
  backlog take [slug]
  backlog advance <slug>
  backlog progress <note>
  backlog cancel <slug> <reason>
  backlog fail <slug> <reason>
  backlog rescue <slug>
  backlog retry <slug> <reason>
  backlog status
  backlog maintain

Backend is read from backlog/AGENTS.md (## Backend section). Default: maildir-git.
See ~/.claude/skills/backlog/SKILL.md for the full surface.
EOF
}

cmd="${1:-}"
shift || true

if [[ "$cmd" == "" || "$cmd" == "-h" || "$cmd" == "--help" ]]; then
  usage; exit 0
fi

backlog_require_git

# Operate at the worktree root so `backlog/...` paths resolve correctly
# regardless of which subdirectory the operator was in when invoking.
cd "$(git rev-parse --show-toplevel)"

# `setup` runs in the entrypoint — AGENTS.md doesn't exist yet.
if [[ "$cmd" == "setup" ]]; then
  backend=""
  for arg in "$@"; do
    case "$arg" in
      --backend=*) backend="${arg#--backend=}" ;;
    esac
  done
  if [[ -z "$backend" ]]; then
    # Heuristic hint, but don't auto-pick — force the operator to choose so
    # the decision is recorded.
    wt_count=$(git worktree list 2>/dev/null | wc -l | tr -d ' ')
    hint="maildir-git (single worktree)"
    [[ "$wt_count" -gt 1 ]] && hint="maildir-shared (>1 worktree detected)"
    cat >&2 <<EOF
setup requires --backend=<maildir-git|maildir-shared|github-issues|jira>.

  maildir-git    — everything committed; claim is \`git mv\`. Single-worktree friendly.
  maildir-shared — todo/done committed; in-flight set lives in git-common-dir
                   shared across worktrees. Atomic claim via O_EXCL.
  github-issues  — tasks live as GitHub Issues on the current repo's remote;
                   verbs dispatch to \`gh\`. Cross-machine. Requires gh auth.
  jira           — tasks live as Jira work items; verbs dispatch to \`acli jira workitem\`; requires acli auth.

This clone has $wt_count worktree(s). Likely fit: $hint.
EOF
    exit 2
  fi
  case "$backend" in
    maildir-git|maildir-shared|github-issues|jira) ;;
    *) echo "unknown backend: $backend (expected maildir-git, maildir-shared, github-issues, or jira)" >&2; exit 1 ;;
  esac
  impl="$script_dir/backlog-${backend}.sh"
  [[ -x "$impl" ]] || { echo "missing impl: $impl" >&2; exit 1; }
  exec "$impl" setup "$@"
fi

# Every other verb dispatches by declared backend.
backend="$(backlog_backend)"
[[ -z "$backend" ]] && backend="maildir-git"

impl="$script_dir/backlog-${backend}.sh"
[[ -x "$impl" ]] || { echo "unknown backend '$backend' — no $impl" >&2; exit 1; }

exec "$impl" "$cmd" "$@"
