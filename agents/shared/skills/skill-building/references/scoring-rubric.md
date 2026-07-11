# Scoring Rubric

## Security Rating

| Rating | Criteria |
|--------|----------|
| **PASS** | No CRITICAL findings, 0-1 HIGH (with clear justification), no obfuscation |
| **WARN** | 1-3 HIGH findings that are contextually appropriate (e.g., subprocess in a build skill), or >5 MEDIUM findings |
| **FAIL** | Any CRITICAL finding without clear justification, >3 unjustified HIGH findings, any obfuscation |

**Context matters**: A `subprocess.run` in a test-runner skill is expected. The same pattern in a "SwiftUI best practices" reference skill is suspicious.

## Quality Rating

| Rating | Criteria |
|--------|----------|
| **A (Exemplary)** | Clear frontmatter with specific triggers, well-organized SKILL.md under 500 lines, progressive disclosure via references, concrete examples, follows all spec conventions |
| **B (Good)** | Valid frontmatter, reasonable organization, minor issues (slightly long, vague triggers), mostly follows conventions |
| **C (Functional)** | Works but has notable issues: missing trigger conditions, over-long SKILL.md, weak examples, some convention violations |
| **D (Poor)** | Significant problems: invalid frontmatter, no clear organization, missing key content, many convention violations |

**Key quality signals**:
- Description includes specific trigger phrases (not just what it does)
- Body uses imperative form and concrete examples
- References are loaded on-demand (not inlined in SKILL.md)
- No forbidden files (README.md at skill root, CHANGELOG.md, etc.)

## Context Budget Rating

| Rating | Triggered Tokens | Guidance |
|--------|-----------------|----------|
| **Light** | <2,000 | Minimal context cost. Adopt freely. |
| **Moderate** | 2,000-10,000 | Reasonable for feature-rich skills. Evaluate value-per-token. |
| **Heavy** | >10,000 | Significant context cost. Must provide proportional value. Consider if references could be trimmed. |

**Metadata budget**: ~100 words is ideal. Always loaded for every skill.
**Body budget**: ~500 words is the guideline. Loaded when triggered.

## Compatibility Rating

| Rating | Criteria |
|--------|----------|
| **Compatible** | Works with current agent setup, no conflicting dependencies, standard conventions |
| **Partial** | Works but needs minor adjustments (e.g., different package manager, missing optional dependency) |
| **Incompatible** | Requires unsupported runtime, conflicts with existing skills, wrong platform |

## Value Rating

| Rating | Criteria |
|--------|----------|
| **High** | Provides specialized knowledge Claude lacks, unique workflow automation, significant time savings, well-maintained |
| **Medium** | Useful but partially overlaps with built-in knowledge or existing skills. Adds some unique value. |
| **Low** | Mostly duplicates what Claude already knows or other installed skills provide. Minor incremental value. |
| **Redundant** | Entirely covered by Claude's training or existing skills. No reason to adopt. |

**Value-per-token heuristic**: `value_rating / triggered_tokens`. A High-value, Light-budget skill is ideal. A Low-value, Heavy-budget skill should be skipped.

## Recommendation Decision Matrix

| Security | Quality | Value | Budget | Recommendation |
|----------|---------|-------|--------|----------------|
| PASS | A-B | High | Any | **ADOPT** |
| PASS | A-B | Medium | Light-Moderate | **ADOPT** |
| PASS | C | High | Light-Moderate | **ADOPT WITH MODIFICATIONS** |
| WARN | A-B | High | Any | **ADOPT WITH MODIFICATIONS** |
| PASS | Any | Low | Heavy | **SKIP** |
| FAIL | Any | Any | Any | **SKIP** |
| Any | D | Any | Any | **SKIP** |
| Any | Any | Redundant | Any | **SKIP** |

When between ratings, lean toward the more cautious recommendation.
