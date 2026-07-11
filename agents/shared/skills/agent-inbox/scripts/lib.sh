#!/usr/bin/env bash
# Shared helpers for agent-inbox hook scripts.

agent_inbox_root() {
  local common_dir top

  if common_dir=$(git rev-parse --git-common-dir 2>/dev/null); then
    case "$common_dir" in
      /*) ;;
      *)
    top=$(git rev-parse --show-toplevel 2>/dev/null) || top="$PWD"
    common_dir="$top/$common_dir"
    ;;
    esac

    printf '%s/.agents/inbox\n' "$(dirname "$common_dir")"
    return 0
  fi

  printf '%s/.agents/inbox\n' "$PWD"
}
