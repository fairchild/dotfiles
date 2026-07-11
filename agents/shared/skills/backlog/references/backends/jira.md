# Backend: jira

Storage mechanism for projects whose `backlog/AGENTS.md` declares `## Backend: jira`. Built for teams whose durable planning already lives in Jira and where a local maildir or GitHub Issues mirror would split the queue.

This backend uses Atlassian CLI (`acli`) as the transport:

- `acli jira auth ...` for authentication
- `acli jira workitem create/search/view/edit/comment/transition` for backlog verbs
- `jq` for JSON extraction from `--json` output

Verb semantics (the protocol-level recipes): `../worker.md`. Implementation: `../../scripts/backlog-jira.sh`.

## When to pick this backend

- The team already triages and prioritizes in Jira.
- Non-agent collaborators need to see claim/progress state in Jira.
- Multiple machines or users need a single remote queue.
- Jira workflow statuses are stable enough to map to `todo -> doing -> done`.

For local-only single-machine work, `maildir-git` is simpler. For multi-worktree work on one clone, `maildir-shared` is more inspectable and has fewer SaaS/API failure modes. For GitHub-native projects, prefer `github-issues`.

---

# Setup

## Prerequisites

Install and authenticate Atlassian CLI before setup:

```bash
acli jira auth login --web
acli jira auth status
```

For non-browser environments, Atlassian CLI also supports site/email/token auth:

```bash
acli jira auth login --site "mysite.atlassian.net" --email "user@example.com" --token < token.txt
```

Confirm basic Jira access:

```bash
acli jira workitem search --jql 'project = TEAM' --limit 5 --json
```

## Recommended setup command

Run from the repo root:

```bash
skills/backlog/scripts/backlog.sh setup \
  --backend=jira \
  --project=TEAM \
  --type=Task \
  --label=backlog \
  --status-todo="To Do" \
  --status-doing="In Progress" \
  --status-done="Done" \
  --status-failed="Failed"
```

If your Jira workflow has a distinct cancelled terminal status, add:

```bash
--status-cancelled="Canceled"
```

If you use a custom membership predicate instead of the default `project = TEAM AND labels = "backlog"`, pass:

```bash
--jql='project = TEAM AND component = "Agent Backlog"'
```

`jql` is a membership predicate, not a full reporting query. Do not include `ORDER BY`; the script appends status filters for `take` and status-specific scans.

## What setup creates

Setup writes and commits:

- `backlog/AGENTS.md`
- `backlog/CLAUDE.md -> AGENTS.md`
- `backlog/ROADMAP.md`

It does not create Jira projects, statuses, workflows, or custom fields. Those must already exist. If Jira requires custom fields on create, the default `add` verb may fail; see "Custom create fields" below.

---

# The protocol

Jira work items returned by `## Jira jql:` are the queue. There is no local `todo/`/`doing/`/`done/` tree. The local repo holds only the convention declaration (`backlog/AGENTS.md`) and roadmap (`backlog/ROADMAP.md`).

## Configuration in `backlog/AGENTS.md`

The script reads:

```markdown
## Jira

project: TEAM
type: Task
label: backlog
jql: project = TEAM AND labels = "backlog"

## Pipeline

todo -> doing -> done

## Statuses

todo: To Do
doing: In Progress
done: Done
failed: Failed
cancelled: Done
```

For an extended pipeline:

```markdown
## Pipeline

todo -> doing -> reviewing -> done

## Statuses

todo: To Do
doing: In Progress
reviewing: In Review
done: Done
failed: Failed
cancelled: Canceled
```

Every pipeline state must map to an existing Jira workflow status, and the workflow must allow the transitions the script asks for.

## State mapping

For the default pipeline:

| Backlog state | Jira status | Meaning |
|---|---|---|
| todo | `todo:` status | available to claim |
| doing | `doing:` status | claimed / in flight |
| done | `done:` status | completed |
| failed | `failed:` status | dead-lettered; `retry` may move it back to todo |
| cancelled | `cancelled:` status | counted as done; log line discriminates |

`cancel` and ordinary `done` can share the same Jira status. The worklog comment distinguishes them.

## Identifiers

Tasks are referenced by Jira work item key: `TEAM-123`.

`take TEAM-123`, `advance TEAM-123`, `fail TEAM-123 "reason"`, and `retry TEAM-123 "reason"` all use the Jira key directly. There are no slug labels or parallel identifiers.

## The worklog convention

Every state transition and progress note is one Jira comment:

```text
- <ISO-8601 ts> <verb> [args] | <trail>
```

| Verb | Args / trail |
|---|---|
| `advanced to=<first-stage>` | `claimer=<who>` `branch=<git-branch>` |
| `advanced to=<intermediate>` | no extra args |
| `advanced to=done` | optional `| PR=<url>` |
| `progress` | `| <note>` |
| `cancelled` | `| <reason>` |
| `failed` | `| <reason>` |
| `rescued` | `claimer=<who>` `branch=<git-branch>` |
| `retried` | `| <reason>` |

Comments are append-only. The current Jira status is the state bucket; the comments are the audit log and claim-resolution source.

## Claim resolution

The **branch** is the claim identity. Agents may share one Jira account or API token, so assignee is not reliable as an ownership signal.

Walking worklog comments in chronological order:

| Comment kind | Effect |
|---|---|
| `retried` | resets the contest |
| `advanced to=<first-stage>` | first-wins; sets the winner only if currently empty |
| `advanced to=<intermediate>` | no ownership effect |
| `rescued` | overrides the current winner after timeout |

The earliest first-stage claim since the most recent `retried`, optionally overridden by a later `rescued`, is the canonical claimer.

---

# Operating directly via `acli`

The protocol is sufficient to participate without the script. Substitute your configured statuses and JQL from `backlog/AGENTS.md`.

**Add a task:**

```bash
acli jira workitem create \
  --summary "rewrite-auth-middleware" \
  --project "TEAM" \
  --type "Task" \
  --label "backlog" \
  --description $'# rewrite-auth-middleware\n\n[problem, decisions, phases, acceptance]\n\n---' \
  --json
```

**Claim a task:**

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
BR=$(git branch --show-current)
WHO="$(whoami)@$(hostname -s)"
acli jira workitem comment create --key TEAM-123 --body "- $TS advanced to=doing claimer=$WHO branch=$BR"
acli jira workitem transition --key TEAM-123 --status "In Progress" --yes
```

Then verify the claim winner by reading comments:

```bash
acli jira workitem view TEAM-123 --fields comment --json \
  | jq -r '.fields.comment.comments[].body'
```

Apply the claim resolution rules above. If an earlier first-stage claim from another branch won, do not continue the task.

**Make progress:**

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
acli jira workitem comment create --key TEAM-123 --body "- $TS progress | first cut passing locally"
```

**Advance to done with PR:**

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
PR=$(gh pr view --json url -q .url 2>/dev/null || true)
acli jira workitem comment create --key TEAM-123 --body "- $TS advanced to=done | PR=$PR"
acli jira workitem transition --key TEAM-123 --status "Done" --yes
```

**Cancel:**

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
acli jira workitem comment create --key TEAM-123 --body "- $TS cancelled | spec was wrong"
acli jira workitem transition --key TEAM-123 --status "Done" --yes
```

**Fail:**

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
acli jira workitem comment create --key TEAM-123 --body "- $TS failed | upstream API changed"
acli jira workitem transition --key TEAM-123 --status "Failed" --yes
```

**Retry:**

```bash
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
acli jira workitem transition --key TEAM-123 --status "To Do" --yes
acli jira workitem comment create --key TEAM-123 --body "- $TS retried | upstream contract clarified"
```

---

# The script

The bundled `backlog-jira.sh` automates the protocol. It is one client over Jira, not the owner of Jira.

## How each verb interacts with `acli`

| Verb | Atlassian CLI calls |
|---|---|
| `setup` | validates `acli jira auth status`; writes `AGENTS.md` sections for project/type/label/JQL/pipeline/statuses; writes ROADMAP; commits locally |
| `add` | `acli jira workitem create --summary ... --project ... --type ... --description ... --label ... --json` |
| `take` | searches `(<jql>) AND status = "<todo-status>"`; posts first-stage claim comment; transitions to first in-flight status; re-reads comments to confirm branch won |
| `advance` | reads current status; for `todo` delegates to `take`; for in-flight states posts `advanced to=<next>` and transitions to next status |
| `progress` | scans in-flight statuses, finds the item whose claim winner branch matches the current branch, posts `progress` |
| `cancel` | posts `cancelled`; transitions to `cancelled:` status, defaulting to `done:` |
| `fail` | posts `failed`; transitions to `failed:` status |
| `rescue` | checks timeout from description frontmatter, posts `rescued`, confirms branch winner |
| `retry` | requires `failed:` status; transitions to `todo:`; posts `retried` |
| `status` | searches membership JQL and buckets work items by configured status |

## Custom create fields

Many Jira projects require fields beyond summary/project/type/description/label. If `add` fails with a required-field error, use Atlassian CLI's JSON path to learn the required payload:

```bash
acli jira workitem create --generate-json
```

Then adapt `cmd_add` in `../../scripts/backlog-jira.sh` to write a temporary JSON payload and call:

```bash
acli jira workitem create --from-json workitem.json --json
```

Keep the protocol unchanged: summary is human-friendly, description includes the backlog spec plus divider, and the created item must match the membership JQL.

## Transition failures

Jira workflows can require transition screens, resolution values, or restricted transitions. The adapter deliberately calls:

```bash
acli jira workitem transition --key TEAM-123 --status "Done" --yes
```

If Jira rejects that, fix the project workflow or extend `transition_key` for that project's required transition payload. Do not paper over failed transitions by only adding comments; status is the state bucket.

## JSON shape assumptions

Atlassian CLI documents `--json` and examples such as:

```bash
acli jira workitem view ACLI-100 --json | jq '.fields.summary'
```

The script accepts the common shapes: arrays, `.issues`, `.values`, `.items`, `.data`, and field objects under `.fields`. If Atlassian changes output shape, the failure point should be one of the small `jq` filters in `backlog-jira.sh`.

## Maintain additions

The buckets in `../maintain.md` translate as:

| Bucket | Jira check |
|---|---|
| `ADVANCED BUT NOT MOVED` | worklog says `advanced to=<state>` but Jira status still shows the prior status |
| `TIMED OUT` | membership JQL filtered to in-flight statuses, then compare most recent claim/progress/rescue timestamp to `timeout:` in description |
| `STALE TODO` | membership JQL filtered to todo status and old `updated` timestamp |
| `ORPHANED CLAIM` | in-flight work item whose claim branch no longer exists on any remote |
| `UNKNOWN STATUS` | work item matches membership JQL but status is not declared in `## Statuses` |

The script's `maintain` verb only points at these docs. Jira-specific cleanup needs agent judgment because every workflow differs.

## What this backend deliberately does not do

- **No workflow provisioning.** It does not create Jira statuses, transitions, screens, fields, or boards.
- **No cross-tracker federation.** A task exists in exactly one tracker.
- **No assignee ownership.** Assignment is optional UX; branch-via-comments is the claim signal.
- **No local cache.** If `acli` is unavailable, unauthenticated, rate-limited, or Jira is down, verbs fail loudly.
- **No universal custom fields.** Required custom fields are project-specific and must be added by the project using the generated JSON path above.

## Migration sketch

From maildir-* to Jira:

1. For each file in `backlog/todo/`, create a Jira work item with summary=slug/title, description=file content, and the backlog membership label or fields.
2. For each file in `backlog/doing/`, create a Jira work item, replay the claim/progress worklog lines as comments, then transition to the mapped in-flight status.
3. For each file in `backlog/done/`, create a Jira work item, replay the worklog, then transition to the mapped done or cancelled status.
4. For each file in `backlog/failed/`, create a Jira work item, replay the worklog, then transition to the mapped failed status.
5. Replace `backlog/AGENTS.md`'s backend declaration and archive the old maildir tree under `.backlog-archive/`.

Keep the old files until a human verifies Jira history and cross-references.

## Test coverage

This backend has syntax coverage and docs, but no live integration test in this repo because it needs a real Jira project with known workflow statuses and side-effect-safe work items.

Before enabling it on a real project, run this smoke test on a disposable Jira project:

```bash
skills/backlog/scripts/backlog.sh setup --backend=jira --project=TEAM --label=backlog
skills/backlog/scripts/backlog.sh add sample plan
skills/backlog/scripts/backlog.sh take TEAM-123
skills/backlog/scripts/backlog.sh progress "adapter smoke"
skills/backlog/scripts/backlog.sh advance TEAM-123
skills/backlog/scripts/backlog.sh status
```

Replace `TEAM-123` with the created key from `add`.
