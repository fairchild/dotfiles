Goal:
Refactor {{target}} for clarity/maintainability with zero functional drift.

Context:
- Current pain points: {{pain_points}}
- Invariants to preserve: {{invariants}}
- Non-goals: {{non_goals}}

Pre-implementation (required):
1) Inspect relevant code and restate architecture assumptions.
2) Produce phased plan with acceptance criteria per phase.
3) Identify regression risks and mitigations.
4) Stop for approval before edits.

Constraints:
- Edit only: {{scope}}.
- No API, behavior, or dependency changes without approval.
- If a simplification requires behavior change, stop and ask.

Implementation protocol:
- One phase at a time.
- Report files changed + rationale after each phase.
- Keep changes reversible and localized.

Validation:
- Add/update tests only as needed to prove behavior unchanged.
- Run checks: {{checks}}.

Output format:
1) What changed
2) Why maintainability improved
3) Evidence behavior is unchanged
4) Files touched + purpose
5) Risks/limitations
6) Suggested commit message
7) Next 3 actions
