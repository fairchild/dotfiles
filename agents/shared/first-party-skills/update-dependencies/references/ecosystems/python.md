# Python Ecosystem

Commands for Python dependency management with uv or poetry.

## Package Manager Detection

| Lockfile | Manager | Install | Run |
|----------|---------|---------|-----|
| `uv.lock` | uv | `uv sync` | `uv run` |
| `poetry.lock` | poetry | `poetry install` | `poetry run` |

## Security Audit

```bash
# Using pip-audit (install: uv pip install pip-audit)
pip-audit --format json

# Or with uv
uv run pip-audit --format json

# With poetry
poetry run pip-audit --format json
```

For vulnerabilities with fixes:
```bash
pip-audit --fix
```

## Outdated Analysis

```bash
# uv
uv pip list --outdated

# poetry
poetry show --outdated

# pip (general)
pip list --outdated --format json
```

## Update Commands

```bash
# uv - update specific package
uv add <package>@latest

# uv - update all
uv lock --upgrade

# poetry - update specific
poetry add <package>@latest

# poetry - update all within constraints
poetry update
```

## Test Commands

```bash
# Common patterns
uv run pytest
uv run mypy .
uv run ruff check .

# Or with poetry
poetry run pytest
poetry run mypy .
```

## Common Ecosystem Groups

### Web Frameworks
```
fastapi
starlette
uvicorn
```

### Data Science
```
numpy
pandas
scipy
matplotlib
```
Often have version interdependencies.

### Testing
```
pytest
pytest-cov
pytest-asyncio
```

### Type Checking
```
mypy
types-*
```
Update type stubs with their packages.

## Lockfile Handling

After updates:
```bash
# uv
git add pyproject.toml uv.lock

# poetry
git add pyproject.toml poetry.lock
```

## Version Constraints

Python packages often use flexible constraints:
- `>=1.0,<2.0` - Accept any 1.x
- `^1.0` (poetry) - Same as above
- `~=1.4` - Accept 1.4.x

When updating, check if constraints need widening for major versions.

## Virtual Environment

Both uv and poetry manage virtual environments automatically:
```bash
# uv creates .venv/
uv sync

# poetry creates in ~/.cache/pypoetry/virtualenvs/ by default
poetry install
```
