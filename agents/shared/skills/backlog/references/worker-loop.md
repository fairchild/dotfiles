# Worker Loop

Canonical recipe for `/backlog worker` — the full execution path an autonomous backlog worker walks from "what's next?" to "shipped or honestly failed." Wraps the verb recipes in `worker.md` with the loading, ranking, and wrap-up phases that turn primitives into a runnable loop.

`parallel-agents.md` carries the *exploratory* worker sketch — the rationale and design notes. This file is the *canonical* recipe: what an agent invoked as `/backlog worker` actually does.

## When to use

- Operator says `/backlog worker`, `take the next task`, `work the backlog`, or similar.
- Agent is dispatched into a project's backlog with no specific task assigned.
- Agent is invoked as part of a scheduled/triggered job that should drain available work.

If the operator names a specific slug (`/backlog take feature-X`), skip the ranking phase and go straight to claim. The loop below is for the auto-pick case.

## The loop

Six phases. Each one references the verb recipes in `worker.md` and the backend bash in `backends/<chosen>.md`.

### 1 — Load context

Before reading any task file, load the project's lens:

- `backlog/AGENTS.md` — backend, pipeline, defaults, project conventions.
- `backlog/ROADMAP.md` — Intent, Principles, Current Focus, Priorities (named arcs), Non-goals. Without this, ranking is just priority numbers; with it, ranking weighs arc alignment too.
- `git status` and `git log -5` — am I on a fresh branch, mid-something, or behind main?

Note which backend is declared. The verb recipes you'll run depend on it.

### 2 — Maintain prelude

Run `maintain` (see `maintain.md`) once before claiming. Two things this catches that would otherwise bite mid-cycle:

- `ADVANCED BUT NOT MOVED` — safe auto-fix. A previous worker marked done in the log but didn't `git mv`; complete the move silently.
- `TIMED OUT` — surface to operator. Author-authorized timeouts may be auto-failed (per `maintain.md`); otherwise wait for direction.

For `maildir-shared`, also watch for `ORPHANED SHARED IN-FLIGHT` — surfaces stale claims from deleted worktrees that need attention before you claim.

Cross-worktree duplicate-detection during the prelude is **not** the worker's job. If duplicate slugs surface naturally (because a stale `todo/` entry exists in this worktree but the slug is also live in another), the backend's claim path catches it — `maildir-shared` via O_EXCL conflict, `maildir-git` only at merge.

### 3 — Rank and claim

Compute the takeable set:

1. List `backlog/todo/*.md`.
2. For `maildir-shared`, subtract any slug already in any shared in-flight dir.
3. Filter: each candidate's `dependencies:` slugs must all resolve under `done/`.

Workers only claim from `todo/`. If the project declares upstream stages (e.g. `inbox/` for triage), those are deliberately out of the worker's scope — `todo/` is the contract that an item is ready for an agent. Grooming earlier stages is reflection work, not worker work.

Rank the survivors. Three-tier:

- **Primary: roadmap lens.** Tasks declaring `arc: <name>` matching the ROADMAP's Current Focus or top-priority arcs sort first. Tasks under arcs warned against (Non-goals, "ad-hoc cleanup" callouts) sort last.
- **Secondary: frontmatter priority.** Lower `priority:` numbers first; default `999` sorts last.
- **Tertiary: fresh-context signals.** Among same-arc/same-priority candidates, prefer the more recently authored or updated task, and prefer tasks whose author-set `timeout:` is shorter than the project default. Both are proxies for fresh authorial context: recency is fresh by construction, and a short timeout was chosen against a budget the author thought achievable *now*. Fresher tasks carry fresher context — the author's reasoning is more likely to still match the current state of the code, deps are less likely to have moved, and the spec is less likely to have drifted from the world it described. A meaningful recency gap (e.g. two months vs. yesterday), or an unusually tight timeout against the default, can also outweigh a one-point priority difference — stale priority labels were assigned against a backlog that no longer looks the same.

Take the top. Call the backend's `advance` recipe from `todo/`. The claim line stamps `claimer=` and `branch=`.

If the takeable set is empty, exit cleanly: `no available tasks` (in `maildir-shared` this may mean other worktrees have everything claimed; that's expected).

### 4 — Execute

Read the full task file end to end. Above the divider is the spec; below is any prior worklog from previous attempts (rescue case — see `parallel-agents.md` for activity-skipping).

If you find the task *underspecified* — gaps the author didn't fill — `fail` with `reason="needs replanning: <what's missing>"` rather than burning the claim guessing. A sharper retry helps the next worker.

Execute the spec in agent (acceptEdits) mode. If you were dispatched in plan mode, follow the Worker mode pattern in `worker.md`: draft a plan from the task → exit plan mode → dispatch a subagent with the plan as its prompt.

While executing, `progress` notes at meaningful checkpoints. Write them semantically — *"phase-1 baseline shows 0% narrative blocks; phase-2 premise needs revision"* tells the next claimer what's safe to skip. *"still working"* tells them nothing. Optional on short single-phase claims where no checkpoint earns its keep.

### 5 — Closure (three branches)

**Default outcome: a merge-ready PR link as the headline of the final report.** The user clicks, reviews, merges. Agent-done means the file is in `done/` with an `advanced to=done | PR=<url>` log line; the human's merge closes the loop, and lead time from agent-done to merged is later trackable from that pairing. The three branches below cover the default (5a), a partial-scope slice that still ships review-ready (5b), and the spec-was-wrong / blocked / out-of-scope cases that don't ship at all (5c). Anything other than a review-ready PR for 5a — draft, no PR, batched with siblings — needs the spec to say so explicitly.

Choose one branch based on outcome:

#### 5a — Shipped: full scope completed

Open the PR as review-ready (not draft, unless the spec said draft), capture the URL, then advance to `done`:

```bash
gh pr create --title "..." --body "..."
# capture URL via: gh pr view --json url -q .url
```

Run the backend's `advance` to done with the PR URL in `| PR=<url>` prose.

**Roadmap reference sweep.** After landing in `done/`, grep `backlog/ROADMAP.md` and any sibling slugs (same `arc:`) for the just-shipped slug or title. If the roadmap's Current Focus or Priorities section described this as upcoming/planned, update it to reflect that it's shipped. Same arc, related tasks: check if the arc's description should evolve. Don't auto-edit aggressively — surface drift to the operator if uncertain.

If the PR has a first round of review comments before the loop exits, respond to them (use `respond-to-pr-review` skill if available).

#### 5b — Shipped a slice but not the full scope

A coherent slice landed on a valid premise, but the original scope was bigger than one claim could cover. Don't `fail` — that pretends the slice didn't ship. Don't extend the claim either — that hoards work.

Instead:
1. Author a follow-up task in `backlog/todo/` capturing what's left, with `arc:` inherited from the parent (if any). Single `add(slug)` commit.
2. Advance the original to `done/` with a progress note explaining what slice shipped and where the rest landed (`see: backlog/todo/<followup-slug>.md`).

Order matters: the follow-up commits first so it's visible (and dependency-resolvable) before the advance closes the original. The two commits are sequential, not atomic — separate commits keep the diffs reviewable and let `git revert` work cleanly on either.

#### 5c — Premise wrong, blocked, or out-of-scope

The work surfaced evidence the spec is wrong, an external blocker won't lift in time, or the task isn't worth doing. Call the backend's `fail` recipe with a precise reason. The retry recipe (when an operator decides to attempt again) permits the spec edit that lands the corrected premise.

Don't silently edit the spec from a worker — the rule is in `worker.md`: spec contradictions surface via `fail`, not silent edit.

### 6 — Report and exit

Print a short summary for the operator with the PR URL as the headline when one was opened — the click-to-merge handoff is the load-bearing thing:

- **PR URL** (when one was opened) — surface first; this is what the user acts on.
- What got claimed and where it ended up (done/failed/sliced).
- Any roadmap edits or follow-up tasks authored.
- Next-loop hint: re-invoke `/backlog worker` to drain more, or stop here.

Stateless — the next loop reads everything from the filesystem. Restart equals re-read.

## Failure modes (and what handles them)

| What can go wrong                              | Where it's caught                              |
|------------------------------------------------|------------------------------------------------|
| Worker crashes mid-execution                   | Timeout (default `7d`); next loop's maintain rescues or fails |
| Worker advances to `done` but `git mv` fails  | `ADVANCED BUT NOT MOVED` bucket; safe auto-fix in next maintain |
| Two workers race the same task (`maildir-shared`) | O_EXCL claim conflict at step 3; loser tries the next candidate |
| Two workers race the same task (`maildir-git`) | Merge conflict; resolution is `fail` one, keep the other |
| Spec premise turns out wrong                   | Step 5c — `fail` with reason; retry edits spec |
| Worker writes ambiguous progress notes         | Next claimer redoes work the prior one already finished — wasted time, not incorrectness |
| Worker keeps hitting the same arc, ignoring others | Operator inspection; bias correction is a roadmap-edit, not a code change |

## What the loop deliberately doesn't do

- Pick which projects' backlogs to work on (operator's decision).
- Coordinate across multiple backlogs (deps are intra-backlog only).
- Hold state between invocations (each loop re-reads from disk).
- Auto-rebase, auto-merge, or auto-deploy the PR.
- Override the operator's manual moves — if the operator has been editing the queue, respect what they wrote.
