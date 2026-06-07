# Backend: github-issues

Storage mechanism for projects whose `backlog/AGENTS.md` declares `## Backend: github-issues`. Built for projects whose work is already visible in GitHub Issues — cross-machine, multi-collaborator (human and agent), and where a parallel maildir would just duplicate the queue.

This doc has two layers. The first is **the protocol** — the conventions a human or any agent must follow to participate in the backlog, expressed in raw `gh` operations. The second is **the script** — how the bundled `backlog-github-issues.sh` implements those conventions as one convenience layer over them. The protocol is the contract; the skill is one client.

Verb semantics (the protocol-level recipes): `../worker.md`. Implementation: `../../scripts/backlog-github-issues.sh`.

## When to pick this backend

- The team already lives in GitHub Issues; a maildir would be a parallel ledger no one updates.
- Multi-machine work (Conductor on one laptop, CI on another, contributor on a third) needs to see the same in-flight set.
- Non-agent collaborators who don't `cd` into the repo need visibility into what's claimed and what's open.
- You want existing repo automation (Matt Pocock-style triage, custom managed reviewers, etc.) to participate in the same label/comment ecosystem as the backlog skill.

For local-only single-machine work, `maildir-git` is simpler; for multi-worktree on one machine, `maildir-shared` keeps everything inspectable in place.

---

# The protocol

GitHub Issues *is* the queue — the repo's open issues are the backlog, holistically. Anything open is takeable; non-conformant issues (random feature requests, dormant bug reports) get triaged when a worker encounters them. There's no marker label gating membership.

There is no local `todo/`/`doing/`/`done/` tree; the local repo holds only the convention declaration (`backlog/AGENTS.md`) and the roadmap (`backlog/ROADMAP.md`).

## State mapping

The state machine is the **pipeline** declared in `backlog/AGENTS.md` (default: `todo → doing → done`). Each in-flight pipeline stage maps to a label, and `advance` walks the issue from one stage to the next, closing it when the next stage is `done`.

For the default pipeline:

| State    | open/closed | labels                  |
|----------|-------------|-------------------------|
| todo     | open        | no `doing` label        |
| doing    | open        | `doing` label           |
| done     | closed      | no `failed` label       |
| failed   | closed      | `failed` label          |

A project that declares `todo → doing → reviewing → done` gets an extra in-flight stage:

| State     | open/closed | labels                       |
|-----------|-------------|------------------------------|
| todo      | open        | no in-flight labels          |
| doing     | open        | `doing` label                |
| reviewing | open        | `reviewing` label            |
| done      | closed      | no `failed` label            |
| failed    | closed      | `failed` label               |

Each in-flight label name and the `failed` label are configurable per project — defaults are the state names themselves. Operators set them via `setup --pipeline="..." --label-<state>=<name> --label-failed=<name>` or by editing `## Pipeline` and `## Labels` in `backlog/AGENTS.md` after setup. The names land in three places that must stay consistent: the actual GitHub labels (`gh label create`), the `## Labels` declaration, and the label references in all worklog operations.

`cancel` and ordinary `done` both close the issue — discriminated by the worklog comment and by GitHub's close reason (`completed` vs `not planned`). The `status` verb lumps cancelled with done, matching the maildir backends.

## Identifiers

Tasks are referenced by **issue number** — `take 42` or `take #42`. Titles are free text; the operator/agent reads them out of `gh issue list` to know which number to grab. There are no slug labels and no parallel identifier scheme — GitHub's native identifier does the whole job.

## The worklog convention

Every state transition and progress note is one comment on the issue, formatted as a single line:

```
- <ISO-8601 ts> <verb> [args] | <trail>
```

| Verb                          | Args / trail                                          |
|-------------------------------|-------------------------------------------------------|
| `advanced to=<first-stage>`   | `claimer=<who>` `branch=<git-branch>` — the claim event |
| `advanced to=<intermediate>`  | no extra args — stage→stage transition by the claimant |
| `advanced to=done`            | optional `\| PR=<url>` — closes the issue              |
| `progress`                    | trail = `\| <note>`                                    |
| `cancelled`                   | trail = `\| <reason>`                                  |
| `failed`                      | trail = `\| <reason>`                                  |
| `rescued`                     | `claimer=<who>` `branch=<git-branch>` — takeover       |
| `retried`                     | trail = `\| <reason>`                                  |

For the default pipeline `todo → doing → done`, the only `advanced to=...` lines you'll see are `to=doing` (claim) and `to=done` (close). For `todo → doing → reviewing → done`, the claimant also posts `advanced to=reviewing` as a stage→stage transition.

Comments are append-only and chronological. `gh issue view --json comments` reconstructs the full history in the same shape a `tail backlog/done/<slug>.md` would show in a maildir backend.

## Claim resolution

The **branch** is the claim identity. Agents often share a GitHub PAT (one bot account, many workers), so `--assignee @me` reduces to "this account is involved" rather than "this worker claimed it." Branch is usually unique per workspace (Conductor, cmux, feature branches).

Walking the worklog comments in chronological order:

| Comment kind                  | Effect on the current winner                                                       |
|-------------------------------|------------------------------------------------------------------------------------|
| `retried`                     | reset — no current winner (contest restarts when an item bounces back from failed) |
| `advanced to=<first-stage>`   | first-wins — sets the winner only if currently empty (catches take-time races)     |
| `advanced to=<intermediate>`  | *no effect* on ownership — just the claimant moving stage→stage                    |
| `rescued`                     | override — replaces the current winner (deliberate takeover after timeout)         |

The earliest `advanced to=<first-stage>` since the most recent `retried`, optionally overridden by a later `rescued`, is the canonical claimer. (For the default pipeline `todo → doing → done`, that's `advanced to=doing`.)

## Operating directly via `gh`

The protocol is sufficient to participate without the skill. Any of these is a legitimate operation. Recipes use the default label names (`doing` / `failed`) — substitute your project's configured names from `backlog/AGENTS.md` `## Labels` if different.

**Add a task:**
```bash
gh issue create --title "rewrite-auth-middleware"
```

**Claim the task you opened above:**
```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
BR=$(git branch --show-current)
gh issue comment 42 --body "- $TS advanced to=doing claimer=jane@laptop branch=$BR"
gh issue edit 42 --add-label doing
# Verify the claim. The skill (`backlog.sh take 42`) does this automatically.
# By hand:
gh issue view 42 --json comments -q '.comments[].body' \
  | grep -E '^- [0-9TZ:-]+ (advanced to=doing|rescued|retried)'
# Apply Claim resolution from above: earliest `advanced to=doing` since the
# last `retried`, overridden by any later `rescued`. If that line's branch=
# isn't yours, you lost — remove the label and let the winner have it.
```

**Make progress:**
```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh issue comment 42 --body "- $TS progress | first cut passing tests locally"
```

**Advance to done with PR:**
```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
PR=$(gh pr view --json url -q .url)
gh issue comment 42 --body "- $TS advanced to=done | PR=$PR"
gh issue edit 42 --remove-label doing
gh issue close 42 --reason completed
```

**Cancel:**
```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh issue comment 42 --body "- $TS cancelled | spec was wrong; legal flipped the requirement"
gh issue edit 42 --remove-label doing
gh issue close 42 --reason "not planned"
```

**Fail (dead-letter, eligible for retry later):**
```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh issue comment 42 --body "- $TS failed | needs replanning: upstream API changed"
gh issue edit 42 --remove-label doing --add-label failed
gh issue close 42 --reason "not planned"
```

A Matt Pocock-style agent, a managed PR reviewer, a human with a terminal — anyone following the protocol participates in the same backlog as the skill. Mix freely: skill for batch operations (auto-pick, race-resolution, status counts), raw `gh` for one-offs.

---

# The script (one implementation of the protocol)

The bundled `backlog-github-issues.sh` automates the patterns above. It's a convenience layer — useful for the operations that benefit from automation (priority-ranked auto-pick, race-resolution at claim time, status counts across all four states) — but isn't required for any individual operation.

## Labels the script reads

The script reads the **pipeline** from `## Pipeline` in `backlog/AGENTS.md` (default `todo → doing → done`) and looks up each in-flight stage's label in `## Labels`. Defaults to the state name itself; overrides honored if present.

| Role               | Default        | Source                                              |
|--------------------|----------------|-----------------------------------------------------|
| `<state-name>`     | `<state-name>` | `backlog/AGENTS.md` `## Labels` `<state>: <name>`   |
| `failed`           | `failed`       | `backlog/AGENTS.md` `## Labels` `failed: <name>`    |

`lib.sh::backlog_label <role> <default>` is the reader. The script wraps it as `state_label <state>` (for in-flight stages) and `failed_label` (for the dead-letter terminal). Projects with existing in-house label vocabularies (e.g., a `claimed` label already in production from a managed-reviewer pipeline) declare `doing: claimed` in their `## Labels` and the script speaks their language end-to-end — no fork required. Projects with extra pipeline stages declare them in `## Pipeline` and add a `## Labels` line per stage (or accept the default of state-name-as-label).

## How each verb interacts with `gh`

| Verb | gh calls |
|---|---|
| `setup` | `gh repo view`, `gh label create --force` (one per in-flight stage + failed), writes AGENTS.md (including `## Pipeline` + `## Labels` declarations) + ROADMAP skeleton + commits. Flags: `--pipeline="<states>"`, `--label-<state>=<name>`, `--label-failed=<name>`. Aliases: `--claim-label=<name>` (first stage), `--failed-label=<name>` |
| `add` | `gh issue create --title "<title>"` (stub body with divider) — returns the new issue URL |
| `take` | `gh issue list` (jq-filter open issues with no in-flight label, rank by body priority + recency) or `validate_id` on the explicit number → post `advanced to=<first-stage>` comment → `gh issue edit --add-label <first-stage>` → re-read comments; if earliest first-stage claim since last `retried` has a different `branch=`, exit with `claim conflict on #N: won by branch=X` |
| `advance` | reads state + labels via `issue_state`; for todo, calls `take`; for an intermediate stage, posts `advanced to=<next>` and swaps labels (remove current, add next); when next is `done`, posts `advanced to=done [\| PR=<url>]`, removes the current label, and closes with `--reason completed` |
| `progress` | finds claim by scanning all open issues with any in-flight label, matches by `branch=$(git branch --show-current)`; `gh issue comment` |
| `cancel` | post comment + `gh issue edit --remove-label <current-stage>` + `gh issue close --reason "not planned"` |
| `fail` | post comment + `gh issue edit --remove-label <current-stage> --add-label <failed>` + `gh issue close --reason "not planned"` |
| `rescue` | reads comments for last first-stage claim or rescued line, checks timeout, posts `rescued` comment, preserves whichever in-flight label is set (fallback: first-stage), verifies post-rescue (symmetric with `take`) |
| `retry` | refuses unless `<failed>` is present, then `gh issue edit --remove-label <failed>` + `gh issue reopen` + comment |
| `status` | one `gh issue list --state all`; jq buckets every issue by pipeline state + failed label; output keys are canonical state names (todo, each in-flight stage, done, failed) regardless of label config |

## Worklog reconstruction

A task's full history is `gh issue view <n> --json comments -q '.comments[].body'`. The script's `worklog_lines` helper filters for the worklog line shape (`^- <ts> ...`) so non-conforming comments are skipped. `claim_winner_branch` applies the resolution rules from the protocol above to derive the current claimant. For deeper history work, `gh api repos/<owner>/<repo>/issues/<n>/timeline` exposes the full event timeline including state changes and label events.

## Maintain additions

The buckets in `../maintain.md` translate as:

| Bucket                       | github-issues check                                                                              |
|------------------------------|--------------------------------------------------------------------------------------------------|
| `ADVANCED BUT NOT MOVED`     | n/a — there is no separate "move" step; close happens atomically with the log comment            |
| `TIMED OUT`                  | `gh issue list --state open` jq-filtered for any in-flight label, then check the most recent claim comment's timestamp against the body's `timeout:` |
| `STALE TODO`                 | `gh issue list --state open` jq-filtered for no in-flight label and `updatedAt` older than threshold |
| `ORPHANED CLAIM`             | an issue with any in-flight label whose `branch=` from the last claim comment no longer exists on any remote — claimer abandoned the worktree |

The script's `maintain` verb prints the advisory message — these queries are agent-judgment territory, not a fixed script.

## Co-existence with other automation

When the skill and other automation both write to the same labels, **the protocol is what they should agree on** — not which tool owns the label. Two healthy patterns:

- **Owner mode (default):** the skill is the only writer of the claim/failed labels. External automation observes (filters by label, watches comments) but doesn't transition state.
- **Participant mode:** the skill is one of several writers. The skill's `current_claim` resolves by branch via comments (not by current label state), so it's robust to other automation moving the issue through intermediate states. The risk is bidirectional removal — if external automation removes the claim label as part of its own transition, the skill's view of "in-flight" diverges. Document the boundary in your project's `AGENTS.md` and stick to it.

For projects with the `agent` + `task` Matt Pocock-style pipeline (`ready → claimed → review → mergeable`), the practical answer is usually: skill is the agent-side claim tool, external automation drives `review`/`mergeable`, and the skill's `advance` to closed happens after the external pipeline has done its work. The skill doesn't try to write `review`/`mergeable` because it has no v1 concept of intermediate stages.

## What this backend deliberately doesn't do

- **Cross-tracker federation.** A task exists in exactly one tracker. Mixing maildir-* and github-issues for the same project is out of scope.
- **Custom title formats.** `add` sets title to the bare slug/title; the human re-titles via `gh issue edit` or the web UI. Title format isn't load-bearing.
- **Assignee as claim signal.** Assignment is supplementary at most (the script doesn't set it); branch-via-comments is the source of truth. Operators are free to assign issues manually for UX without affecting backlog state.
- **Cross-machine guarantees beyond GitHub's.** If `gh` is unavailable (auth expired, rate-limited, outage) the verbs fail loudly. There's no local cache or queued retry.

## Migration (sketch — not yet implemented)

From maildir-* to github-issues:

1. For each file in `backlog/todo/`, `gh issue create` with title=slug-as-title, body=spec. Capture the new issue number; old maildir slug → new issue number is the migration map for any cross-references.
2. For each file in `backlog/doing/`, do (1) then post the `advanced to=doing` claim comment + add the claim label.
3. For each file in `backlog/done/`, do (1) then replay the worklog lines as comments + close with the appropriate reason.
4. Replace `backlog/AGENTS.md`'s backend declaration; delete or archive the local task tree.

The replay step is the load-bearing one — timestamps and claimer/branch metadata in the worklog need to survive. Practical approach: keep the old maildir tree archived under `.backlog-archive/` rather than deleting, so the history stays browseable locally.

## Test coverage (followup)

`scripts/test.sh` exercises the maildir backends end-to-end against throwaway git repos. The github-issues backend is harder to integration-test — either a real test repo on GitHub (network, auth, side effects) or a mock `gh` that records calls and returns canned responses. Tracked in `backlog/todo/github-issues-test-harness-followup.md`.
