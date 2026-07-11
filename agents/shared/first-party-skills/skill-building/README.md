# Skill Building

Guide for creating and evaluating skills that extend Claude's capabilities with specialized knowledge, workflows, and tool integrations.

Covers the full lifecycle: understanding use cases, planning resources, initializing structure, writing SKILL.md, packaging for distribution, iterating from real usage, and evaluating third-party skills for security, quality, and value.

## Key Concepts

- **Progressive disclosure**: Metadata always loaded (~100 words), SKILL.md body on trigger (<500 lines), references on demand
- **Description as trigger**: The `description` field determines when the skill activates — write triggering conditions, not workflow summaries
- **Defensive writing**: Agents optimize for speed and rationalize shortcuts. Good skills anticipate this with explicit steps, verification, and rationalization counters

## Validation

Run `scripts/quick_validate.py <skill-dir>` after writing or editing a SKILL.md. Checks required frontmatter fields, description length, YAML structure, and file organization.

## References

- `references/testing-methodology.md` — Testing patterns, defensive writing, rationalization prevention
- `references/workflows.md` — Sequential workflow and conditional logic patterns
- `references/output-patterns.md` — Template and example output patterns
- `scripts/init_skill.py` — Scaffold a new skill directory
- `scripts/package_skill.py` — Validate and package for distribution

## Credits

Built on work from:

- **[anthropic-agent-skills](https://github.com/anthropics/anthropic-agent-skills)** (Anthropic, Apache-2.0) — Original skill-creator framework, anatomy, progressive disclosure patterns, init/package scripts
- **[superpowers](https://github.com/obra/superpowers)** (Jesse Vincent, MIT) — Defensive writing patterns, rationalization tables, evidence-before-claims, red-green-refactor for skills, testing methodology
