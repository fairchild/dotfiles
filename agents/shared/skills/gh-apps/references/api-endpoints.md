# GitHub Apps REST API Endpoints

## Authentication Types

| Type | How to get | Header |
|------|-----------|--------|
| JWT | `_generate_jwt(app_id, key_path)` | `Authorization: Bearer <JWT>` |
| Installation token | `POST /app/installations/{id}/access_tokens` | `Authorization: Bearer <token>` |
| Personal (gh CLI) | `gh auth login` | Handled by `gh api` |

## App Endpoints (JWT auth)

### GET /app
Get the authenticated app's info.
```bash
gh api /app -H "Authorization: Bearer $(gh-apps.py jwt)"
```

### GET /app/installations
List all installations of the app.
```bash
gh-apps.py installations
```
Response: array of installation objects with `id`, `account.login`, `target_type`, `permissions`.

### GET /app/hook/config
Get webhook configuration.

### PATCH /app/hook/config
Update webhook URL, secret, or content type.
```json
{"url": "https://new.example.com/hook", "content_type": "json"}
```

### GET /app/hook/deliveries
List webhook deliveries. Supports `?per_page=N`.

### POST /app/hook/deliveries/{delivery_id}/attempts
Redeliver a webhook event.

## Installation Endpoints (JWT auth)

### POST /app/installations/{installation_id}/access_tokens
Create an installation access token.
```bash
gh-apps.py token --installation 12345
```
Response: `{"token": "ghs_...", "expires_at": "...", "permissions": {...}}`

## Installation-Scoped Endpoints (installation token auth)

### GET /installation/repositories
List repositories accessible to the installation.

### GET /repos/{owner}/{repo}
Get a specific repository.

## Manifest Flow (no auth)

### POST /app-manifests/{code}/conversions
Exchange temporary code for app credentials.
Returns: `id`, `pem`, `webhook_secret`, `client_id`, `client_secret`, `name`, `owner`, `slug`.

## Rate Limits

| Auth type | Limit |
|-----------|-------|
| JWT | 5,000/hour (shared across all installations) |
| Installation token | 5,000/hour per installation |
| User token | 5,000/hour per user |

## Common `gh api` Examples

```bash
# Get app info (needs JWT — use urllib, not gh api)
gh-apps.py info

# List installations
gh-apps.py installations

# Get installation token
gh-apps.py token

# Check webhook config
gh-apps.py webhook-config

# List recent deliveries
gh-apps.py deliveries --limit 20

# Redeliver failed webhook
gh-apps.py redeliver 12345678
```
