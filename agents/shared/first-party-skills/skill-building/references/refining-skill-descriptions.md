# Refining Skill Descriptions

The description field's primary job is **invocation matching** — helping the model decide when to invoke the skill. It also serves a secondary audience: humans browsing skill registries or catalogs who want to understand what each skill does at a glance. The two purposes overlap heavily, and the same shape serves both. It is not the place to document the skill, list features, or explain design rationale — those belong in `SKILL.md`'s body.

This doc captures heuristics from real refinement sessions for making descriptions tight, intentional, and matcher-aligned.

## What the description is for

Two overlapping audiences:

- **Agent matching (primary)** — the model deciding when to invoke this skill against a user request.
- **Human inspection (secondary)** — operators scanning a skill registry or catalog to understand at a glance what each skill does.

Both want nearly the same surface. Effective descriptions front-load:

1. **Primary keyword.** The noun a user would type for this domain (`backlog`, `prototype`, `chronicle`).
2. **Trigger phrasings.** Verbs or gerunds matching how users actually phrase requests (`adding`, `taking`, `recording progress`).
3. **Disambiguators.** Just enough context to differentiate from similar skills.

Humans want a touch more "what is this" framing than the matcher strictly needs, but a well-shaped trigger list ("for adding, taking, recording progress, ...") does double duty — it tells the matcher what to invoke for *and* tells a human what the skill operates on. Optimize for the matcher; the inspection benefit follows for free.

Nothing else earns its space.

## Keep vs. cut

| Keep                                       | Cut                                                  |
|--------------------------------------------|------------------------------------------------------|
| The domain noun                            | Architecture details (file format, internal layout)  |
| Verbs the user would actually type         | Implementation mechanics (recipe shape, lock primitives) |
| Compact path or structure if distinctive   | Design rationale ("designed for X workflow")         |
| One disambiguating qualifier               | Audience qualifiers that narrow unnecessarily        |

The last one is sneaky. "For parallel agents," "for data scientists," "for production code" sound informative but tell the matcher *who not to invoke for*. If the skill works for a broader audience, drop the qualifier — keeping it can suppress matches the skill would have handled fine.

## Inferable on inspection

A good description is dense enough that an agent encountering the skill's working files (e.g., via `ls`) can infer the system from the description alone — *before* reading SKILL.md. Pack distinctive structure into the description:

- A path like `backlog/{todo,doing,done}/` tells an agent the directory shape immediately
- A naming convention like `{slug}-{category}.md` signals the filename pattern
- A delimiter or marker like `^---$ divider` signals body structure

If the description includes a *file-level* signal that maps to what the agent would see in the project, the system bootstraps without a SKILL.md round-trip.

## Shape options

Different rhetorical structures suit different needs:

- **Trigger-leading** — "Use when adding, taking, ..." Highest matcher confidence; ideal for skills where the user phrasing varies a lot.
- **Frame-leading + triggers** — "Markdown task backlog (...). Use when adding, ..." Best for skills where the framing itself disambiguates.
- **For-linked** — "Markdown task backlog (...) for adding, taking, ..." Single sentence; reads naturally; gerund-tasks match user verbs.
- **Telegraphic** — "Markdown task backlog (...); verbs: add, take, ..." Maximum density; slight risk that bare verb stems don't expand to user phrasings.

There's no single right shape. Pick the one whose density and rhythm match the skill's character.

## One sentence or two?

- **One sentence** is tighter and forces fusion of framing and triggers. Best when the framing is short.
- **Two sentences** allow clearer separation ("here's what it is. Here's when to invoke it."). Best when the framing needs its own phrase to land.

Default to one; reach for two if the fusion gets awkward.

## Refinement process

1. **Read the current description against its purpose.** For each phrase, ask: "does this map to something a user would type, or does it describe internal mechanics?"
2. **Categorize each phrase as keeps-matching or doesn't.** Cut the doesn't-keepers.
3. **Watch for audience qualifiers** sneaking in as "for X" framing. Most are design rationale, not selection criteria.
4. **Compress paths and structure** if distinctive — shell brace expansion (`dir/{a,b,c}/`) is agent-readable.
5. **Try variants** at different densities (telegraphic, named-verb, gerund-tasks, trigger-leading). Pick by which density and shape suit the skill.
6. **Verify inferability** — could an agent figure out the system from just the description + `ls`?

## Worked example: the backlog skill

Original (540 chars, ~85 words):

> Maildir-style backlog for parallel agents. Tasks are markdown files in todo/, doing/, or done/ — location is status, claim is an atomic git mv. Body has two halves divided by `---`, an author-set description above and an append-only bullet log of timestamped events below. Use when adding deferred work, taking the next task, recording progress, completing, cancelling, reopening, releasing, or grooming. Every verb is a small bash recipe: optional `git mv`, append one log line, commit.

What was cut and why:

| Cut                                                              | Why                                              |
|------------------------------------------------------------------|--------------------------------------------------|
| `Maildir-style`                                                  | Design aesthetic; users don't say "maildir"      |
| `location is status, claim is an atomic git mv`                  | Internal mechanics                               |
| `Body has two halves divided by ---, ...append-only bullet log` | Implementation detail; SKILL.md body covers it   |
| `Every verb is a small bash recipe: optional git mv, ...commit`  | Recipe architecture; SKILL.md body covers it     |
| `for parallel agents`                                            | Audience qualifier; skill works fine solo too    |
| `deferred work, ... the next task`                               | Compressed to bare gerunds; same matching surface |

Final (155 chars, one sentence):

> Markdown task backlog (backlog/{todo,doing,done}/) for adding, taking, recording progress, completing, cancelling, reopening, releasing, or grooming tasks.

29% of original. Three keywords up front (`Markdown`, `task`, `backlog`), the path inline as a parenthetical disambiguator that doubles as the inspection-inferability hint, and the verb list as triggers.

## Checklist for a final read

- [ ] Domain noun appears early
- [ ] Verbs / gerunds match how users phrase requests
- [ ] No internal mechanics or architecture details
- [ ] No audience qualifiers narrowing matches unnecessarily
- [ ] If there's a distinctive structure (path, filename pattern), it's in the description
- [ ] One sentence unless fusion gets awkward
- [ ] An agent could figure out the system from the description + `ls` of the working files
