#!/usr/bin/env bash
# SessionStart hook: summarize unread inbox messages so the agent sees them as initial context.
# Agent name from $CLAUDE_SESSION_NAME, fallback to "orchestrator".
# Silent when empty. Designed to be fast (<200ms).

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
. "$script_dir/lib.sh"

inbox_root=$(agent_inbox_root)
agent="${CLAUDE_SESSION_NAME:-orchestrator}"
inbox="$inbox_root/$agent/new"

[[ -d "$inbox" ]] || exit 0

# Collect .md files — fast glob, no find
shopt -s nullglob
files=("$inbox"/*.md)
shopt -u nullglob

count=${#files[@]}
[[ $count -eq 0 ]] && exit 0

echo "📬 ${count} unread in ${inbox_root}/${agent}/new/"
echo ""

for f in "${files[@]}"; do
  name=$(basename "$f")
  # Extract sender from frontmatter (first 'from:' line)
  from=$(awk '/^from:/{print $2; exit}' "$f")
  # Extract first non-frontmatter, non-blank line as subject
  subject=$(awk 'BEGIN{in_fm=0} /^---$/{in_fm=!in_fm; next} in_fm{next} /^$/{next} {print; exit}' "$f")
  printf "  • [%s] %s — %s\n" "${from:-unknown}" "${subject:0:80}" "$name"
done

echo ""
echo "Read with: cat \"${inbox_root}/${agent}/new/<file>\""
