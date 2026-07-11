# Backend: maildir-git

Storage mechanism for projects whose `backlog/AGENTS.md` declares `## Backend: maildir-git`. The original design — single-worktree-friendly. The committed git tree is the whole truth: every state lives under `backlog/{todo,doing,done,failed}/` and every transition is a `git mv` + log-line append + commit.

Verb semantics: `../worker.md`. The canonical implementation is `../../scripts/backlog-maildir-git.sh` (invoke via `../../scripts/backlog.sh <verb>`). This doc describes the mechanism — for bash, read the script.

## When to pick this backend

- Single-worktree project, or projects that always merge before parallel work begins.
- Projects that prize "git history is the only source of truth" over cross-worktree coordination.

If two agents work the same repo in separate worktrees, prefer `maildir-shared` — the cross-worktree race is real and this backend can only catch it at merge time.

## Layout

```
backlog/
  todo/       committed; available work
  doing/      committed; in-flight (plus reviewing/, etc., if pipeline declares)
  done/       committed; terminal — completion and cancellation
  failed/     committed; dead-letter, created on demand
  AGENTS.md   committed
  CLAUDE.md   → AGENTS.md
  ROADMAP.md  committed
```

## How each verb interacts with git

Every verb is some combination of `git mv` + appended log line + `git commit`. The pipeline declaration in `backlog/AGENTS.md` tells `advance` what counts as "the next dir."

| Verb | Mechanism |
|---|---|
| `add` | Write file to `todo/`, `git add` + commit |
| `take` / `advance` from `todo/` | `git mv todo/X.md doing/X.md`, append claim log line, commit |
| `progress` | Append note to current claim file, commit |
| `advance` (intermediate or to done) | `git mv` to next pipeline dir, append `advanced` log line, commit |
| `cancel` | `git mv` to `done/`, append `cancelled` log line, commit |
| `fail` | `git mv` to `failed/`, append `failed` log line, commit |
| `rescue` | In-place — append `rescued` log line, commit (no move) |
| `retry` | `git mv failed/X.md todo/X.md`, append `retried` log line, optionally edit spec, commit |

## Race semantics

Two agents racing the same `git mv` on different branches both succeed locally and collide at merge. That's the documented failure mode — "the explicit failure mode, not silent double-work" — but in multi-worktree flows it can surface weeks after the wasted work happened. If that's a real cost, pick `maildir-shared`.

## Maintain

The buckets in `../maintain.md` apply. Backend-specific note: `ADVANCED BUT NOT MOVED` (a file in an in-flight dir whose log already shows `advanced to=done`) is safe to auto-fix here — the proof of completion is the log line, the `git mv` just needs to run.
