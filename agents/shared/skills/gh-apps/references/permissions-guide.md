# GitHub App Permissions Guide

## Permission Levels

- `read` — Read-only access
- `write` — Read and write access
- `admin` — Full administrative access (rare, use sparingly)

## Common Permission Sets

### Issue Bot
```
issues:write, metadata:read
```
Events: `issues`, `issue_comment`

### CI / Checks App
```
checks:write, statuses:write, contents:read, metadata:read
```
Events: `check_suite`, `check_run`, `push`

### Discussion Coordinator
```
discussions:write, metadata:read
```
Events: `discussion`, `discussion_comment`

### Pull Request Automation
```
pull_requests:write, contents:read, metadata:read
```
Events: `pull_request`, `pull_request_review`

### Repository Automation
```
contents:write, pull_requests:write, issues:write, metadata:read
```
Events: `push`, `pull_request`, `issues`

### Security Scanner
```
security_events:write, contents:read, metadata:read
```
Events: `code_scanning_alert`, `secret_scanning_alert`

### Release Manager
```
contents:write, metadata:read
```
Events: `release`, `push`

### Webhook-Only (no API permissions)
```
metadata:read
```
Events: (whatever you need to observe)

## Repository Permissions

| Permission | Read | Write | Description |
|-----------|------|-------|-------------|
| `actions` | View workflow runs | Manage workflows | GitHub Actions |
| `checks` | View check results | Create/update checks | CI status checks |
| `contents` | Clone, list files | Push, create branches | Repository content |
| `deployments` | View deployments | Create deployments | Deployment status |
| `environments` | View environments | Manage environments | Deployment environments |
| `issues` | View issues | Create/edit issues | Issue tracker |
| `metadata` | Basic repo info | — | Always included (read) |
| `packages` | View packages | Publish packages | GitHub Packages |
| `pages` | View Pages config | Manage Pages | GitHub Pages |
| `pull_requests` | View PRs | Create/edit PRs | Pull requests |
| `security_events` | View alerts | Dismiss alerts | Code/secret scanning |
| `statuses` | View commit status | Create statuses | Commit statuses |
| `workflows` | — | Manage workflow files | `.github/workflows/` |

## Organization Permissions

| Permission | Description |
|-----------|-------------|
| `members` | View/manage org members |
| `administration` | Manage org settings |
| `plan` | View org plan |

## Account Permissions

| Permission | Description |
|-----------|-------------|
| `email_addresses` | View user emails |
| `followers` | Manage follows |
| `gpg_keys` | Manage GPG keys |

## Webhook Events Reference

### Repository Events
`push`, `create`, `delete`, `fork`, `release`, `star`, `watch`

### Issue Events
`issues`, `issue_comment`, `label`, `milestone`

### Pull Request Events
`pull_request`, `pull_request_review`, `pull_request_review_comment`, `pull_request_review_thread`

### CI/CD Events
`check_suite`, `check_run`, `status`, `deployment`, `deployment_status`, `workflow_run`, `workflow_job`

### Discussion Events
`discussion`, `discussion_comment`

### Security Events
`code_scanning_alert`, `secret_scanning_alert`, `dependabot_alert`

### App Events
`installation`, `installation_repositories`, `installation_target`

## Selecting Permissions via CLI

```bash
# Issue bot
gh-apps.py create my-bot --permissions issues:write,metadata:read --events issues,issue_comment

# CI app
gh-apps.py create my-ci --permissions checks:write,statuses:write,contents:read --events check_suite,push

# Discussion coordinator
gh-apps.py create coordinator --permissions discussions:write --events discussion,discussion_comment
```
