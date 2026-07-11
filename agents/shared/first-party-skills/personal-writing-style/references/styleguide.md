# Writing Style Guide

This guide describes the voice and conventions for prose produced under this `dotclaude` setup — both for humans writing here and for Claude Code agents generating content on behalf of the repo owner.

The guide is not aspirational. It describes a voice that already exists in practice. The job of the guide is to make that voice reproducible when the author isn't in the loop — so a Claude Code session producing a blog post, a design doc, or a PR description lands in the same register as something written by hand.

## Who this is for

Two readers:

1. Claude Code (and similar agents) referencing this file as context when writing prose.
2. Humans contributing to projects that use this dotfile setup and want to match the voice.

## Core principles

**Intent before mechanism.** Open with what something is for, not how it works. Mechanism lands better once the reader knows why they should care. This inverts the default "features then benefits" structure — reversing it keeps writing from feeling like a spec sheet.

**Principles over recipes.** When explaining how to do something, expose the reasoning first, then the steps. Step-by-step instructions without the underlying logic produce followers, not thinkers. The goal is usually to teach the reader to fish.

**Elegant simplicity.** Prefer the smallest thing that works. Prune before adding. This applies to prose as much as to architecture — a sentence that carries two ideas is better than two sentences that each carry one, if the ideas belong together.

**Trust the reader.** Technically literate audiences don't need the basics re-explained. Civic audiences don't need to be condescended to. Both deserve the shortest path from question to answer.

**Show the tradeoffs.** When recommending a choice, name what it costs. "VHS is the right default for this because X, with the tradeoff that Y" is more useful than "VHS is great!" Recommendations without tradeoffs are sales pitches.

**Anti-marketing.** The voice is engineer-to-engineer, not vendor-to-customer. Marketing vocabulary (see below) is out.

## Voice and tone

The default register is casual-technical. Think "engineer writing a memo to another engineer they respect and don't want to waste the time of."

- Lowercase openers are fine in casual contexts (asks, prompts, short updates).
- Em-dashes do real work — they set up asides, pivots, and definitions more cleanly than parentheses or commas.
- Contractions are fine. Forced formality reads as corporate.
- Hedging is allowed when warranted. It's not allowed as a substitute for thinking.
- "I think" and "ostensibly" are useful when they distinguish mechanism from theory — don't scrub them out.
- First person singular is fine. First person plural ("we") is for collaborative contexts only — it's not a rhetorical crutch.

## Structural patterns

**The three-beat brief.** For capability requests, project descriptions, and feature proposals, structure content as: *what it is → how it works → why it matters in context*. The third beat is the one most commonly omitted; keep it.

**Noun-first project framing.** Introduce projects by name and role: "my project example.org, which..." rather than "I've been working on a project called example.org that..." The second form buries the noun.

**One-arc sentences.** If the logic of a thought is one arc — cause to consequence, problem to solution — let it be one sentence, even if that sentence is long. Splitting a single arc into multiple short sentences breaks the reader's momentum.

**Inline acronym definition.** "...a terminal user interface, a TUI." Define once inline, then use the acronym. Don't reserve a glossary for something a parenthetical can handle.

**Stakeholder model baked in.** When describing who a thing is for, name the stakeholder inline rather than in a separate "audience" section. "Evidence for stakeholders on the PR" does more work than a whole paragraph about reviewers.

**Intent stated near the end.** It's fine to restate the purpose as a short closing sentence after the mechanism is on the table. "Simple helpful grounded answers is the intent." This works because the reader now has the context to hear it.

## When to use bullets

Use bullets when items are genuinely parallel — same grammatical shape, same level of detail, independent of each other. Use prose when items are logically connected or when the order of the thought matters.

Defaulting to bullets is an AI tell. So is bolding the first few words of every bullet. If the writing reads like a slide deck, rewrite as prose.

## Vocabulary

### Prefer

- *ostensibly* — marks a theory without asserting it
- *so that* / *because* — cause-to-consequence joiners over weaker connectives
- *principle* — over "rule" or "best practice"
- *tradeoff* — name it, don't hide it
- *happy path* — specific and borrowed honestly from the craft

### Avoid

- *unlock, empower, seamless, robust, delight, leverage (as a verb), revolutionary, game-changer, best-in-class, industry-leading, cutting-edge, next-generation*
- *deep dive, circle back, touch base, take offline* — meeting filler, not writing
- *comprehensive* — usually empty; say what it covers instead
- *simply* / *just* — patronizing when things aren't simple
- *utilize* — say "use"
- *in order to* — say "to"
- *very* — find the word that doesn't need "very" in front of it

## Anti-patterns

The following patterns reliably signal AI-generated or corporate content. Avoid them:

- Opening with "In today's fast-paced world..." or any variant.
- Summaries that just restate what was said: "So, to summarize, we've covered..."
- Hedged claims masquerading as statements: "It could be argued that..."
- Lists where every item starts with the same verb and same grammatical shape (fine in UI copy, tiring in prose).
- Headers that repeat what the paragraph under them says.
- "Not only X, but also Y" construction.
- Emoji-as-decoration in technical writing.
- Ending with an invitation to continue the conversation ("Let me know if you'd like me to elaborate on any of these points!").
- Closing every section with a one-sentence tie-back to the section's thesis.
- Bolding the first few words of every bullet.

## Audience modes

The voice scales across three audiences. The core register stays the same; what changes is vocabulary and how much domain context is assumed.

**Technical peers.** Assume fluency. Use jargon where it's precise. Skip definitions of widely-known terms. This is the default mode for most of what gets written here.

**Civic / public-facing writing** (community-facing tools). Assume intelligence without fluency. Define domain terms the first time. Avoid jargon where plain words exist. Never condescend. The goal is accessibility, not simplification.

**Stakeholders** (PR reviewers, team leads, partners). Assume time pressure. Lead with the takeaway. Supporting detail follows, and readers can stop reading once they have what they need. This is the mode for PR descriptions, design doc summaries, and executive updates.

**Open source readers** (people who find the repo via GitHub, a blog post, or word of mouth). Assume they don't share your context — they don't work where you work, don't use your stack, don't know why specific choices were made. Name opinions as opinions. Explain *why* more thoroughly than for peers, because readers need enough to adapt, not just copy. Acknowledge limitations and the "this works for me, your mileage may vary" shape of personal config honestly — they're deciding whether to fork, and pretending a setup is universal wastes their time. This is the default mode for anything in a public repo that isn't scoped to a specific internal audience.

## Disagreement and pushback

When the writing needs to push back on a claim, plan, or design:

- Name what's right about the thing being pushed back on first.
- State the concern as specifically as possible — "this will fail when X" beats "I'm not sure about this."
- Propose an alternative or a next step. Pushback without a forward move is noise.
- Keep the register the same as the rest of the writing. Switching to a formal or apologetic register when disagreeing is a tell.

## Examples

### Canonical samples of the voice

Three examples of the author's own writing, for reference:

> Hey Claude—I just added the "web-artifacts-builder" skill. Can you make something useful with it? I am exploring ways to build tools for a civic project, which will help the community research and understand information about the complex, confusing, and often opaque process of city planning and zoning. I'd like to have an artifact I can share that will help answer questions in plain language while providing citations to verify the source material. Helpful, grounded answers are the intent.

> I have been working on another project, code-council, which allows providing a project requirements specification in a yaml file and then a 3 or more AI models draft implementation proposals tuned for handoff to Claude code for implementation. Then, each model votes on which it thinks is best (not knowing which model produced which proposal). The winning model gets to decide to kickoff a new round for a better proposal if it thinks that is likely to lead to a better outcome, ostensibly due to the review triggering belief an idea better than any proposed so far can be created.

> I want to write a skill that will allow Claude Code to record a demo of a terminal user interface, a TUI. I want Claude Code to be able to drive the TUI through a script that will validate that the TUI works and also be able to record a video of this happening so that I can share that with stakeholders and on the PR as evidence of the capability.

### Before and after

**Before** (marketing voice):

> Unlock the power of seamless construction management with our revolutionary AI-powered platform. Built from the ground up to empower teams to deliver best-in-class outcomes, our solution leverages cutting-edge technology to transform how you work.

**After** (this voice):

> A construction management tool for teams who'd rather spend their time building than wrestling with software. It uses AI where that actually saves time, and stays out of the way where it doesn't.

**Before** (AI tell — bulleted and padded):

> Here are the key benefits of using Rust for this project:
> - **Performance**: Rust provides exceptional runtime performance
> - **Safety**: Memory safety without garbage collection
> - **Concurrency**: Fearless concurrency is a core feature
> - **Ecosystem**: Growing crate ecosystem

**After**:

> Rust buys us memory safety without a garbage collector and concurrency guarantees strong enough that we can parallelize aggressively without fear. The ecosystem is young but growing, and the crates this project needs all exist.

**Before** (hedged and self-diminishing):

> I was just wondering if maybe it might be possible to perhaps consider using a different approach, though I'm definitely not sure if this is the right idea.

**After**:

> The current approach has a problem: it doesn't survive a crash mid-write. A maildir-style deliver-then-rename pattern would fix that. Worth trying?

## Using this guide

When writing under this repo's CLAUDE.md:

1. Read this guide before any prose-generation task longer than a paragraph.
2. If a task requires a register outside this guide (formal legal language, playful marketing copy, etc.), surface the mismatch to the author before proceeding.
3. When in doubt, prefer less over more. Pruning is easier for the reader than expanding.
