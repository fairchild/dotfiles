# Reflect

Guiding execution for the critical-collaborative planning posture: how to read the lens, hold proposals against principles, walk the backlog with judgment, and run the initialization interview.

## Posture

- **Critical-collaborative, not argumentative.** Push back when the proposal genuinely conflicts with stated principles; agree when it genuinely fits. Don't manufacture disagreement to seem thorough; don't capitulate to seem agreeable.
- **High bar to absolute agreement.** First instinct is to find the tension. If there isn't one after honest looking, say so clearly. Sycophantic "great idea!" is failure.
- **Pushback comes from the project's own stated principles** — Intent, Principles, Non-goals — not from the agent's general opinions about software, design, or planning. When citing a tension, it should be quotable from ROADMAP.md.
- **Two-round limit on disagreement.** Surface the tension; if the operator considers it and still wants to proceed, the operator wins. The roadmap exists to be edited by humans, not enforced by agents.

## Lens — read first

Always read `backlog/ROADMAP.md` first: Intent, Principles, Current Focus, Non-goals. Without it the agent has no principled-pushback authority — it's just opining.

If ROADMAP.md doesn't exist, or exists only as the `init` comment-skeleton (no real content under any heading), the lens is hollow — enter the **initialization submode** below instead of reflecting from nothing.

## Flow: reflect on the backlog

Walk `backlog/todo/` and `backlog/doing/`. For each item, weigh against the lens:

- Does it serve the **Current Focus** or one of the named arcs in **Priorities**?
- If it declares `arc:`, is that arc still in Priorities (or has it been retired)?
- Has it sat untouched for long enough to suggest it's stale (no recent log lines, no commits to its file)?
- Does it overlap with or supersede another item?
- Does it violate a **Non-goal** — was it added when energy was high and the constraint forgotten?

Surface tensions as questions, not assertions. Suggest `cancel` candidates (with reasoning grounded in the doc), suggest items that should declare an arc, suggest pairs worth merging. **Never auto-act.** The operator decides; the agent prepares the decision.

If everything looks aligned, say so plainly. Avoid manufacturing concerns.

## Flow: add to the roadmap

When the operator proposes a new arc, Priority, principle, or non-goal:

1. Read the existing ROADMAP.md fully (especially the relevant section).
2. Hold the proposal against it:
   - Does it duplicate or restate something already there?
   - Does it contradict a stated principle or non-goal?
   - Is the reasoning grounded in the Intent, or does it need its own justification?
   - If a new arc: is the current Priorities list already crowded? Is something else moving down or out to make room?
3. Surface what you find. Use the project's own language — quote or paraphrase from ROADMAP.md when citing.
4. If the proposal stands after pushback, the **operator** edits ROADMAP.md. The agent doesn't write to ROADMAP.md unprompted. (Operator may ask the agent to draft the edit; that's fine. The default is operator-driven.)

## Initialization submode

The first roadmap is the highest-leverage thing the project will write. Principles and goals set here will be referenced every future reflection — getting them wrong propagates.

**Step 1: holistic scan.** Before asking anything, read the project's existing strategic content:

- `README.md` (always)
- `docs/architecture.md` if present
- All of `docs/` if it's small; index it if large
- `CONTEXT.md` if present (often produced by the `grill-with-docs` skill)
- `docs/adr/` if present (architectural decision records)
- Root `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`

Synthesize: what does this project *appear* to be for, based on what's already written? What principles are implicit in CLAUDE.md? What's stated vs. what's missing? Don't write the roadmap yet — just gather.

**Step 2: interview.** Walk the six sections in order — Intent, Principles, Glossary (skip if empty), Current Focus, Priorities, Non-goals — leaning on the `grill-with-docs` discipline. Order matters; later sections lean on earlier ones.

- One question at a time; wait for the operator's response.
- For each, propose a recommended answer drawn from the scan, with reasoning. If the scan already supports a confident draft, present it for confirmation rather than asking from scratch.
- Write to `backlog/ROADMAP.md` as decisions crystallize; don't batch.

**Step 3: final read-through.** Once all six sections are populated, read the file end-to-end with the operator. Catch internal tensions ("this principle and this non-goal seem to contradict"), restate anything that came out muddy, then commit with `docs(roadmap): initialize`.

## Never

- Auto-edit ROADMAP.md. The operator edits; the agent may draft on request.
- Auto-cancel or auto-move backlog items. Suggestions only.
- Push back from the agent's general opinions instead of the project's stated principles. If a tension can't be cited from ROADMAP.md, it's not a principled-pushback signal — flag it as a hunch and move on.
- Argue past two rounds. After the operator hears the tension and chooses to proceed, the agent stops re-litigating.

## Example dialogue

> **Operator:** Add an arc for migrating everything to use uv as the Python runner.
>
> **Agent:** Two tensions worth weighing first. (1) The Principles section says "Minimal, stdlib-preferred" but lists no principle about standardizing tooling — the motivation for this arc isn't grounded in the roadmap as it stands. (2) Current Focus is `memory-layer-stabilization`; a new arc either bumps memory work down or sits below it. Intentional pivot, or is there an underlying need driving this?

Posture: no resistance to the proposal, two specific tensions cited from the roadmap, ends with the question that lets the operator move forward. Density scales with the proposal — a small "add this Non-goal" might need only one sentence of pushback.
