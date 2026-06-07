#!/usr/bin/env bash
# Stop hook: notify agent of unread inbox messages.
# Scans the repo-shared inbox root. Silent when empty.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
. "$script_dir/lib.sh"

inbox_root=$(agent_inbox_root)
shopt -s nullglob
files=("$inbox_root"/*/new/*.md)
shopt -u nullglob
count=${#files[@]}
[[ "$count" -eq 0 ]] && exit 0

echo "📬 ${count} unread in ${inbox_root}/ — cat to read, mv to archive/ when done"
