# Pipeline

How `advance` knows where to go, and how to extend the default `todo → doing → done` with intake and intermediate in-flight states.

## Default

If `backlog/AGENTS.md` has no `## Pipeline` section, the pipeline is:

```
todo → doing → done
```

In a default project, `advance` from `todo/` lands in `doing/` (with claim), and `advance` from `doing/` lands in `done/` (completion). Two steps; one verb.

`failed/` is out-of-pipeline — it's the dead-letter dir, reached only via `fail`. Nothing in the pipeline points to it; `retry` is the one way out (back to `todo/`).

## Declaring a longer pipeline

A project that wants intermediate states adds a `## Pipeline` section to `backlog/AGENTS.md`:

```markdown
## Pipeline

`todo → doing → reviewing → done`
```

Backticks and the `→` arrow are decorative; the recipe strips them. Any whitespace-separated form works.

This means:
- `advance` from `todo/` → `doing/` (claim)
- `advance` from `doing/` → `reviewing/` (e.g., PR opened, awaiting review)
- `advance` from `reviewing/` → `done/` (PR merged)

Create the intermediate directory (`mkdir -p backlog/reviewing`) and commit a placeholder if you want it visible before any task arrives. The `advance` recipe will `mkdir -p` on demand if it's missing.

## Optional intake stage

A project can add a triage queue before `todo/`:

```markdown
## Pipeline

`inbox → todo → doing → done`
```

`inbox/` is not in-flight. It is an intake bucket for untriaged work; workers claim from `todo/`, and triage advances ready items from `inbox/` to `todo/`.

## Naming convention

Intermediate dirs are gerunds: `reviewing/`, `shipping/`, `deploying/`. The directory name describes the state the task is *in*; the verb is always `advance`.

`todo/` (noun) and `done/` (past participle) are the grandfathered exceptions — they bookend the pipeline and predate the convention.

## What `advance` does

1. Find the task's current directory.
2. Read the pipeline from `backlog/AGENTS.md` (or use the default).
3. Find the next directory in the chain.
4. `git mv` the file there.
5. Append a log line: `- {ts} advanced to=<next> [claimer=X branch=Y]`. Claimer/branch are only stamped when entering from `todo/` (the claim moment) or via `rescue`.
6. Commit.

A task in the last in-flight dir advances to `done/`. The log line for completion: `- {ts} advanced to=done | PR=<url>` (PR URL optional).

## Timeouts in intermediate states

The timeout clock anchors to the latest `advanced` or `rescued` log line, *not* to `started`. Each forward step is evidence the claimer is alive and the work has changed phase — so advancing into a slow stage (e.g. `reviewing/`, where you're waiting on a human) gives that stage its own budget.

If a stage needs a different budget from the task's overall `timeout:`, the project should either:
- accept the single-budget model (simple; one number governs the slowest stage)
- declare per-stage budgets in the project's AGENTS.md as social convention (the recipes don't read it, but authors set `timeout:` per task accordingly)

The skill doesn't ship per-stage timeouts. Add that complexity only if observation says you need it.

## What stays unchanged in the simple case

A project that doesn't declare a pipeline pays no cost:

- `backlog/` has only `todo/`, `doing/`, `done/` (+ lazy `failed/`).
- `advance` walks the default two-step chain.
- `AGENTS.md` doesn't need a Pipeline section.
- All verbs read the same.

The pipeline mechanism is opt-in by directory creation and one line in AGENTS.md.
