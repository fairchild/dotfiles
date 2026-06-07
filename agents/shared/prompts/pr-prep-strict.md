Goal:
Produce a reviewer-ready PR package for the current branch.

Pre-check:
1) Inspect branch diff and summarize intent.
2) Identify risky areas (security, migrations, API, data changes).
3) Note any missing tests/docs.

Output format (strict):
1) PR title (conventional commit style)
2) PR description:
   - Context/problem
   - What changed
   - Why this approach
   - Alternatives considered (brief)
3) Files changed grouped by concern
4) Testing performed + exact commands
5) Rollout/ops notes (if any)
6) Risks and mitigations
7) Reviewer checklist
8) Follow-up tasks (non-blocking)

Style constraints:
- Keep concise and factual.
- Flag uncertainty explicitly.
- Do not claim tests ran unless verified.
