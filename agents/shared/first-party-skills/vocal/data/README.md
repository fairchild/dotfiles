# Vocal Skill Local Data

This directory is for local, personal data created by the vocal skill.

The web console stores saved tuning defaults in `preferences.json` by default.
That file is gitignored because voice preferences can be personal and machine-specific.

Override the location with:

```bash
VOCAL_DATA_DIR=/path/to/private/vocal-data uv run --script ~/.claude/skills/vocal/scripts/web_console.py
```
