# Parallel Agents

Advisory guidance for running multiple independent agents against a shared backlog. The skill provides primitives; this doc names the patterns that compose them into a working distributed system, and the failure modes you have to design around.

## Mental model

A task file is a durable execution log: frontmatter + description is the spec, the bullet log is the event stream, the pile location is derived state — all in git. Loosely inspired by Temporal's durable-workflow pattern: `progress` lines are activity checkpoints that survive across attempts, and an agent rescuing or retrying a task can read prior progress and skip what's already done.

This puts a usage obligation on progress notes: **write them semantically and idempotently**. "auth migration prototype passing locally" tells the next claimer what's done and is safe to skip; "still working" tells them nothing.

## What the skill provides

The atomic primitives, and nothing else:

- **Maildir lock.** The first `advance` (`git mv todo/X.md doing/X.md`) is the claim. Two agents racing the same task collide at merge — the failure is surfaced, not silenced.
- **Append-only log.** One bullet per event, in committed git history. Both `cat` and `git log --follow` are valid views.
- **Near-immutable spec.** Frontmatter and description are frozen after first commit, with one exception: `retry` may edit them, since retry IS a correction. State changes otherwise go to the log.
- **Author-declared (or default) budgets.** `timeout:` in frontmatter is the contract for "fail this if it sits in any in-flight dir past this duration." Absent = 7d (see "Default timeout" below).
- **No backward verb.** A task that can't proceed gets `fail`ed; an operator (or another agent) may `retry` it back to `todo/`. There is no "release," and `retry` does not work on `done/` tasks.

## What's out of scope

- **No worker pool.** Agents discover and take tasks themselves; nothing dispatches.
- **No leader election.** All agents are peers; collisions are git's problem.
- **No heartbeat enforcement.** A claimer that goes silent isn't pinged; timeouts and maintenance are the failure-detection mechanism.
- **No cron / scheduler.** Periodic cleanup is the operator's responsibility — see "Two cleanup patterns" below.

## Default timeout: 7 days

Tasks may declare a `timeout:` in frontmatter. **If they don't, maintain and advance-prelude treat the task as having `timeout: 7d`.** That way every task is rescuable from a dead claimer without forcing the author to think about budgets at add time. The clock anchors to the latest `advanced` or `rescued` log line — so each forward step gets its own stage budget under the same number.

```
- 2026-05-17T00:00:00Z failed | timeout: budget=7d (default), claimed=2026-05-10T00:00:00Z, claimer=...
```

The 7d default is a skill-level convention, documented here and in `backlog/AGENTS.md` (so a fresh agent landing in the project sees it). Authors who need a tighter or looser budget for a specific task declare it explicitly:

```yaml
---
timeout: 4h        # short-running agent task
timeout: 30d       # long-running migration
---
```

Projects with a fundamentally different rhythm can override the default by stating one at the top of their `backlog/AGENTS.md` (e.g., "default timeout in this project: 24h"). The recipes don't read AGENTS.md — it's social convention — but humans and agents do, and they declare timeouts on tasks accordingly.

## Failure detection

Timeout is the primitive built in. The other detection patterns are useful supplements you can add as additional `maintain` buckets without changing the file format:

| Pattern              | What it catches                              | What it needs                     |
|----------------------|----------------------------------------------|-----------------------------------|
| **Timeout** (built-in) | Claim age exceeded the budget (declared or 7d default) | Just the file                |
| Heartbeat            | Claimer hung mid-task without timing out     | Claimer cooperation: append `progress` every N min |
| Branch / PR liveness | Claim's branch is dead and never shipped     | Git / network state               |
| Workspace presence   | Claim's workspace ID no longer exists        | Conductor (or equivalent) inspection |

For v1, timeout alone is enough because it requires nothing external. Add the others as new maintain buckets if you observe real cases they'd catch.

## Two cleanup patterns (both idempotent, both safe)

The skill provides two routes for handling timed-out tasks — `rescue` in place (if the current agent wants to take it over) or `fail` to `failed/` (so the queue drains and an operator can `retry` later). The two patterns differ in *who runs the routing*, not in what actions are available. They compose — you can do either or both. Parallel runs collide at git the same way a real claim-race would, which is the right failure mode.

### Advance-prelude (recommended for high-traffic backlogs)

Before an `advance` out of `todo/`, scan all in-flight dirs for stale claims. For each:

- If this is the task the agent wants to work on: invoke `rescue` — claim in place, no `git mv`.
- Else: invoke `fail` with reason `timeout` — move to `failed/`. An operator can `retry` later if the task is still worth doing.

```bash
now=$(date -u +%s); ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
target_slug="${1:-}"        # set if the agent has a specific slug in mind; empty for scan-only

# Enumerate in-flight dirs by exclusion (anything that isn't inbox/todo/done/failed)
in_flight=$(find backlog -mindepth 1 -maxdepth 1 -type d ! -name todo ! -name done ! -name failed)

for d in $in_flight; do
  for f in "$d"/*.md; do
    [[ -f "$f" ]] || continue
    timeout=$(awk '/^---$/{n++; if(n==2) exit} n==1 && /^timeout:/ {sub(/^timeout:[[:space:]]*/, ""); print; exit}' "$f")
    [[ -z "$timeout" ]] && timeout=7d
    last=$(grep -E '^- [0-9TZ:-]+ (advanced|rescued) ' "$f" | tail -1 | awk '{print $2}')
    [[ -z "$last" ]] && continue
    n="${timeout%[smhdw]*}"; unit="${timeout: -1}"
    case "$unit" in s) secs=$n;; m) secs=$((n*60));; h) secs=$((n*3600));; d) secs=$((n*86400));; w) secs=$((n*604800));; *) continue;; esac
    ep=$(date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$last" +%s 2>/dev/null || gdate -d "$last" +%s 2>/dev/null || true)
    [[ -z "$ep" ]] && continue
    (( now - ep > secs )) || continue

    slug=$(basename "$f" .md)

    if [[ "$slug" == "$target_slug" ]]; then
      # Rescue in place
      branch=$(git rev-parse --abbrev-ref HEAD)
      claimer=${CONDUCTOR_WORKSPACE_NAME:+conductor:$CONDUCTOR_WORKSPACE_NAME}
      claimer=${claimer:-${CMUX_WORKSPACE_ID:+cmux:$CMUX_WORKSPACE_ID}}
      claimer=${claimer:-$(whoami)@$(hostname -s)}
      echo "- $ts rescued claimer=$claimer branch=$branch" >> "$f"
      git add "$f"
      git commit -m "rescue($slug) $claimer @ $branch"
    else
      # Dead-letter — operator can retry if still worth doing
      mkdir -p backlog/failed
      git mv "$f" "backlog/failed/${slug}.md"
      echo "- $ts failed | timeout: budget=$timeout, claimed=$last" >> "backlog/failed/${slug}.md"
      git add "backlog/failed/${slug}.md"
      git commit -m "fail($slug) timeout"
    fi
  done
done
# Then run the normal advance recipe (or auto-pick) for the target_slug if not rescued above.
```

### Periodic janitor (recommended for low-traffic backlogs)

A scheduled job (cron, GitHub Action, Conductor hook) runs the same loop above with `target_slug=""` (scan-only), which fails stale tasks into `failed/`. The janitor never *rescues* — that requires an agent ready to do the work. Catches the case where tasks time out but no agent has done any work in a while.

The failed line in the log looks like:

```
- 2026-05-17T00:00:00Z failed | timeout: budget=3d, claimed=2026-05-14T00:00:00Z, claimer=conductor:austin-v3
```

**In-flight set = active work, with an asterisk:** the invariant holds *as of the last detection sweep*. Either a janitor must run on a schedule, or workers must run preludes frequently enough that staleness windows stay bounded.

## Why fail moves the file rather than tagging in place

A `fail` could append a `failed` log line in place and leave the file where it was — but that breaks location-is-status: `ls doing/` would no longer mean "in flight," every status check would have to read each file's log, and the `git mv` race that gives us the atomic lock would be decoupled from the state change. Keeping fail as one operation (move + append + commit) preserves both invariants.

## The single permitted exception to "maintain never moves files"

Maintain is advisory by default. The one exception: for TIMED-OUT entries (author-declared budget exceeded, or default-inherited), maintain may `fail` them to `failed/`. The author authorized the timeout, so enforcing it is contract-keeping, not policy. An operator can `retry` anything in `failed/` that's still worth doing.

## Limits worth knowing about

- **The 7d default may be wrong for your workflow.** Conductor agents typically finish in hours; long migrations may take weeks. Authors should override per-task when the default is a poor fit, and projects with a fundamentally different rhythm should state their convention in `backlog/AGENTS.md`.
- **Failed-then-retried tasks come back to `todo/`**, where any agent can claim them — including the one whose attempt failed. The log reflects both attempts. The deliberate two-step (`fail` reason → `retry` reason) is more honest about what happened than a single "release" would have been.
- **Cross-task ordering isn't preserved across timeouts.** If `B` was claimed after `A` originally, and `A` timed out, `B` could complete before `A`'s second attempt. Dependencies in frontmatter handle the cases where ordering matters.
- **Activity skipping is convention, not enforcement.** The format makes prior progress notes visible; the claimer is trusted to read them and skip appropriately. There's no machine-checked "this activity was already done" guarantee.

---

## Worker process design (rationale)

Beyond the primitives, the canonical worker loop now lives at `worker-loop.md` — the recipe `/backlog worker` runs. What follows is the rationale and design notes behind that loop: why these phases, what scheduling shapes the primitives enable, what failures each component handles.

### Core loop

```
while true:
  advance a task out of todo/ (with advance-prelude that fails timed-out)
  read the file's full body — frontmatter spec + prior progress notes
  identify completed activities from prior attempts (semantic reading)
  for each remaining activity:
    do the work
    append a progress note with semantic detail, commit
    advance the task forward in the pipeline if the activity completed a phase
  if work succeeded all the way: advance to done/ (with PR url if applicable)
  if work didn't complete: run `fail` with reason — operator can `retry` later
  if work shouldn't continue (no longer useful): run `cancel` with reason
```

Stateless: each cycle reads everything it needs from the task file. No worker-side memory across tasks; restart equals re-read.

`rescue` is for *picking up someone else's* stale claim, which is what advance-prelude does before a fresh advance. The worker doesn't have a voluntary-handback verb — if it can't continue, it `fail`s honestly.

### Worker identity

The advance recipe stamps a `claimer=` from the environment (when claiming from todo/) in this order:

1. `CONDUCTOR_WORKSPACE_NAME` → `conductor:austin-v3`
2. `CMUX_WORKSPACE_ID` → `cmux:abc123`
3. fallback → `user@host`

For your own worker, pick whichever identifies the agent process uniquely enough to be useful in `git blame` / progress logs. The identity is informational — it doesn't drive scheduling or authorization.

### Scheduling shapes

The skill enables several worker scheduling patterns without baking any in:

| Shape           | When it fits                                       | How it composes with the skill                    |
|-----------------|----------------------------------------------------|---------------------------------------------------|
| **One-off**     | Human invokes a worker for a specific task         | Just call the verb recipes inline                 |
| **Continuous loop** | Single agent burning down a backlog            | Worker loops; sleeps when `todo/` is empty        |
| **Parallel pool** | Many workers, shared backlog                     | Each worker is independent; lock = git mv         |
| **Specialized** | Workers filter tasks by slug prefix or `topic:`-like convention | Worker scans `todo/` and filters before calling `advance` with an explicit slug |

For most cases, *the agents themselves are the scheduler* — each one reads the backlog and decides what to claim. The skill enables this by making all relevant state visible in the filesystem; no broker, no queue, no dispatcher.

### Failure modes and what handles them

| Failure                                       | Handled by                                |
|-----------------------------------------------|-------------------------------------------|
| Worker crashes mid-activity                   | Timeout → next worker's prelude rescues in place (or janitor fails to `failed/`) |
| Worker advances to `done/` but the `git mv` never lands | MERGED-BUT-NOT-MOVED bucket; safe auto-fix |
| Worker hangs (no progress, timeout not yet exceeded) | Waits until TIMED OUT fires (declared budget or 7d default) |
| Worker writes ambiguous progress notes        | Next attempt redundantly redoes work — wasted time, not incorrectness |
| Two workers race the same task                | Git merge conflict → one wins, one rebases |
| Worker claims a task it can't handle          | `fail` with reason; operator `retry`s if still worth doing |
| Task keeps failing across many retries        | Operator inspects `failed/` and decides to `cancel` (terminal) or keep retrying |

### What this skill deliberately doesn't help with

- Choosing which projects' backlogs to work on
- Inter-backlog dependencies (deps are intra-backlog only)
- Cross-backlog rate limiting or quota
- Persistent worker registries or health dashboards
- Retry policy beyond manual `retry` (no automatic exponential backoff, jittered retries, or retry counters)

Build those *above* the skill, in your project, where they belong.
