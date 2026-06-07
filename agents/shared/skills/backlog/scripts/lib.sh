#!/usr/bin/env bash
# Shared helpers for the backlog backend scripts. Sourced, not run.

backlog_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

backlog_claimer() {
  if [[ -n "${CONDUCTOR_WORKSPACE_NAME:-}" ]]; then
    echo "conductor:$CONDUCTOR_WORKSPACE_NAME"
  elif [[ -n "${CMUX_WORKSPACE_ID:-}" ]]; then
    echo "cmux:$CMUX_WORKSPACE_ID"
  else
    echo "$(whoami)@$(hostname -s)"
  fi
}

backlog_branch() { git rev-parse --abbrev-ref HEAD 2>/dev/null; }

# Read backend declaration from backlog/AGENTS.md. Empty if unset.
# Convention: the first backtick-quoted token after the `## Backend` heading
# is the backend name (e.g. `maildir-shared`, `maildir-git`, `github-issues`).
backlog_backend() {
  awk '
    /^## Backend/ { flag=1; next }
    flag && /^## / { exit }
    flag && match($0, /`[a-z][a-z0-9-]*`/) {
      print substr($0, RSTART+1, RLENGTH-2); exit
    }
  ' backlog/AGENTS.md 2>/dev/null | head -1
}

# Read a label name by role from backlog/AGENTS.md `## Labels` section. Returns
# the configured name if found, otherwise the supplied default. The role is
# the pipeline state name (or `failed` for the dead-letter terminal). Format:
#
#   ## Labels
#
#   doing: claimed
#   reviewing: under-review
#   failed: dead-letter
#
# Lines may be bare `role: name` or list items `- role: name`. Comments and
# blanks are ignored. The section ends at the next `##` heading. Backends
# wrap this in their own helpers (e.g. github-issues uses `state_label` /
# `failed_label` with defaults that match the bare names cmd_setup creates).
backlog_label() {
  local role="${1:?role required}"
  local default="${2:?default required}"
  local found
  found=$(awk -v role="$role" '
    /^## Labels/ { flag=1; next }
    flag && /^## / { exit }
    flag {
      line = $0
      sub(/^[[:space:]]*-?[[:space:]]*/, "", line)
      if (match(line, /^[a-zA-Z][a-zA-Z0-9_-]*[[:space:]]*:[[:space:]]*/)) {
        k = substr(line, 1, RLENGTH)
        sub(/[[:space:]]*:[[:space:]]*$/, "", k)
        if (k == role) {
          v = substr(line, RLENGTH + 1)
          sub(/[[:space:]]+$/, "", v); sub(/^[[:space:]]+/, "", v)
          print v; exit
        }
      }
    }
  ' backlog/AGENTS.md 2>/dev/null)
  printf '%s' "${found:-$default}"
}

# Next dir after $1 in the pipeline declared in AGENTS.md.
# Default pipeline: todo -> doing -> done.
backlog_next_dir() {
  local curr="$1"
  awk -v curr="$curr" '
    BEGIN { defaults["todo"]="doing"; defaults["doing"]="done" }
    /^## Pipeline/ { flag=1; next }
    flag && /[a-z]/ {
      parsed=1; n=0
      while (match($0, /[a-z][a-z0-9-]*/)) {
        arr[n++]=substr($0, RSTART, RLENGTH)
        $0=substr($0, RSTART + RLENGTH)
      }
      for (i=0; i<n; i++) if (arr[i]==curr && i+1<n) { print arr[i+1]; exit }
      exit
    }
    END { if (!parsed && curr in defaults) print defaults[curr] }
  ' backlog/AGENTS.md 2>/dev/null
}

# First dir in the pipeline declared in AGENTS.md. Default: todo.
# Used by `add` to land new tasks in the pipeline's intake bucket — a project
# that extends the pipeline (e.g. `inbox -> todo -> doing -> done`) wants new
# tasks to land in `inbox/`, not `todo/`.
backlog_first_dir() {
  awk '
    /^## Pipeline/ { flag=1; next }
    flag && /[a-z]/ {
      if (match($0, /[a-z][a-z0-9-]*/)) { print substr($0, RSTART, RLENGTH); exit }
    }
    END { if (!flag) print "todo" }
  ' backlog/AGENTS.md 2>/dev/null
}

# In-flight dir names from pipeline (excluding intake/terminal dirs). Default: doing.
backlog_inflight_dirs() {
  awk '
    /^## Pipeline/ { flag=1; next }
    flag && /[a-z]/ {
      parsed=1
      while (match($0, /[a-z][a-z0-9-]*/)) {
        d=substr($0, RSTART, RLENGTH)
    if (d != "inbox" && d != "todo" && d != "done" && d != "failed") print d
        $0=substr($0, RSTART + RLENGTH)
      }
      exit
    }
    END { if (!parsed) print "doing" }
  ' backlog/AGENTS.md 2>/dev/null
}

# First in-flight pipeline state — the one a worker enters on claim.
# (Convenience wrapper used by backends that need a single-state reference.)
backlog_first_inflight_dir() {
  backlog_inflight_dirs | head -1
}

# Parse timeout from frontmatter (e.g. "3d") to seconds. Defaults to 7d.
backlog_timeout_seconds() {
  local file="$1"
  local t
  t=$(awk '/^---$/{n++; if(n==2) exit} n==1 && /^timeout:/ {sub(/^timeout:[[:space:]]*/, ""); print; exit}' "$file")
  [[ -z "$t" ]] && t=7d
  local n="${t%[smhdw]*}" unit="${t: -1}"
  case "$unit" in
    s) echo "$n" ;;
    m) echo "$((n*60))" ;;
    h) echo "$((n*3600))" ;;
    d) echo "$((n*86400))" ;;
    w) echo "$((n*604800))" ;;
    *) echo 604800 ;;
  esac
}

# Parse an ISO timestamp into epoch seconds (GNU date or BSD date).
backlog_epoch() {
  local ts="$1"
  date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$ts" +%s 2>/dev/null \
    || gdate -d "$ts" +%s 2>/dev/null
}

# Ensure body divider exists before appending log lines.
backlog_ensure_divider() {
  local file="$1"
  local required=1 count
  if [[ "$(head -n 1 "$file")" == "---" ]]; then
    required=3
  fi
  count=$(grep -cx -- "---" "$file" 2>/dev/null || true)
  if (( count < required )); then
    printf '\n---\n' >> "$file"
  fi
}

# Read priority from frontmatter. Defaults to 999.
backlog_priority() {
  local file="$1" p
  p=$(awk '/^---$/{n++; if(n==2) exit} n==1 && /^priority:/ {sub(/^priority:[[:space:]]*/, ""); print; exit}' "$file" 2>/dev/null)
  [[ -z "$p" ]] && p=999
  echo "$p"
}

# Read dependency slugs from frontmatter. Supports block-form (map) and array-form.
# Prints one slug per line; empty output = no deps.
backlog_deps() {
  local file="$1"
  awk '
    /^---$/ { n++; if (n==2) exit; next }
    n == 1 && /^dependencies:[[:space:]]*$/ { block=1; next }
    n == 1 && /^dependencies:[[:space:]]*\[/ {
      # Inline array form: dependencies: [a, b]
      s = $0
      sub(/^dependencies:[[:space:]]*\[/, "", s); sub(/\].*/, "", s)
      gsub(/[ \t]/, "", s); n_items = split(s, items, ",")
      for (i = 1; i <= n_items; i++) if (items[i] != "") print items[i]
      next
    }
    block && /^[[:space:]]+[A-Za-z0-9_-]+/ {
      line = $0
      sub(/^[[:space:]]+/, "", line); sub(/[:[:space:]].*/, "", line)
      print line; next
    }
    block && /^[^[:space:]]/ { block=0 }
  ' "$file" 2>/dev/null
}

# Returns 0 if every dep slug resolves to a file under done/; 1 otherwise.
backlog_deps_resolved() {
  local file="$1" dep
  while IFS= read -r dep; do
    [[ -z "$dep" ]] && continue
    [[ -f "backlog/done/${dep}.md" ]] || return 1
  done < <(backlog_deps "$file")
  return 0
}

# Guard: bail if not in a git repo.
backlog_require_git() {
  git rev-parse --git-dir >/dev/null 2>&1 \
    || { echo "not inside a git repository" >&2; exit 1; }
}
