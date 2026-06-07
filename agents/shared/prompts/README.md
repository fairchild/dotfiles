# Prompt Template Cheat Sheet

Use these suffixes by intent:

- `-quick`: Fast, minimal guardrails. Best for low-risk/simple tasks.
- `-guided`: Default mode. Adds plan + constraints + verification.
- `-strict`: High-stakes mode. Phase gates, explicit risks, approval stops.

## Recommended defaults

- Bug fixes: `/bugfix-guided`
- Refactors: `/refactor-guided`
- Features: `/feature-guided`
- PR prep: `/pr-prep-guided`
- Coaching: `/coach-guided`

## Escalate when needed

Move from `guided` to `strict` when:
- scope is cross-cutting,
- regressions would be costly,
- auth/billing/data flows are involved,
- output format must be exact.

Drop to `quick` when:
- task is tiny and isolated,
- code risk is low,
- you want speed over ceremony.

## Current templates

- `/bugfix-quick`, `/bugfix-guided`, `/bugfix-strict`
- `/refactor-quick`, `/refactor-guided`, `/refactor-strict`
- `/feature-quick`, `/feature-guided`, `/feature-strict`
- `/pr-prep-quick`, `/pr-prep-guided`, `/pr-prep-strict`
- `/coach-guided`, `/coach-strict`
