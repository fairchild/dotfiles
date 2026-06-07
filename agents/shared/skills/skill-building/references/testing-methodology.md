# Skill Testing Methodology

Inspired by [obra/superpowers](https://github.com/obra/superpowers) (MIT, Jesse Vincent 2025).

## Core Principle

Writing skills is test-driven development applied to process documentation. Observe agents fail before documenting solutions. Every line in a skill should exist because you watched an agent struggle without it.

## Red-Green-Refactor for Skills

**RED**: Run pressure scenarios without the skill. Document exact agent behavior — where it goes wrong, what it rationalizes, what it skips.

**GREEN**: Write the minimal skill addressing only those specific failures. No speculative content.

**REFACTOR**: Test again. Identify new rationalizations the agent produces. Add explicit counters. Repeat until the skill is bulletproof.

This cycle applies to new skills and to skill revisions. When a skill isn't working well, go back to RED — observe the failure before fixing it.

## Description as Trigger

The description field is a search index, not a summary. Agents read descriptions to decide whether to load the skill body.

Descriptions must state *triggering conditions*, not workflow summaries.

**Why this matters**: If the description summarizes the workflow ("dispatches subagent per task with code review between tasks"), agents follow the summary verbatim instead of reading the full skill body. This causes them to miss steps, simplify multi-step processes, and skip nuance documented in the body.

**Good**: "Use when creating new skills, editing existing skills, or verifying skills work before deployment"

**Bad**: "Guide that walks through 6-step skill creation process with init, edit, validate, package, and iterate phases"

## Testing Scripts

Skills with scripts/ must test them before shipping. Run each script, verify the output matches expectations. For large collections of similar scripts, test a representative sample.

This sounds obvious. It gets skipped anyway — often rationalized as "the logic is straightforward" or "I'll test it when the user runs it." Those are the scripts that break.

## Testing by Skill Type

**Discipline-enforcing skills** (TDD, verification-before-completion):
- Test with pressure scenarios — time constraints, sunk cost, near-completion exhaustion
- The agent will rationalize. Document every excuse, then add explicit counters.

**Technique skills** (how-to guides):
- Test application to scenarios the skill doesn't explicitly cover
- Test edge cases and missing instructions
- Verify the agent can follow the steps without prior knowledge

**Process skills** (multi-step workflows):
- Test that agents complete ALL steps, not just the first few
- Test interruption recovery — can the agent resume mid-process?
- Verify ordering constraints are respected

## Defensive Writing

Agents skip steps. Not maliciously — they optimize for speed and produce reasonable-sounding justifications for shortcuts. Good skills anticipate this.

### Rationalization table

Build one from testing. Every excuse you observe becomes an explicit counter in the skill.

| Rationalization | Counter |
|----------------|---------|
| "This is simple enough to skip" | Name the step explicitly; no exceptions for simple cases |
| "I already did the equivalent" | Require specific evidence or output, not claims |
| "The user didn't ask for this" | State when the skill is mandatory vs optional |
| "I'll do it at the end" | Require the step before proceeding to the next |
| "I verified it mentally" | Require running the command and showing output |

### Red flags

When writing a skill, watch for these patterns that indicate it won't hold up:

- **Relies on the agent "knowing" something** — If the skill assumes the agent will remember a constraint, make it explicit. Context gets long. Details get lost.
- **No concrete examples** — Abstract instructions invite creative interpretation. Show input/output pairs for anything that matters.
- **Vague ordering** — "Then do X" is weaker than "Do X before proceeding to Y." Ambiguity in sequencing is where steps get dropped.
- **No verification step** — If the skill produces output, include how to check it. "Run X and verify Y" is stronger than "Run X."

### Evidence before claims

When a skill includes verification steps, require the agent to run the verification and show the output *before* claiming success. This is the single most effective pattern for preventing false completion claims.

Not because agents lie — because they optimize. "Tests pass" is shorter than running the tests. The skill should make running-then-showing the path of least resistance.

### Ground in real examples

Prefer examples drawn from actual sessions over hypothetical scenarios. Real examples carry specificity that hypotheticals lack — they include the edge cases and context that actually matter.

When iterating on a skill, capture the scenario that exposed a gap and add it as an example. Over time, the examples section becomes the skill's immune system.

## Token Budget Guidelines

| Skill type | Target |
|-----------|--------|
| Getting-started / bootstrapping | < 150 words |
| Frequently-loaded (every session) | < 200 words body |
| On-demand skills | < 500 words body |
| With references | SKILL.md < 500 lines, split to references/ |

These are guidelines, not hard limits. A 210-word frequently-loaded skill that's well-written is better than a 190-word one with essential context removed. The point is awareness — every word in a skill costs context window for every session it loads.
