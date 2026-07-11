#!/usr/bin/env python3
"""Validate skill SKILL.md frontmatter and structure"""
import sys
import json
import yaml
from pathlib import Path

REQUIRED_FIELDS = ["name", "description"]
FORBIDDEN_FILES = [
    "INSTALLATION.md",
    "QUICK_REFERENCE.md",
    "INSTALLATION_GUIDE.md"
]

def validate_skill(file_path: str) -> list[str]:
    """Returns list of validation errors"""
    errors = []
    path = Path(file_path)

    # Must be SKILL.md
    if path.name != "SKILL.md":
        return []  # Not a skill file, skip validation

    skill_dir = path.parent

    # Read and parse frontmatter
    try:
        content = path.read_text()
    except Exception as e:
        errors.append(f"Failed to read file: {e}")
        return errors

    if not content.startswith("---"):
        errors.append("Missing YAML frontmatter (must start with '---')")
        return errors

    try:
        parts = content.split("---", 2)
        if len(parts) < 3:
            errors.append("Invalid frontmatter structure (missing closing '---')")
            return errors

        frontmatter_raw = parts[1]
        frontmatter = yaml.safe_load(frontmatter_raw)

        if not isinstance(frontmatter, dict):
            errors.append("Frontmatter must be a YAML object/dictionary")
            return errors

    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML frontmatter: {e}")
        return errors
    except Exception as e:
        errors.append(f"Error parsing frontmatter: {e}")
        return errors

    # Check required fields
    for field in REQUIRED_FIELDS:
        if field not in frontmatter:
            errors.append(f"Missing required field: '{field}'")
        elif not frontmatter[field]:
            errors.append(f"Field '{field}' cannot be empty")

    # Validate description length and content
    if "description" in frontmatter:
        desc = frontmatter["description"]
        if len(desc) < 50:
            errors.append(
                f"Description too short ({len(desc)} chars) - should be comprehensive (50+ chars). "
                "Include what the skill does AND when to use it."
            )

    # Check for forbidden files in skill directory
    for forbidden in FORBIDDEN_FILES:
        if (skill_dir / forbidden).exists():
            errors.append(
                f"Forbidden file found: {forbidden} - "
                "Skills should only contain essential files (SKILL.md, scripts/, references/, assets/)"
            )

    return errors

if __name__ == "__main__":
    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
        file_path = hook_input["tool_input"]["file_path"]
    except Exception as e:
        print(json.dumps({
            "decision": "block",
            "reason": f"Validator error: Failed to parse hook input: {e}"
        }), file=sys.stderr)
        sys.exit(2)

    # Validate
    errors = validate_skill(file_path)

    if errors:
        # Blocking output - agent will see this and fix issues
        output = {
            "decision": "block",
            "reason": f"Skill validation failed for {Path(file_path).name}",
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"Fix these skill structure issues in {file_path}:\n\n" +
                                    "\n".join(f"  • {e}" for e in errors) +
                                    "\n\nSee skill-building guidelines for proper structure."
            }
        }
        print(json.dumps(output))
        sys.exit(2)
    else:
        # Success output
        output = {
            "continue": True,
            "systemMessage": f"✅ Skill validation passed: {Path(file_path).name}"
        }
        print(json.dumps(output))
        sys.exit(0)
