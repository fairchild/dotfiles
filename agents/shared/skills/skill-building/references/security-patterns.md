# Security Patterns Catalog

## 1. File System (HIGH)

Patterns that modify, delete, or traverse the filesystem.

| Pattern | Severity | Expected When | Suspicious When |
|---------|----------|---------------|-----------------|
| `rm -rf` | HIGH | Build cleanup scripts | Targets user dirs, `~/`, `/` |
| `shutil.rmtree` | HIGH | Temp dir cleanup | Targets non-temp paths |
| `../` (path traversal) | MEDIUM | Relative imports | In user-provided input paths |
| `chmod` | MEDIUM | Making scripts executable | Changing system files |
| `os.remove` | MEDIUM | Cleanup operations | Deleting config/credentials |

**Expected in skills**: Scripts that scaffold files may use `open(path, 'w')`. Build scripts may clean temp dirs.

## 2. Network / Exfiltration (CRITICAL)

Patterns that send data to external services.

| Pattern | Severity | Expected When | Suspicious When |
|---------|----------|---------------|-----------------|
| `requests.post` | CRITICAL | API integration skills | No clear API purpose |
| `requests.get` | MEDIUM | Fetching docs/data | Sending query params with local data |
| `urllib.request` | HIGH | Downloading resources | Uploading/POSTing data |
| `curl` / `wget` | MEDIUM | Documented in SKILL.md | Hidden in scripts |
| Hardcoded URLs | LOW | API endpoints, docs | Unknown domains |
| `fetch(` | MEDIUM | Web API skills | POST with local data |

**Red flag**: Any outbound request that includes local file content, env vars, or skill context.

## 3. Credentials (HIGH)

Patterns that access secrets, tokens, or sensitive configuration.

| Pattern | Severity | Expected When | Suspicious When |
|---------|----------|---------------|-----------------|
| `os.environ` | HIGH | API key for skill's service | Reading unrelated keys |
| `process.env` | HIGH | Same as above (Node) | Same as above |
| `~/.ssh` | CRITICAL | Git/SSH skills | Any other skill |
| `.env` | HIGH | Documented config loading | Undocumented access |
| `keychain`/`token`/`secret` | MEDIUM | Auth-related skills | Generic utility skills |

**Expected in skills**: API-calling skills (image-gen, AI) need env vars for their specific service.

## 4. Code Execution (CRITICAL)

Patterns that execute dynamic or user-provided code.

| Pattern | Severity | Expected When | Suspicious When |
|---------|----------|---------------|-----------------|
| `eval(` | CRITICAL | Never expected in skills | Always suspicious |
| `exec(` | CRITICAL | Code generation skills (rare) | Generic utility skills |
| `subprocess.run` | HIGH | Build/test/CLI wrapper skills | Running user-controlled strings |
| `os.system` | CRITICAL | Legacy code | Always prefer subprocess |
| `__import__()` | HIGH | Plugin systems | Simple utility skills |
| `child_process` | HIGH | Node CLI wrappers | With interpolated strings |

**Expected in skills**: Build/test runners legitimately use subprocess. The key question: are arguments hardcoded or user-controlled?

## 5. Persistence / Hooks (MEDIUM)

Patterns that install auto-running code or modify system startup.

| Pattern | Severity | Expected When | Suspicious When |
|---------|----------|---------------|-----------------|
| `hooks:` frontmatter | MEDIUM | Validation hooks (PostToolUse) | PreToolUse with network calls |
| `crontab` | HIGH | Scheduling skills | Hidden in utility skills |
| `launchctl` | HIGH | macOS service skills | Unrelated to skill purpose |
| `LaunchAgents` | HIGH | Same as above | Same as above |
| `systemctl` | HIGH | Server deployment skills | Desktop utility skills |

**Key question for hooks**: Does the hook validate (acceptable) or execute arbitrary code (dangerous)?

## 6. Obfuscation (CRITICAL)

Patterns that hide intent through encoding or assembly.

| Pattern | Severity | Expected When | Suspicious When |
|---------|----------|---------------|-----------------|
| Long base64 strings (100+ chars) | CRITICAL | Embedded binary assets | In scripts |
| Hex-encoded sequences | CRITICAL | Binary protocol skills | General utility skills |
| String concatenation chains | HIGH | Never really expected | Always suspicious |
| `atob()`/`base64.b64decode` | HIGH | Handling encoded API responses | Decoding embedded payloads |

**Rule**: Legitimate skills have no reason to obfuscate. Any obfuscation pattern is a red flag.

## Regex Patterns (for security_scan.py)

```python
# These are the compiled patterns used by the scanner.
# See security_scan.py PATTERNS dict for the authoritative list.
# This reference provides context for interpreting findings.
```
