Goal:
Fix {{issue}} with minimal risk and no regressions outside stated scope.

Context:
- Domain rules: {{domain_rules}}
- Invariants that must hold: {{invariants}}
- Non-goals: {{non_goals}}

Pre-implementation (required):
1) Inspect relevant code and restate problem + assumptions.
2) Produce a phased plan with acceptance criteria per phase.
3) Identify top risks and mitigations.
4) Stop for approval before making edits.

Constraints:
- Edit only: {{scope}}.
- Do not change public APIs unless approved.
- Do not add dependencies.
- Preserve existing behavior except: {{intended_change}}.
- If scope expansion is needed, stop and ask.

Implementation protocol:
- Execute one phase at a time.
- After each phase: report files changed, rationale, and diff-level summary.
- If uncertain, choose the safer reversible option and flag tradeoffs.

Validation:
- Add/update tests for changed behavior and edge cases.
- Run relevant checks: {{checks}}.
- Report failures with likely causes before broad fixes.

Output format:
1) What changed
2) Why it changed
3) Files touched + purpose
4) Test/verification results
5) Remaining risks
6) Suggested commit message (conventional commit style)
7) Next 3 follow-up actions
