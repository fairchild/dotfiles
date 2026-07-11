---
name: skill-building
description: Guide for creating, editing, and evaluating skills. Use when creating a new skill, updating an existing skill, or verifying skills work before deployment. Also use when reviewing a third-party skill from skills.sh or GitHub, when asking "should I install this skill", "is this skill safe", "review this skill", "evaluate skill quality", or when comparing competing skills.
license: Apache-2.0
disable-model-invocation: true
metadata:
  author: Michael Fairchild
  version: "3.0"
---

# Skill Building

Create, edit, and evaluate skills that extend Claude's capabilities.

**Self-description**: When a user asks what this skill does, read `README.md`.

## About Skills

Skills are modular, self-contained packages that extend Claude's capabilities with specialized knowledge, workflows, and tools. They provide:

1. **Specialized workflows** — multi-step procedures for specific domains
2. **Tool integrations** — instructions for working with specific file formats or APIs
3. **Domain expertise** — company-specific knowledge, schemas, business logic
4. **Bundled resources** — scripts, references, and assets for complex tasks

## Core Principles

**Concise is key.** The context window is a public good. Only add context Claude doesn't already have. Challenge each piece: "Does this justify its token cost?"

**Set appropriate degrees of freedom.** Match specificity to fragility:
- **High freedom** (text instructions): multiple valid approaches, context-dependent
- **Medium freedom** (pseudocode/parameterized scripts): preferred pattern with variation
- **Low freedom** (specific scripts): fragile operations, consistency critical

## Anatomy of a Skill

```
skill-name/
├── SKILL.md              (required: frontmatter + instructions)
├── README.md             (optional: human-facing documentation)
├── scripts/              (optional: deterministic, token-efficient)
├── references/           (optional: on-demand context for Claude)
└── assets/               (optional: files used in output)
```

**SKILL.md** has two parts:
- **Frontmatter** (YAML): `name` and `description` (required) — determines when the skill triggers. Optional fields: `license`, `hooks`, `allowed-tools`, `metadata`.
- **Body** (Markdown): instructions loaded only after triggering

**Progressive disclosure** manages context efficiently:
1. **Metadata** (name + description) — always in context (~100 words)
2. **SKILL.md body** — when skill triggers (<500 lines)
3. **Bundled resources** — as needed (unlimited; scripts execute without loading)

Keep SKILL.md body under 500 lines. When splitting content, reference files from SKILL.md with clear "when to read" guidance. Keep references one level deep.

## Creating a Skill

| Step | Action | Details |
|------|--------|---------|
| 1 | Understand with examples | Gather concrete usage examples from the user |
| 2 | Plan reusable contents | Identify scripts, references, and assets needed |
| 3 | Initialize | `scripts/init_skill.py <name> --path <dir>` |
| 4 | Edit | Implement resources, write SKILL.md |
| 5 | Validate | `scripts/quick_validate.py <path>` |
| 6 | Package | `scripts/package_skill.py <path>` |
| 7 | Iterate | Improve from real usage |

For detailed guidance on each step, read `references/creating.md`.

## Evaluating a Skill

| Step | Action | Tool |
|------|--------|------|
| 1 | Resolve source | `scripts/fetch_skill.py --source <url> --skill <name>` |
| 2 | Structural check | `skills-manager validate` or manual check |
| 3 | Security audit | `scripts/security_scan.py --path <dir>` |
| 4 | Quality assessment | Manual review against rubric |
| 5 | Context budget | `scripts/context_budget.py --path <dir>` |
| 6 | Value assessment | Overlap and unique contribution analysis |
| 7 | Generate report | Save to `reports/<name>-<YYYY-MM-DD>.md` |

**Quick decision matrix:**

| Security | Quality | Value | Recommendation |
|----------|---------|-------|----------------|
| PASS | A-B | High-Medium | **ADOPT** |
| WARN | A-B | High | **ADOPT WITH MODIFICATIONS** |
| FAIL | Any | Any | **SKIP** |
| Any | D | Any | **SKIP** |

For the full 7-step workflow, read `references/evaluating.md`.

## Live Development

Skills must be "live" at the target path to test (`~/.claude/skills/` for global, `.claude/skills/` for project-local). Use **symlinks** to bridge development and runtime without copying files.

For the symlink workflow and key rules, see `references/live-development.md`.

## Shared Tools

These scripts serve both creation and evaluation workflows:

- **`scripts/context_budget.py`** — token cost estimation for any skill
  ```bash
  uv run scripts/context_budget.py --path <skill-dir> --format json
  ```
- **`scripts/quick_validate.py`** — fast structural validation
  ```bash
  uv run scripts/quick_validate.py <skill-dir>
  ```
- **`scripts/security_scan.py`** — static security pattern analysis
  ```bash
  uv run scripts/security_scan.py --path <skill-dir> --format json
  ```

## Reference Index

| File | When to read |
|------|-------------|
| `references/creating.md` | Creating or editing a skill (6-step detailed guide) |
| `references/evaluating.md` | Evaluating a third-party skill (7-step workflow) |
| `references/live-development.md` | Symlink workflow for testing skills during development |
| `references/testing-methodology.md` | Testing patterns, defensive writing, rationalization prevention |
| `references/workflows.md` | Sequential workflow and conditional logic patterns |
| `references/output-patterns.md` | Template and example output patterns |
| `references/report-template.md` | Evaluation report template |
| `references/scoring-rubric.md` | Security, quality, value rating criteria |
| `references/security-patterns.md` | Expected vs suspicious security patterns |
| `references/refining-skill-descriptions.md` | Tightening the `description` field for invocation matching |
