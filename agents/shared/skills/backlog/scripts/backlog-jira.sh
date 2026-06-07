#!/usr/bin/env bash
# jira backend - backlog tasks live as Jira work items and verbs dispatch to
# Atlassian CLI (`acli`). Jira status is the state bucket; Jira comments carry
# the append-only backlog worklog.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
. "$script_dir/lib.sh"

require_acli() {
  command -v acli >/dev/null 2>&1 \
    || { echo "Atlassian CLI not installed; see https://developer.atlassian.com/cloud/acli/guides/introduction/" >&2; exit 1; }
  command -v jq >/dev/null 2>&1 \
    || { echo "jq not installed; required by jira backend" >&2; exit 1; }
  acli jira auth status >/dev/null 2>&1 \
    || { echo "acli is not authenticated for Jira; run: acli jira auth login --web" >&2; exit 1; }
}

section_value() {
  local section="${1:?section required}"
  local key="${2:?key required}"
  local default="${3:-}"
  local found
  found=$(awk -v heading="## ${section}" -v key="$key" '
    $0 == heading { flag=1; next }
    flag && /^## / { exit }
    flag {
      line = $0
      sub(/^[[:space:]]*-?[[:space:]]*/, "", line)
      if (index(line, key ":") == 1) {
        v = substr(line, length(key) + 2)
        sub(/^[[:space:]]+/, "", v); sub(/[[:space:]]+$/, "", v)
        print v; exit
      }
    }
  ' backlog/AGENTS.md 2>/dev/null)
  printf '%s' "${found:-$default}"
}

jira_config() { section_value Jira "$1" "${2:-}"; }
jira_status() { section_value Statuses "$1" "${2:-}"; }

jira_status_default() {
  case "$1" in
    todo) echo "To Do" ;;
    doing) echo "In Progress" ;;
    done) echo "Done" ;;
    failed) echo "Failed" ;;
    *) echo "$1" ;;
  esac
}

jira_project() {
  local project; project=$(jira_config project "")
  [[ -n "$project" ]] || { echo "missing Jira project in backlog/AGENTS.md (## Jira project: KEY)" >&2; exit 1; }
  printf '%s' "$project"
}

jira_type() { jira_config type Task; }
jira_label() { jira_config label backlog; }

jql_quote() {
  local value="${1//\"/\\\"}"
  printf '"%s"' "$value"
}

jira_jql() {
  local explicit project label
  explicit=$(jira_config jql "")
  if [[ -n "$explicit" ]]; then
    printf '%s' "$explicit"
    return
  fi
  project=$(jira_project)
  label=$(jira_label)
  if [[ -n "$label" ]]; then
    printf 'project = %s AND labels = %s' "$project" "$(jql_quote "$label")"
  else
    printf 'project = %s' "$project"
  fi
}

jira_status_for_state() {
  local state="${1:?state required}"
  if [[ "$state" == "cancelled" ]]; then
    jira_status cancelled "$(jira_status done "$(jira_status_default done)")"
  else
    jira_status "$state" "$(jira_status_default "$state")"
  fi
}

first_inflight_state() { backlog_first_inflight_dir; }

jira_status_jql() {
  local status="${1:?status required}"
  printf '(%s) AND status = %s' "$(jira_jql)" "$(jql_quote "$status")"
}

jira_inflight_jql() {
  local statuses="" state status
  while IFS= read -r state; do
    [[ -z "$state" ]] && continue
    status=$(jira_status_for_state "$state")
    [[ -n "$statuses" ]] && statuses+=", "
    statuses+="$(jql_quote "$status")"
  done < <(backlog_inflight_dirs)
  printf '(%s) AND status in (%s)' "$(jira_jql)" "$statuses"
}

jira_search_json() {
  local jql="${1:?jql required}"
  local fields="${2:-key,summary,status}"
  local limit="${3:-100}"
  acli jira workitem search --jql "$jql" --fields "$fields" --limit "$limit" --json
}

jira_view_json() {
  local key="${1:?key required}"
  local fields="${2:-key,status,summary,description}"
  acli jira workitem view "$key" --fields "$fields" --json
}

validate_key() {
  local key="${1:?work item key required}"
  [[ "$key" =~ ^[A-Za-z][A-Za-z0-9]+-[0-9]+$ ]] \
    || { echo "expected Jira work item key like PROJ-123 (got: ${key})" >&2; return 1; }
  jira_view_json "$key" key >/dev/null 2>&1 \
    || { echo "no such Jira work item: ${key}" >&2; return 1; }
  printf '%s' "$key"
}

post_log() {
  local key="$1" line="$2"
  acli jira workitem comment create --key "$key" --body "$line" >/dev/null
}

transition_key() {
  local key="$1" status="$2"
  acli jira workitem transition --key "$key" --status "$status" --yes >/dev/null
}

jira_description_text() {
  local key="$1"
  jira_view_json "$key" description | jq -r '
    def textify:
      if type == "string" then .
      elif . == null then ""
      else ([. | .. | objects | .text? // empty] | join("")) end;
    (.fields.description? // .description? // "") | textify
  '
}

jira_comment_bodies() {
  local key="$1"
  jira_view_json "$key" comment | jq -r '
    def textify:
      if type == "string" then .
      elif . == null then ""
      else ([. | .. | objects | .text? // empty] | join("")) end;
    def comments:
      if (.fields.comment.comments? != null) then .fields.comment.comments
      elif ((.fields.comment? // null) | type) == "array" then .fields.comment
      elif (.comment.comments? != null) then .comment.comments
      elif ((.comments? // null) | type) == "array" then .comments
      else [] end;
    comments | sort_by(.created // .createdAt // .updated // "") | .[].body | textify
  '
}

worklog_lines() {
  local key="$1"
  jira_comment_bodies "$key" | grep -E '^- [0-9TZ:-]+ ' || true
}

claim_winner_branch() {
  local key="$1"
  local first; first=$(first_inflight_state)
  worklog_lines "$key" | awk -v first="$first" '
    function branch_of(line,    p) {
      p = match(line, /branch=[^ ]+/)
      return p ? substr(line, RSTART+7, RLENGTH-7) : ""
    }
    /retried/ { winner = ""; next }
    $0 ~ ("advanced to=" first "( |$)") {
      if (winner == "") winner = branch_of($0)
    }
    /rescued/ {
      b = branch_of($0); if (b != "") winner = b
    }
    END { if (winner != "") print winner }
  '
}

item_status_name() {
  local key="$1"
  jira_view_json "$key" key,status | jq -r '
    .fields.status.name // .status.name // .fields.status // .status // empty
  '
}

pipeline_state_for_status() {
  local status="${1:?status required}"
  local state expected
  expected=$(jira_status_for_state todo)
  [[ "$status" == "$expected" ]] && { echo todo; return; }
  while IFS= read -r state; do
    [[ -z "$state" ]] && continue
    expected=$(jira_status_for_state "$state")
    [[ "$status" == "$expected" ]] && { echo "$state"; return; }
  done < <(backlog_inflight_dirs)
  expected=$(jira_status_for_state done)
  [[ "$status" == "$expected" ]] && { echo done; return; }
  expected=$(jira_status_for_state cancelled)
  [[ "$status" == "$expected" ]] && { echo done; return; }
  expected=$(jira_status_for_state failed)
  [[ "$status" == "$expected" ]] && { echo failed; return; }
  echo unknown
}

pipeline_state() {
  local key="$1" status
  status=$(item_status_name "$key")
  [[ -n "$status" ]] || { echo "unknown"; return; }
  pipeline_state_for_status "$status"
}

pick_takeable() {
  local todo_status jql
  todo_status=$(jira_status_for_state todo)
  jql=$(jira_status_jql "$todo_status")
  jira_search_json "$jql" "key,summary,status,description,updated" 1000 \
    | jq -r '
        def items:
          if type == "array" then .
          elif .issues? then .issues
          elif .values? then .values
          elif .items? then .items
          elif ((.data? // null) | type) == "array" then .data
          else [] end;
        def key: .key // .issueKey // .id // .fields.key // empty;
        def description:
          (.fields.description? // .description? // "") as $d
          | if ($d | type) == "string" then $d
            elif $d == null then ""
            else ([$d | .. | objects | .text? // empty] | join("")) end;
        def updated: .fields.updated // .updated // .updatedAt // "";
        [items[] | {k: key, p: (try (description | capture("(^|\\n)priority:[[:space:]]*(?<v>\\d+)").v | tonumber) catch 999), u: updated}]
        | map(select(.k != ""))
        | sort_by([.p, (try (.u | fromdateiso8601 * -1) catch 0)])
        | .[0].k // empty
      '
}

status_state_map_json() {
  {
    printf '%s\t%s\n' "$(jira_status_for_state todo)" todo
    local state
    while IFS= read -r state; do
      [[ -n "$state" ]] && printf '%s\t%s\n' "$(jira_status_for_state "$state")" "$state"
    done < <(backlog_inflight_dirs)
    printf '%s\t%s\n' "$(jira_status_for_state done)" done
    printf '%s\t%s\n' "$(jira_status_for_state cancelled)" done
    printf '%s\t%s\n' "$(jira_status_for_state failed)" failed
  } | jq -Rn 'reduce inputs as $line ({}; ($line | split("\t")) as $p | .[$p[0]] = $p[1])'
}

bucket_init_json() {
  {
    printf '%s\n' todo
    backlog_inflight_dirs
    printf '%s\n' done
    printf '%s\n' failed
    printf '%s\n' unknown
  } | jq -Rn 'reduce inputs as $k ({}; .[$k] = 0)'
}

output_order_json() {
  {
    printf '%s\n' todo
    backlog_inflight_dirs
    printf '%s\n' done
    printf '%s\n' failed
    printf '%s\n' unknown
  } | jq -Rn '[inputs]'
}

cmd_setup() {
  require_acli
  [[ -f backlog/AGENTS.md ]] && {
    echo "backlog/AGENTS.md exists - refusing to overwrite" >&2; exit 1
  }

  local pipeline="todo -> doing -> done"
  local project="" type="Task" label="backlog" jql=""
  local arg
  for arg in "$@"; do
    case "$arg" in
      --pipeline=*) pipeline="${arg#--pipeline=}" ;;
    esac
  done

  local -a inflight_list=()
  local tok
  while IFS= read -r tok; do
    case "$tok" in todo|done|failed|inbox|'') ;; *) inflight_list+=("$tok") ;; esac
  done < <(echo "$pipeline" | grep -oE '[a-z][a-z0-9-]*')
  [[ ${#inflight_list[@]} -eq 0 ]] && {
    echo "pipeline must declare at least one in-flight stage (got: $pipeline)" >&2
    exit 1
  }

  is_valid_status_role() {
    local target="$1" s
    case "$target" in todo|done|failed|cancelled) return 0 ;; esac
    for s in "${inflight_list[@]}"; do
      [[ "$s" == "$target" ]] && return 0
    done
    return 1
  }

  local -a status_args=()
  for arg in "$@"; do
    case "$arg" in
      --backend=*|--pipeline=*) ;;
      --project=*) project="${arg#--project=}" ;;
      --type=*) type="${arg#--type=}" ;;
      --label=*) label="${arg#--label=}" ;;
      --jql=*) jql="${arg#--jql=}" ;;
      --todo-status=*) status_args+=("todo=${arg#--todo-status=}") ;;
      --done-status=*) status_args+=("done=${arg#--done-status=}") ;;
      --failed-status=*) status_args+=("failed=${arg#--failed-status=}") ;;
      --cancelled-status=*) status_args+=("cancelled=${arg#--cancelled-status=}") ;;
      --status-*)
        local rest="${arg#--status-}"
        local state="${rest%%=*}"
        local name="${rest#*=}"
        [[ "$state" == "$rest" || -z "$state" || -z "$name" ]] && {
          echo "malformed flag: $arg (want --status-<state>=<jira-status>)" >&2; exit 1
        }
        is_valid_status_role "$state" || {
          echo "unknown status role: $state (valid: todo ${inflight_list[*]} done failed cancelled)" >&2; exit 1
        }
        status_args+=("${state}=${name}")
        ;;
      *) echo "unknown setup flag: $arg" >&2; exit 1 ;;
    esac
  done

  [[ -n "$project" ]] || {
    echo "jira setup requires --project=<JIRA_PROJECT_KEY>" >&2
    exit 2
  }
  if [[ -z "$jql" ]]; then
    if [[ -n "$label" ]]; then
      jql="project = ${project} AND labels = $(jql_quote "$label")"
    else
      jql="project = ${project}"
    fi
  fi

  setup_status_for_state() {
    local target="$1" pair k v result
    result="$(jira_status_default "$target")"
    if [[ "$target" == "cancelled" ]]; then
      result="$(setup_status_for_state done)"
    fi
    if [[ ${#status_args[@]} -gt 0 ]]; then
      for pair in "${status_args[@]}"; do
        k="${pair%%=*}"; v="${pair#*=}"
        [[ "$k" == "$target" ]] && result="$v"
      done
    fi
    printf '%s' "$result"
  }

  local pipeline_line="todo"
  local statuses_section="todo: $(setup_status_for_state todo)"$'\n'
  local state_table="| todo | \`$(setup_status_for_state todo)\` | available to claim |"$'\n'
  local s
  for s in "${inflight_list[@]}"; do
    pipeline_line+=" -> ${s}"
    statuses_section+="${s}: $(setup_status_for_state "$s")"$'\n'
    state_table+="| ${s} | \`$(setup_status_for_state "$s")\` | claimed / in flight |"$'\n'
  done
  pipeline_line+=" -> done"
  statuses_section+="done: $(setup_status_for_state done)"$'\n'
  statuses_section+="failed: $(setup_status_for_state failed)"$'\n'
  statuses_section+="cancelled: $(setup_status_for_state cancelled)"
  state_table+="| done | \`$(setup_status_for_state done)\` | completed |"$'\n'
  state_table+="| failed | \`$(setup_status_for_state failed)\` | dead-lettered; retry may return to todo |"$'\n'
  state_table+="| cancelled | \`$(setup_status_for_state cancelled)\` | counted as done; log line discriminates |"

  mkdir -p backlog
  cat > backlog/AGENTS.md <<EOF
# backlog/

\`CLAUDE.md\` here is a symlink to this file - read one, not both.

Task state lives in Jira work items returned by this membership JQL:

    ${jql}

The backlog skill uses Atlassian CLI (\`acli jira workitem ...\`) as the
convenience client. Jira is still the source of truth; humans can operate
directly in Jira if they preserve the worklog comment convention below.

## Jira

project: ${project}
type: ${type}
label: ${label}
jql: ${jql}

## Backend

\`jira\` - see the \`backlog\` skill's \`references/backends/jira.md\` for setup and script behavior.

## Pipeline

${pipeline_line}

\`advance\` transitions the work item to the next Jira status named in \`## Statuses\`.
Jira statuses and transition rules must already exist in the project workflow.

## Statuses

${statuses_section}

## State mapping

| Backlog state | Jira status | Meaning |
|---|---|---|
${state_table}

## Worklog

Every state transition and progress note is one Jira comment, in this shape:

    - <ISO-8601 ts> <verb> [args] | <trail>

The branch is the claim identity because agents may share one Jira account.

## ROADMAP

Strategic counterpart at \`backlog/ROADMAP.md\`. See the \`backlog\` skill's \`references/roadmap.md\`.
EOF
  ln -sf AGENTS.md backlog/CLAUDE.md
  [[ -f backlog/ROADMAP.md ]] || cat > backlog/ROADMAP.md <<'EOF'
# ROADMAP

## Intent
<!-- One paragraph. -->

## Principles
<!-- 3-7 short statements. -->

## Current Focus
<!-- 1-3 paragraphs. -->

## Priorities
<!-- Ordered named arcs. -->

## Non-goals
<!-- What we are explicitly not doing right now. -->
EOF
  git add backlog/AGENTS.md backlog/CLAUDE.md backlog/ROADMAP.md
  git commit -m "setup backlog (jira; project=${project})"
}

cmd_add() {
  require_acli
  local title="${1:?title required}"
  local category="${2:-}"
  [[ -n "$category" ]] && title="${title}-${category}"
  local project type label body out key
  project=$(jira_project)
  type=$(jira_type)
  label=$(jira_label)
  body=$'# '"${title}"$'\n\n[problem, decisions, phases, acceptance]\n\n---'
  local -a cmd=(acli jira workitem create --summary "$title" --project "$project" --type "$type" --description "$body" --json)
  [[ -n "$label" ]] && cmd+=(--label "$label")
  out=$("${cmd[@]}")
  key=$(jq -r 'if type == "array" then .[0] else . end | .key // .issueKey // .id // .fields.key // empty' <<<"$out" 2>/dev/null || true)
  if [[ -n "$key" ]]; then
    printf '%s\n' "$key"
  else
    printf '%s\n' "$out"
  fi
}

cmd_take() {
  require_acli
  local id="${1:-}"
  local key
  if [[ -n "$id" ]]; then
    key=$(validate_key "$id") || exit 1
  else
    key=$(pick_takeable)
    [[ -z "$key" ]] && { echo "no available tasks" >&2; exit 0; }
  fi

  local curr; curr=$(pipeline_state "$key")
  [[ "$curr" == "todo" ]] || {
    echo "${key} is not takeable (state=${curr}, status=$(item_status_name "$key"))" >&2
    exit 1
  }

  local ts claimer branch first first_status
  ts=$(backlog_now); claimer=$(backlog_claimer); branch=$(backlog_branch)
  first=$(first_inflight_state); first_status=$(jira_status_for_state "$first")
  post_log "$key" "- ${ts} advanced to=${first} claimer=${claimer} branch=${branch}"
  transition_key "$key" "$first_status"

  local winner; winner=$(claim_winner_branch "$key")
  if [[ "$winner" != "$branch" ]]; then
    echo "claim conflict on ${key}: won by branch=${winner}" >&2; exit 1
  fi
  printf '%s\n' "$key"
}

cmd_advance() {
  require_acli
  local id="${1:?Jira work item key required}"
  local key; key=$(validate_key "$id") || exit 1
  local curr; curr=$(pipeline_state "$key")
  case "$curr" in
    todo)
      cmd_take "$key"
      return
      ;;
    done|failed)
      echo "no forward step from ${curr}: ${key}" >&2
      exit 1
      ;;
    unknown)
      echo "unknown Jira status for ${key}: $(item_status_name "$key")" >&2
      exit 1
      ;;
  esac

  local next; next=$(backlog_next_dir "$curr")
  [[ -n "$next" ]] || { echo "no next state from ${curr} in declared pipeline" >&2; exit 1; }
  local ts line status
  ts=$(backlog_now)
  if [[ "$next" == "done" ]]; then
    line="- ${ts} advanced to=done"
    local pr_url
    pr_url=$(gh pr view --json url -q .url 2>/dev/null || true)
    [[ -n "$pr_url" ]] && line+=" | PR=${pr_url}"
    post_log "$key" "$line"
  else
    post_log "$key" "- ${ts} advanced to=${next}"
  fi
  status=$(jira_status_for_state "$next")
  transition_key "$key" "$status"
  printf '%s\n' "$key"
}

current_claim() {
  local branch; branch=$(backlog_branch)
  local -a hits=()
  local key
  while IFS= read -r key; do
    [[ -z "$key" ]] && continue
    local winner; winner=$(claim_winner_branch "$key")
    [[ "$winner" == "$branch" ]] && hits+=("$key")
  done < <(
    jira_search_json "$(jira_inflight_jql)" "key,status" 200 \
      | jq -r '
          def items:
            if type == "array" then .
            elif .issues? then .issues
            elif .values? then .values
            elif .items? then .items
            elif ((.data? // null) | type) == "array" then .data
            else [] end;
          items[] | .key // .issueKey // .id // .fields.key // empty
        '
  )
  case "${#hits[@]}" in
    1) printf '%s' "${hits[0]}" ;;
    0) echo "no in-flight claim for branch=${branch}" >&2; return 1 ;;
    *) echo "ambiguous: ${#hits[@]} in-flight claims for branch=${branch}" >&2; return 1 ;;
  esac
}

cmd_progress() {
  require_acli
  local note="${1:?note required}"
  local key; key=$(current_claim) || exit 1
  local ts; ts=$(backlog_now)
  post_log "$key" "- ${ts} progress | ${note}"
  printf '%s\n' "$key"
}

cmd_cancel() {
  require_acli
  local id="${1:?Jira work item key required}" reason="${2:?reason required}"
  local key; key=$(validate_key "$id") || exit 1
  local ts status
  ts=$(backlog_now)
  post_log "$key" "- ${ts} cancelled | ${reason}"
  status=$(jira_status_for_state cancelled)
  transition_key "$key" "$status"
}

cmd_fail() {
  require_acli
  local id="${1:?Jira work item key required}" reason="${2:?reason required}"
  local key; key=$(validate_key "$id") || exit 1
  local ts status
  ts=$(backlog_now)
  post_log "$key" "- ${ts} failed | ${reason}"
  status=$(jira_status_for_state failed)
  transition_key "$key" "$status"
}

cmd_rescue() {
  require_acli
  local id="${1:?Jira work item key required}"
  local key; key=$(validate_key "$id") || exit 1
  local curr; curr=$(pipeline_state "$key")
  case "$curr" in
    todo|done|failed|unknown)
      echo "${key} is not an in-flight task (state=${curr})" >&2
      exit 1
      ;;
  esac

  local first; first=$(first_inflight_state)
  worklog_lines "$key" | grep -qE "(advanced to=${first}( |\$)|rescued)" \
    || { echo "no prior claim line on ${key}" >&2; exit 1; }
  local last_line; last_line=$(worklog_lines "$key" \
    | grep -E '(advanced to=|progress|rescued)' | tail -1)
  [[ -n "$last_line" ]] || { echo "no activity on ${key}" >&2; exit 1; }
  local last_ts; last_ts=$(awk '{print $2}' <<<"$last_line")
  local ep; ep=$(backlog_epoch "$last_ts" 2>/dev/null || true)
  [[ -n "$ep" ]] || { echo "unparseable timestamp: $last_ts" >&2; exit 1; }

  local tmp; tmp=$(mktemp)
  jira_description_text "$key" > "$tmp"
  local secs; secs=$(backlog_timeout_seconds "$tmp"); rm -f "$tmp"
  (( $(date -u +%s) - ep > secs )) \
    || { echo "claim still active; refusing rescue" >&2; exit 1; }

  local ts claimer branch
  ts=$(backlog_now); claimer=$(backlog_claimer); branch=$(backlog_branch)
  post_log "$key" "- ${ts} rescued claimer=${claimer} branch=${branch}"
  local winner; winner=$(claim_winner_branch "$key")
  if [[ "$winner" != "$branch" ]]; then
    echo "rescue conflict on ${key}: won by branch=${winner}" >&2; exit 1
  fi
}

cmd_retry() {
  require_acli
  local id="${1:?Jira work item key required}" reason="${2:?reason required}"
  local key; key=$(validate_key "$id") || exit 1
  local curr; curr=$(pipeline_state "$key")
  [[ "$curr" == "failed" ]] || { echo "not in failed state: ${key}" >&2; exit 1; }
  transition_key "$key" "$(jira_status_for_state todo)"
  local ts; ts=$(backlog_now)
  post_log "$key" "- ${ts} retried | ${reason}"
}

cmd_status() {
  require_acli
  local status_map bucket_init order
  status_map=$(status_state_map_json)
  bucket_init=$(bucket_init_json)
  order=$(output_order_json)
  jira_search_json "$(jira_jql)" "key,status" 1000 \
    | jq -r --argjson stateMap "$status_map" \
            --argjson init "$bucket_init" \
            --argjson order "$order" '
        def items:
          if type == "array" then .
          elif .issues? then .issues
          elif .values? then .values
          elif .items? then .items
          elif ((.data? // null) | type) == "array" then .data
          else [] end;
        def status: .fields.status.name // .status.name // .fields.status // .status // "";
        reduce items[] as $i ($init;
          ($stateMap[($i | status)] // "unknown") as $bucket
          | .[$bucket] += 1
        )
        | . as $b
        | $order
        | map("\(.): \($b[.] // 0)")
        | .[]
      '
}

cmd_maintain() {
  echo "maintain: load ~/.claude/skills/backlog/references/maintain.md and references/backends/jira.md" >&2
  echo "(advisory walk; Jira workflows vary by project)"
}

cmd="${1:-}"
shift || true
case "$cmd" in
  setup)    cmd_setup "$@" ;;
  add)      cmd_add "$@" ;;
  take)     cmd_take "$@" ;;
  advance)  cmd_advance "$@" ;;
  progress) cmd_progress "$@" ;;
  cancel)   cmd_cancel "$@" ;;
  fail)     cmd_fail "$@" ;;
  rescue)   cmd_rescue "$@" ;;
  retry)    cmd_retry "$@" ;;
  status)   cmd_status "$@" ;;
  maintain) cmd_maintain "$@" ;;
  *)        echo "unknown subcommand: $cmd" >&2; exit 1 ;;
esac
