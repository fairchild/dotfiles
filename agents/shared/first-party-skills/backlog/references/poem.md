---
name: backlog-poem
description: Markdown task backlog and project roadmap (backlog/{todo,doing,done,failed}/, backlog/ROADMAP.md) for adding, advancing, recording progress, rescuing, cancelling, retrying, failing, maintenance, or reflecting on backlog priorities and roadmap direction.
license: Apache-2.0
---

# Backlog

A tracker shaped like a maildir —
one task, one file, one fate.
The folder it lives in *is* its state.

    todo/    waiting for a claim
    doing/   held in someone's hand
    done/    finished — or cancelled, the log line decides
    failed/  out of tries

Tasks move forward; there is no backward verb.
A pipeline of dirs (default `todo → doing → done`)
declared in `AGENTS.md` when it grows.

To claim is to advance:
`git mv todo/X.md doing/X.md`.
Two agents reaching for the same file
collide at the merge — loudly,
the right way to fail.

## The file, halved

Above the rule: what the author meant.
Below the rule: what the workers did.

```markdown
---
priority: 2
dependencies:
  other-slug: "why it blocks this"
---

# Task Title

problem, decisions, phases, acceptance.

---

- 2026-05-16T14:22:00Z advanced to=doing  claimer=… branch=…
- 2026-05-16T16:45:00Z progress           | prototype green
- 2026-05-17T11:03:00Z advanced to=done   | PR=…
```

The top half freezes on first commit
(only `retry` may thaw it).
The bottom half is append-only —
each worker leaves a line and moves on.
Verbs and recipes: `worker.md`.

## Frontmatter, all optional

Every field has a default,
so the smallest task is just a title and a problem:

    priority      999    declare a number when order matters
    timeout       7d     shorter when an agent owns it, longer when the world must answer
    dependencies  {}     only hard preconditions; deps resolve when done/

Other keys you write are kept but not read.
Schema, kinds, queries: `agents-schema.md`.

## Adding

Pick a kebab-case **slug**,
a **category** (`plan` / `followup` / `task-list` / `ideas`),
write enough that a fresh session can finish it
without ever having met you —
paths, commands, the deps that bind it.

Then commit, before anyone can claim.

## Working

Advance, progress, cancel,
fail, rescue, retry, status, maintain —
recipes and rules in `worker.md`.
Pipeline shape and how `advance` walks it: `pipeline.md`.

A task that can't proceed is `fail`ed honestly;
an operator may `retry` it later, back to `todo/`.
Done is done — revisits go in new tasks that name the old.

## Above the queue

`ROADMAP.md` answers *why these, in this order* —
Intent, Principles, Current Focus, named Arcs, Non-goals.
Tasks may name their arc in frontmatter.
Shape: `roadmap.md`.
To reflect, to add, to begin one: `reflect.md`.

## Other kin

`parallel-agents.md` carries the distributed-systems patterns; `workflows.md` the `init` and `migrate` recipes; `maintain.md` the advisory walks; `README.md` the background and philosophy.
