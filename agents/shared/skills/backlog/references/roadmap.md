# ROADMAP.md — strategic counterpart to the tactical backlog

The backlog answers *what's the next thing to do*; the roadmap answers *why these things, in this order, and not others*. Without one, principles and goals live only in the operator's head, and the backlog drifts session to session for lack of a shared lens.

## Placement

`backlog/ROADMAP.md`. Sibling to `backlog/AGENTS.md`, co-located with the queue so direction and current state are one `cat` apart. Reflection sessions read it before touching the backlog. The `init` recipe in `references/workflows.md` scaffolds it.

## Shape — six sections, fixed order, free prose inside

```markdown
# ROADMAP

## Intent
[One paragraph. What this project ultimately intends to be. Stable across
quarters — if it changes monthly, it isn't the intent.]

## Principles
[3–7 short statements. What values guide decisions when tradeoffs come up.
Each principle earns its line by ruling things out, not by sounding nice.]

## Glossary
[Optional. Only terms with real ambiguity in this project. Skip if empty —
the section header is a reminder, not a quota.]

## Current Focus
[1–3 paragraphs. The active arc — what we're pushing on right now, why now,
and what "done with this arc" looks like. This is the section that changes
most often.]

## Priorities
[An ordered list of named arcs (kebab-case, short), each with one or two
sentences of reasoning. Not task slugs — tasks reference arcs, not the
other way around. Order encodes intent.]

## Non-goals
[Things we are explicitly *not* doing right now, even though they'd be
reasonable. The list of dragons we're choosing not to fight. Protects
against scope creep — when the same "no" gets said twice, promote it here
so future-you doesn't re-litigate.]
```

The skeleton survives drift; the prose inside each section stays human. Order matters because top sections (Intent, Principles) ground the rest — a reader scanning top-down gets the values before the tactics.

## Reverse linkage: tasks reference arcs

ROADMAP's `Priorities` lists arc *names*, not task slugs. Tasks declare which arc they serve via an optional `arc:` frontmatter field:

```yaml
---
priority: 2
arc: memory-layer-stabilization
---
```

The `arc:` field is absorbed by the existing schema rule that preserves additional keys without interpreting them (see `agents-schema.md`). No recipe reads it; it's a documented convention.

**One arc per task.** A task that genuinely serves two arcs is two tasks. This matches the backlog's atomic-task philosophy and keeps `grep` queries unambiguous.

Queries are grep-shaped:

```bash
# Queued or in-flight under an arc:
grep -l '^arc: memory-layer-stabilization' backlog/{todo,doing}/*.md

# Shipped under an arc:
grep -l '^arc: memory-layer-stabilization' backlog/done/*.md

# Active tasks with no arc:
for f in backlog/{todo,doing}/*.md; do
  grep -q '^arc:' "$f" || echo "$f"
done
```

The arc name is the contract; everything else is emergent. ROADMAP never enumerates tasks, so completing a task never drifts ROADMAP. A task changing arcs is one frontmatter edit; an arc being renamed is `grep -l ... | xargs sed -i ''` away.

## Maintenance rhythm by section

| Section        | Edit when                                                     |
|----------------|---------------------------------------------------------------|
| Intent         | The project's intent actually shifts (months apart, rare). |
| Principles     | A new principle emerges from real friction, or one stops mattering. |
| Glossary       | A term has caused real ambiguity. Empty is fine.             |
| Current Focus  | The active arc completes or the project pivots.              |
| Priorities     | The arc ordering changes, an arc is added, or one is dropped. |
| Non-goals      | You catch yourself saying "no" to the same proposal twice — promote it. |

The roadmap is a low-cadence doc. If it's being edited every session, something is wrong: either the sections are mis-shaped, or the prose is too task-y (those should be backlog items, not roadmap text).

## Commit convention

ROADMAP changes get their own commit with the `docs(roadmap):` prefix — never bundled with code or backlog state changes. This mirrors the backlog's "every action = one bullet + one commit" discipline and makes `git log --grep='docs(roadmap)'` a clean history of strategic shifts.

## No verbs

ROADMAP isn't lifecycle-shaped. Editing it is a thinking act, not a state transition. When the operator wants help — adding an arc, refining a principle, weighing a non-goal — that's the *reflective-planning* mode in `reflect.md`.

## Initialization

A fresh roadmap is the highest-leverage moment in the project's life; principles and goals set here are referenced every future reflection. Don't write it from a blank template — let the `init` flow in `references/workflows.md` hand control to `reflect.md`'s initialization submode, which scans existing project docs and walks the six sections as an interview.

## A worked example (sketch)

```markdown
# ROADMAP

## Intent
A working `~/.claude/` configuration that treats each Claude Code session as
worth remembering. Memory is the throughline; everything else is supporting
infrastructure.

## Principles
- Minimal, stdlib-preferred. External packages earn their place by clear value.
- Code can be poetry. Density of value per token in every artifact.
- Inspectable in place. `ls`, `cat`, and `git log` should tell the story.
- Single source of truth per concept. Drift between specs and code is failure.

## Current Focus
Stabilizing the chronicle memory layer. The session-end extraction works but
recall is rough — agents starting new sessions don't reliably pick up the
threads that matter. Done with this arc: a new session in a known project
reliably surfaces the last open thread without prompting.

## Priorities
1. **memory-layer-stabilization** — Recall quality is the highest-friction
   gap; pays off everywhere because every other workflow assumes memory works.
2. **skill-catalog-cleanup** — Several skills overlap or reference deleted
   scripts; before adding more, the catalog needs to stay navigable.
3. **backlog-dogfood** — Migrate this repo's own `backlog/` to the new
   maildir layout and exercise the full lifecycle end-to-end.

## Non-goals
- Building a workspace orchestrator inside dotclaude. Conductor and cmux
  handle this; the config layer doesn't need to compete.
- Real-time multi-user collaboration. Personal config; collaborators
  cherry-pick.
```
