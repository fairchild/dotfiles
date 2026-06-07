Goal:
Implement feature {{feature}} with explicit acceptance criteria and safe rollout.

Context:
- User outcome: {{user_outcome}}
- Acceptance criteria: {{acceptance_criteria}}
- Domain constraints: {{domain_rules}}
- Non-goals: {{non_goals}}

Pre-implementation (required):
1) Inspect relevant code and restate assumptions.
2) Produce phased implementation plan with acceptance criteria per phase.
3) Identify top risks + mitigations.
4) Stop for approval before edits.

Constraints:
- Edit only: {{scope}}.
- No API-breaking changes unless approved.
- No new dependencies unless approved.

Implementation protocol:
- Deliver one phase at a time.
- Report files changed + rationale per phase.
- If scope expansion is needed, stop and ask.

Validation:
- Add/update tests for feature behavior and edge cases.
- Run checks: {{checks}}.

Output format:
1) What was implemented
2) How acceptance criteria were met
3) Files touched + purpose
4) Test/verification results
5) Remaining risks/debt
6) Suggested commit message
7) Next 3 actions
