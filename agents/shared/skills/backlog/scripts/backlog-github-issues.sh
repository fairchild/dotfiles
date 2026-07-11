#!/usr/bin/env bash
# github-issues backend — backlog tasks live as GitHub Issues on the current
# repo's remote. Verb semantics are unchanged from maildir; storage moves from
# local files to `gh`. The repo's open issues *are* the backlog — there is no
# separation between "backlog tasks" and "other issues." Anything open is
# takeable. Non-conformant issues (random feature requests, dormant bug
# reports) get handled as they're encountered, not gated by a marker label.
#
# Tasks are referenced by GitHub issue number — the platform's native
# identifier. `take 42` and `take #42` both work; titles are free text and
# the operator/agent reads them out of `gh issue list` to know which number
# to grab. No slug labels, no parallel identifier scheme.
#
# State derives from GitHub-native signals where it can, falling back to
# labels only where the platform can't encode the distinction. The state
# machine is the pipeline declared in `backlog/AGENTS.md` (default:
# `todo → doing → done`); each in-flight pipeline stage maps to a label
# (default = state name; configurable via `## Labels`). For the default
# pipeline:
#
#   todo   = open,   no  `<first-stage>` label
#   doing  = open,   has `<first-stage>` label
#   done   = closed, no  `<failed>` label
#   failed = closed, has `<failed>` label
#
# For a pipeline like `todo → doing → reviewing → done`, `advance` walks the
# in-flight stages one label at a time before closing.
#
# `cancel` and ordinary `done` both close the issue; they're discriminated by
# the worklog comment (and by GitHub's own close reason — `completed` vs
# `not planned`). Status lumps them, matching the maildir backends.
#
# Claim discriminator is the **branch**, not the assignee. Agents often share
# a GitHub identity (one PAT, many workers), so assignee can't tell two
# workers apart; branch usually can. `take` posts the claim comment first,
# adds the first-stage label, then re-reads comments — the earliest
# `advanced to=<first-stage>` line since the most recent `retried` comment
# wins. If the winner's `branch=` matches ours, the claim is ours; otherwise
# we lost the race and exit non-zero. Intermediate `advanced to=` lines
# (stage→stage) are not claim events and don't affect ownership.
#
# Worklog format matches the maildir backends — each state transition or
# progress note is one `- <ts> <verb> ...` line, posted as an issue comment.
# `gh issue view --json comments` reconstructs the same chronological log a
# maildir worker would see by reading the file body below the divider.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
. "$script_dir/lib.sh"

require_gh() {
  command -v gh >/dev/null 2>&1 \
    || { echo "gh CLI not installed; see https://cli.github.com" >&2; exit 1; }
  command -v jq >/dev/null 2>&1 \
    || { echo "jq not installed; required by github-issues backend" >&2; exit 1; }
  gh auth status >/dev/null 2>&1 \
    || { echo "gh not authenticated; run: gh auth login" >&2; exit 1; }
}

# Lazy label-name lookups, pipeline-aware. The `## Labels` section in
# backlog/AGENTS.md maps state name → label name; defaults are state-name as
# label-name (so `doing` state → `doing` label unless overridden).
#
#   state_label <state>     → label name for that pipeline state
#   failed_label            → label name for the dead-letter terminal
#   inflight_states         → all in-flight state names from the pipeline
#   first_inflight_state    → the state a worker enters on claim
#   inflight_labels_json    → JSON array of all in-flight label names (for jq)
#   issue_state <n>         → the in-flight state an issue is currently in
#                              (last-matched in pipeline order; empty if none)
state_label()         { backlog_label "$1" "$1"; }
failed_label()        { backlog_label failed failed; }
inflight_states()     { backlog_inflight_dirs; }
first_inflight_state() { backlog_first_inflight_dir; }

inflight_labels_json() {
  local state
  while IFS= read -r state; do
    [[ -z "$state" ]] && continue
    # state_label uses printf without newline so it composes inline; echo adds
    # the line break that jq -R needs to read each label as a separate entry.
    echo "$(state_label "$state")"
  done < <(inflight_states) | jq -R . | jq -sc .
}

issue_state() {
  local n="$1"
  local labels_json; labels_json=$(gh issue view "$n" --json labels -q '[.labels[].name]')
  local result="" state label
  while IFS= read -r state; do
    [[ -z "$state" ]] && continue
    label=$(state_label "$state")
    if jq -e --arg l "$label" 'any(. == $l)' <<<"$labels_json" >/dev/null; then
      result="$state"
    fi
  done < <(inflight_states)
  printf '%s' "$result"
}

# Validate an id arg and emit the bare issue number. Accepts `42` or `#42`.
# Verifies the issue exists in the repo (one API call) so callers get a clear
# "no such issue" message rather than a cascade of gh errors.
validate_id() {
  local id="$1"
  [[ "$id" =~ ^#?[0-9]+$ ]] \
    || { echo "expected issue number (got: ${id})" >&2; return 1; }
  id="${id#\#}"
  gh issue view "$id" --json number -q .number 2>/dev/null \
    || { echo "no such issue: #${id}" >&2; return 1; }
}

post_log() {
  local n="$1" line="$2"
  gh issue comment "$n" --body "$line" >/dev/null
}

ensure_label() {
  local name="$1" color="$2" desc="$3"
  gh label create "$name" --color "$color" --description "$desc" --force >/dev/null 2>&1
}

# Comments matching the worklog line shape, in chronological order.
# Each line is the raw comment body. Skips bodies that aren't worklog lines.
worklog_lines() {
  local n="$1"
  gh issue view "$n" --json comments \
    -q '.comments | sort_by(.createdAt) | .[].body' \
    | grep -E '^- [0-9TZ:-]+ '
}

# Extract `branch=<X>` from a worklog line. Empty if not present.
branch_of() {
  grep -oE 'branch=[^ ]+' <<<"$1" | tail -1 | cut -d= -f2
}

cmd_setup() {
  require_gh
  [[ -f backlog/AGENTS.md ]] && {
    echo "backlog/AGENTS.md exists — refusing to overwrite" >&2; exit 1
  }
  # Flags:
  #   --pipeline="todo → doing → done"      pipeline declaration (default shown)
  #   --label-<state>=<name>                rename label for a pipeline state
  #   --label-failed=<name>                 rename the dead-letter label
  #   --failed-label=<name>                 alias for --label-failed
  #   --claim-label=<name>                  alias for renaming the first stage
  #   --backend=*                           dispatcher's flag, ignored here
  #
  # Two-pass: first extract --pipeline so we know the valid label roles, then
  # validate and collect label overrides against that pipeline.
  local pipeline="todo → doing → done"
  local arg
  for arg in "$@"; do
    case "$arg" in
      --pipeline=*) pipeline="${arg#--pipeline=}" ;;
    esac
  done

  # Parse pipeline into in-flight states (drop intrinsic todo/done/failed/
  # inbox). Token extraction matches lib.sh's regex so this parser and the
  # runtime pipeline parser stay consistent: `[a-z][a-z0-9-]*` greedily
  # pulls state-shaped tokens out of the string regardless of separator
  # (`→`, `->`, `>`, `,`, spaces all work).
  local -a inflight_list=()
  local tok
  while IFS= read -r tok; do
    case "$tok" in todo|done|failed|inbox|'') ;; *) inflight_list+=("$tok") ;; esac
  done < <(echo "$pipeline" | grep -oE '[a-z][a-z0-9-]*')
  [[ ${#inflight_list[@]} -eq 0 ]] && {
    echo "pipeline must declare at least one in-flight stage (got: $pipeline)" >&2
    exit 1
  }

  # Valid label roles = inflight_list + "failed". Linear lookup (parallel-
  # array style) so this works on macOS default bash 3.2 (no associative
  # arrays).
  is_valid_role() {
    local target="$1" s
    [[ "$target" == "failed" ]] && return 0
    for s in "${inflight_list[@]}"; do
      [[ "$s" == "$target" ]] && return 0
    done
    return 1
  }

  # Second pass: collect label overrides as `state=name` pairs.
  local failed="failed"
  local -a label_args=()
  for arg in "$@"; do
    case "$arg" in
      --backend=*|--pipeline=*) ;;
      --failed-label=*) failed="${arg#--failed-label=}" ;;
      --claim-label=*)  label_args+=("${inflight_list[0]}=${arg#--claim-label=}") ;;
      --label-*)
        local rest="${arg#--label-}"
        local state="${rest%%=*}"
        local name="${rest#*=}"
        [[ "$state" == "$rest" || -z "$state" || -z "$name" ]] && {
          echo "malformed flag: $arg (want --label-<state>=<name>)" >&2; exit 1
        }
        is_valid_role "$state" || {
          echo "unknown label role: $state (valid: ${inflight_list[*]} failed)" >&2; exit 1
        }
        if [[ "$state" == "failed" ]]; then
          failed="$name"
        else
          label_args+=("${state}=${name}")
        fi
        ;;
      *) echo "unknown setup flag: $arg" >&2; exit 1 ;;
    esac
  done

  # Resolve each in-flight state's label. Default = state name; override from
  # the last matching `--label-<state>=` (parallel-array lookup). The empty-
  # array length guard is required by bash 3.2 + `set -u` — `${arr[@]}` errors
  # on an unset empty array without it.
  local -a labels_resolved=()
  local s i pair k v lbl
  for s in "${inflight_list[@]}"; do
    lbl="$s"
    if [[ ${#label_args[@]} -gt 0 ]]; then
      for pair in "${label_args[@]}"; do
        k="${pair%%=*}"; v="${pair#*=}"
        [[ "$k" == "$s" ]] && lbl="$v"
      done
    fi
    labels_resolved+=("$lbl")
  done
  # label_for_state <state> → label name (helper for template rendering below)
  label_for_state() {
    local target="$1" i
    for i in "${!inflight_list[@]}"; do
      [[ "${inflight_list[$i]}" == "$target" ]] && { printf '%s' "${labels_resolved[$i]}"; return; }
    done
  }

  local repo; repo=$(gh repo view --json nameWithOwner -q .nameWithOwner)

  # Create one label per in-flight state, plus the failed label.
  local s
  for s in "${inflight_list[@]}"; do
    ensure_label "$(label_for_state "$s")" "fbca04" "backlog: ${s}"
  done
  ensure_label "$failed" "d93f0b" "backlog: dead-lettered; needs retry"

  # Build the dynamic sections of the AGENTS.md template.
  local first_state="${inflight_list[0]}"
  local first_label="$(label_for_state "$first_state")"
  local pipeline_arrow="todo"
  for s in "${inflight_list[@]}"; do pipeline_arrow+=" → ${s}"; done
  pipeline_arrow+=" → done"

  # State mapping table — todo + each in-flight state + done + failed.
  local state_table=""
  state_table+=$'| todo     | open        | no in-flight labels      |\n'
  for s in "${inflight_list[@]}"; do
    state_table+="| ${s}     | open        | \`$(label_for_state "$s")\` label     |"$'\n'
  done
  state_table+=$'| done     | closed      | no `'"${failed}"$'` label       |\n'
  state_table+=$'| failed   | closed      | `'"${failed}"$'` label          |'

  # `## Labels` section — one line per in-flight state plus failed.
  local labels_section=""
  for s in "${inflight_list[@]}"; do
    labels_section+="${s}: $(label_for_state "$s")"$'\n'
  done
  labels_section+="failed: ${failed}"

  mkdir -p backlog
  cat > backlog/AGENTS.md <<EOF
# backlog/

\`CLAUDE.md\` here is a symlink to this file — read one, not both.

Task state lives in GitHub Issues on **${repo}**. The repo's open issues are
the backlog — anything open is takeable. Non-conformant issues (random
feature requests, dormant bug reports) get triaged when a worker encounters
them; there's no marker label gating membership.

## State mapping

| State    | open/closed | labels                   |
|----------|-------------|--------------------------|
${state_table}

## Worklog

Every state transition and progress note is one comment on the issue, in this shape:

    - <ISO-8601 ts> <verb> [args] | <trail>

| Verb                       | Args / trail                                                |
|----------------------------|-------------------------------------------------------------|
| \`advanced to=<state>\`    | for \`<first-in-flight>\`: \`claimer=<who>\` \`branch=<git-branch>\`; for \`done\`: optional \`\| PR=<url>\`; intermediate transitions: no extra args |
| \`progress\`               | trail = \`\| <note>\`                                        |
| \`cancelled\`              | trail = \`\| <reason>\`                                      |
| \`failed\`                 | trail = \`\| <reason>\`                                      |
| \`rescued\`                | \`claimer=<who>\` \`branch=<git-branch>\`                   |
| \`retried\`                | trail = \`\| <reason>\`                                      |

## Claim resolution

The **branch** is the claim identity (agents often share a GitHub account, so assignee isn't reliable). Walking comments chronologically:

- \`retried\` resets the contest (no current winner)
- \`advanced to=${first_state}\` sets the winner only if currently empty (first-wins, catches take-time races)
- \`rescued\` overrides the current winner (deliberate takeover after timeout)

The earliest \`advanced to=${first_state}\` since the most recent \`retried\`, optionally overridden by a later \`rescued\`, is the canonical claimer.

## Operating

These conventions are operable directly via \`gh issue\` — open an issue, add the \`${first_label}\` label, post the right comment. The \`backlog\` skill (\`add / take / advance / progress / cancel / fail / rescue / retry / maintain / status\`) is a convenience layer that automates the patterns (auto-pick by priority, race-resolution at claim time, status counts) but isn't required for any of them. Mix both: skill for batch operations, raw \`gh\` for one-offs.

Tasks are referenced by issue number — \`take 42\` or \`take #42\`. Titles are free text.

## Backend

\`github-issues\` — see the \`backlog\` skill's \`references/backends/github-issues.md\` for the script's behavior.

## Pipeline

${pipeline_arrow}

(Each in-flight state has a label. \`advance\` moves an issue to the next state in this line — closes the issue when it reaches \`done\`. Add or remove intermediate stages by editing this line; declare each new state in \`## Labels\` below.)

## Labels

${labels_section}

(Each in-flight pipeline state maps to a label. Defaults to the state name itself; override here to align with an existing label vocabulary. \`failed\` is the special dead-letter terminal. Configurable at setup via \`--label-<state>=<name>\` and \`--failed-label=<name>\`; editing this section after \`setup\` requires \`gh label rename\` on the remote to keep the actual labels in sync.)

## ROADMAP

Strategic counterpart at \`backlog/ROADMAP.md\`. See the \`backlog\` skill's \`references/roadmap.md\`.
EOF
  ln -sf AGENTS.md backlog/CLAUDE.md
  [[ -f backlog/ROADMAP.md ]] || cat > backlog/ROADMAP.md <<'EOF'
# ROADMAP

## Intent
<!-- One paragraph. -->

## Principles
<!-- 3–7 short statements. -->

## Current Focus
<!-- 1–3 paragraphs. -->

## Priorities
<!-- Ordered named arcs. -->

## Non-goals
<!-- What we are explicitly not doing right now. -->
EOF
  git add backlog/AGENTS.md backlog/CLAUDE.md backlog/ROADMAP.md
  local label_summary=""
  for s in "${inflight_list[@]}"; do label_summary+="${s}=$(label_for_state "$s") "; done
  git commit -m "setup backlog (github-issues; ${label_summary}failed=${failed})"
}

cmd_add() {
  require_gh
  # Single arg is the issue title (can have spaces if quoted). Any extra
  # positional args are silently ignored for backwards-compat with operators
  # who scripted the old `add SLUG CAT` shape.
  local title="${1:?title required}"
  gh issue create \
    --title "${title}" \
    --body $'[problem, decisions, phases, acceptance]\n\n---'
}

# Best takeable issue: lowest declared priority, recency tiebreak. Empty stdout
# if nothing's takeable. Takeable = open, no claim label. Every open issue is
# in the running — non-conformant ones get handled when encountered.
# Best takeable issue: lowest declared priority, recency tiebreak. Empty stdout
# if nothing's takeable. Takeable = open, no in-flight pipeline label. Every
# open issue is in the running — non-conformant ones get handled when
# encountered.
pick_takeable() {
  gh issue list --state open --limit 1000 \
    --json number,body,updatedAt,labels \
    | jq -r --argjson inflight "$(inflight_labels_json)" '
        [.[] | select(.labels | map(.name) | any(. as $l | $inflight | index($l) != null) | not)]
        | map({
            n: .number,
            p: (try ((.body // "") | capture("(^|\\n)priority:[[:space:]]*(?<v>\\d+)").v | tonumber) catch 999),
            u: .updatedAt
          })
        | sort_by([.p, (.u | fromdateiso8601 * -1)])
        | .[0].n // empty
      '
}

# Returns the branch that currently owns the claim on issue $1. Rules:
#   - `retried` resets the contest (back to no claimant)
#   - `advanced to=<first-in-flight-state>` sets the winner only if there's no
#     current claimant (earliest-wins for race detection at claim time)
#   - `rescued` overrides the current winner (deliberate takeover after timeout)
# Intermediate-stage `advanced to=` lines (e.g. doing → reviewing) are NOT
# claim events; they're the current claimant moving forward. They don't
# affect ownership.
# Empty stdout if no claim has been posted since the last retry.
claim_winner_branch() {
  local n="$1"
  local first; first=$(first_inflight_state)
  worklog_lines "$n" | awk -v first="$first" '
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

cmd_take() {
  require_gh
  local slug="${1:-}"
  local n
  if [[ -n "$slug" ]]; then
    n=$(validate_id "$slug") || exit 1
  else
    n=$(pick_takeable)
    [[ -z "$n" ]] && { echo "no available tasks" >&2; exit 0; }
  fi
  local ts claimer branch first first_lbl
  ts=$(backlog_now); claimer=$(backlog_claimer); branch=$(backlog_branch)
  first=$(first_inflight_state); first_lbl=$(state_label "$first")
  # Post the claim comment first — comment timestamps are the discriminator.
  post_log "$n" "- ${ts} advanced to=${first} claimer=${claimer} branch=${branch}"
  gh issue edit "$n" --add-label "$first_lbl" >/dev/null
  # Re-read: did our comment win the race?
  local winner; winner=$(claim_winner_branch "$n")
  if [[ "$winner" != "$branch" ]]; then
    echo "claim conflict on #${n}: won by branch=${winner}" >&2; exit 1
  fi
  gh issue view "$n" --json url -q .url
}

cmd_advance() {
  require_gh
  local slug="${1:?issue number required}"
  local n; n=$(validate_id "$slug") || exit 1
  local state; state=$(gh issue view "$n" --json state -q .state)

  if [[ "$state" == "CLOSED" ]]; then
    echo "no forward step from closed: $slug" >&2; exit 1
  fi

  # Detect which in-flight state the issue is in (by label).
  local curr; curr=$(issue_state "$n")

  if [[ -z "$curr" ]]; then
    # Not in any in-flight state — this is todo. Claim it (advances to first).
    cmd_take "$slug"
    return
  fi

  # We're in an in-flight state. Look up the next stage in the pipeline.
  local next; next=$(backlog_next_dir "$curr")
  if [[ -z "$next" ]]; then
    echo "no next state from \`${curr}\` in declared pipeline" >&2; exit 1
  fi

  local ts curr_lbl; ts=$(backlog_now); curr_lbl=$(state_label "$curr")

  if [[ "$next" == "done" ]]; then
    # Terminal: close the issue, optionally annotate with PR url.
    local pr_url line
    pr_url=$(gh pr view --json url -q .url 2>/dev/null || true)
    line="- ${ts} advanced to=done"
    [[ -n "$pr_url" ]] && line+=" | PR=${pr_url}"
    post_log "$n" "$line"
    gh issue edit "$n" --remove-label "$curr_lbl" >/dev/null
    gh issue close "$n" --reason completed >/dev/null
  else
    # Intermediate hop: swap the in-flight label.
    local next_lbl; next_lbl=$(state_label "$next")
    post_log "$n" "- ${ts} advanced to=${next}"
    gh issue edit "$n" --remove-label "$curr_lbl" --add-label "$next_lbl" >/dev/null
  fi
  gh issue view "$n" --json url -q .url
}

# Find the in-flight issue claimed by the current branch. Errors if 0 or >1.
# Scans all open issues with any in-flight label (across all pipeline stages).
current_claim() {
  local branch; branch=$(backlog_branch)
  local hits=()
  local n
  while IFS= read -r n; do
    [[ -z "$n" ]] && continue
    local winner; winner=$(claim_winner_branch "$n")
    [[ "$winner" == "$branch" ]] && hits+=("$n")
  done < <(
    gh issue list --state open --limit 200 --json number,labels \
      | jq -r --argjson inflight "$(inflight_labels_json)" '
          .[] | select(.labels | map(.name) | any(. as $l | $inflight | index($l) != null)) | .number
        '
  )
  case "${#hits[@]}" in
    1) printf '%s' "${hits[0]}" ;;
    0) echo "no in-flight claim for branch=${branch}" >&2; return 1 ;;
    *) echo "ambiguous: ${#hits[@]} in-flight claims for branch=${branch}" >&2; return 1 ;;
  esac
}

cmd_progress() {
  require_gh
  local note="${1:?note required}"
  local n; n=$(current_claim) || exit 1
  local ts; ts=$(backlog_now)
  post_log "$n" "- ${ts} progress | ${note}"
  gh issue view "$n" --json url -q .url
}

close_with_log() {
  local n="$1" verb="$2" reason="$3" close_reason="$4" extra_label="${5:-}"
  local ts; ts=$(backlog_now)
  post_log "$n" "- ${ts} ${verb} | ${reason}"
  # Remove whichever in-flight pipeline label is currently set.
  local curr; curr=$(issue_state "$n")
  if [[ -n "$curr" ]]; then
    gh issue edit "$n" --remove-label "$(state_label "$curr")" >/dev/null 2>&1 || true
  fi
  [[ -n "$extra_label" ]] && gh issue edit "$n" --add-label "$extra_label" >/dev/null
  gh issue close "$n" --reason "$close_reason" >/dev/null
}

cmd_cancel() {
  require_gh
  local slug="${1:?issue number required}" reason="${2:?reason required}"
  local n; n=$(validate_id "$slug") || exit 1
  close_with_log "$n" cancelled "$reason" "not planned"
}

cmd_fail() {
  require_gh
  local slug="${1:?issue number required}" reason="${2:?reason required}"
  local n; n=$(validate_id "$slug") || exit 1
  close_with_log "$n" failed "$reason" "not planned" "$(failed_label)"
}

cmd_rescue() {
  require_gh
  local slug="${1:?issue number required}"
  local n; n=$(validate_id "$slug") || exit 1
  local state; state=$(gh issue view "$n" --json state -q .state)
  [[ "$state" != "OPEN" ]] && { echo "issue #${n} is closed; nothing to rescue" >&2; exit 1; }
  local first; first=$(first_inflight_state)
  # Two distinct questions:
  #   (a) was the issue ever claimed? — needs a first-stage advance OR a prior rescue
  #   (b) when was the last sign of life? — any worklog activity counts, so
  #       intermediate stage transitions and progress notes prevent false-positive
  #       rescue on a still-active claimant in a multi-stage pipeline.
  worklog_lines "$n" | grep -qE "(advanced to=${first}( |\$)|rescued)" \
    || { echo "no prior claim line on #${n}" >&2; exit 1; }
  local last_line; last_line=$(worklog_lines "$n" \
    | grep -E '(advanced to=|progress|rescued)' | tail -1)
  [[ -z "$last_line" ]] && { echo "no activity on #${n}" >&2; exit 1; }
  local last_ts; last_ts=$(awk '{print $2}' <<<"$last_line")
  local ep; ep=$(backlog_epoch "$last_ts")
  [[ -z "$ep" ]] && { echo "unparseable timestamp: $last_ts" >&2; exit 1; }
  # Timeout lives in body frontmatter — write the body to a tempfile so the
  # shared helper (which works on files) can parse it.
  local tmp; tmp=$(mktemp)
  gh issue view "$n" --json body -q .body > "$tmp"
  local secs; secs=$(backlog_timeout_seconds "$tmp"); rm -f "$tmp"
  (( $(date -u +%s) - ep > secs )) \
    || { echo "claim still active; refusing rescue" >&2; exit 1; }
  local ts claimer branch
  ts=$(backlog_now); claimer=$(backlog_claimer); branch=$(backlog_branch)
  post_log "$n" "- ${ts} rescued claimer=${claimer} branch=${branch}"
  # Preserve whichever stage the issue is in. If no in-flight label is present
  # (shouldn't happen in normal flow but worth defending), set the first stage.
  local curr; curr=$(issue_state "$n")
  if [[ -z "$curr" ]]; then
    gh issue edit "$n" --add-label "$(state_label "$first")" >/dev/null
  fi
  # Symmetry with cmd_take: re-read in case another agent also rescued.
  local winner; winner=$(claim_winner_branch "$n")
  if [[ "$winner" != "$branch" ]]; then
    echo "rescue conflict on #${n}: won by branch=${winner}" >&2; exit 1
  fi
}

cmd_retry() {
  require_gh
  local slug="${1:?issue number required}" reason="${2:?reason required}"
  local n; n=$(validate_id "$slug") || exit 1
  local labels failed
  labels=$(gh issue view "$n" --json labels -q '[.labels[].name] | join(",")')
  failed=$(failed_label)
  [[ ",${labels}," == *",${failed},"* ]] \
    || { echo "not in failed state: $slug" >&2; exit 1; }
  gh issue edit "$n" --remove-label "$failed" >/dev/null
  gh issue reopen "$n" >/dev/null
  local ts; ts=$(backlog_now)
  post_log "$n" "- ${ts} retried | ${reason}"
}

cmd_status() {
  require_gh
  # One fetch, bucket via jq. Every issue is counted. Bucket names are the
  # canonical pipeline state names regardless of label config — operators
  # compare across projects without translating.
  #
  # Build:
  #   state_label_map: label-name → state-name (so jq can reverse-lookup)
  #   bucket_init:     {"todo":0, "<state1>":0, ..., "done":0, "failed":0}
  #   output_order:    state name printing order (todo → in-flight stages → done → failed)
  local state_label_map bucket_init output_order failed_lbl
  state_label_map=$({
    printf '{'
    local first=1
    while IFS= read -r s; do
      [[ -z "$s" ]] && continue
      [[ $first -eq 1 ]] && first=0 || printf ','
      printf '"%s":"%s"' "$(state_label "$s")" "$s"
    done < <(inflight_states)
    printf '}'
  })
  bucket_init=$({
    printf '{"todo":0'
    while IFS= read -r s; do
      [[ -n "$s" ]] && printf ',"%s":0' "$s"
    done < <(inflight_states)
    printf ',"done":0,"failed":0}'
  })
  output_order=$({
    printf '["todo"'
    while IFS= read -r s; do
      [[ -n "$s" ]] && printf ',"%s"' "$s"
    done < <(inflight_states)
    printf ',"done","failed"]'
  })
  failed_lbl=$(failed_label)

  gh issue list --state all --limit 1000 --json number,state,labels \
    | jq -r --argjson init "$bucket_init" \
            --argjson stateMap "$state_label_map" \
            --argjson order "$output_order" \
            --arg failed "$failed_lbl" '
        reduce .[] as $i ($init;
          ($i.labels | map(.name)) as $L
          | if $i.state == "OPEN" then
              # Any in-flight label puts the issue in that state bucket;
              # otherwise it sits in todo.
              ($L | map($stateMap[.] // empty)) as $hit
              | if ($hit | length) > 0 then .[$hit[0]] += 1 else .todo += 1 end
            elif ($L | contains([$failed])) then .failed += 1
            else .done += 1 end
        )
        | . as $b | $order | map("\(.): \($b[.])") | .[]
      '
}

cmd_maintain() {
  echo "maintain: load ~/.claude/skills/backlog/references/maintain.md and walk the buckets" >&2
  echo "(advisory walk; benefits from agent judgment)"
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
