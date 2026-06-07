# Creating a Skill

Detailed guide for the 7-step skill creation process. See SKILL.md for the summary.

## Table of Contents

- [Step 1: Understanding with Concrete Examples](#step-1-understanding-the-skill-with-concrete-examples)
- [Step 2: Planning Reusable Contents](#step-2-planning-the-reusable-skill-contents)
- [Step 3: Initializing the Skill](#step-3-initializing-the-skill)
- [Step 4: Editing the Skill](#step-4-edit-the-skill)
- [Step 5: Validating](#step-5-validating)
- [Step 6: Packaging](#step-6-packaging-a-skill)
- [Step 7: Iterating](#step-7-iterate)

## Step 1: Understanding the Skill with Concrete Examples

Skip this step only when the skill's usage patterns are already clearly understood. It remains valuable even when working with an existing skill.

To create an effective skill, clearly understand concrete examples of how the skill will be used. This understanding can come from either direct user examples or generated examples that are validated with user feedback.

For example, when building an image-editor skill, relevant questions include:

- "What functionality should the image-editor skill support? Editing, rotating, anything else?"
- "Can you give some examples of how this skill would be used?"
- "I can imagine users asking for things like 'Remove the red-eye from this image' or 'Rotate this image'. Are there other ways you imagine this skill being used?"
- "What would a user say that should trigger this skill?"

To avoid overwhelming users, avoid asking too many questions in a single message. Start with the most important questions and follow up as needed for better effectiveness.

Conclude this step when there is a clear sense of the functionality the skill should support.

## Step 2: Planning the Reusable Skill Contents

To turn concrete examples into an effective skill, analyze each example by:

1. Considering how to execute on the example from scratch
2. Identifying what scripts, references, and assets would be helpful when executing these workflows repeatedly

Example: When building a `pdf-editor` skill to handle queries like "Help me rotate this PDF," the analysis shows:

1. Rotating a PDF requires re-writing the same code each time
2. A `scripts/rotate_pdf.py` script would be helpful to store in the skill

Example: When designing a `frontend-webapp-builder` skill for queries like "Build me a todo app" or "Build me a dashboard to track my steps," the analysis shows:

1. Writing a frontend webapp requires the same boilerplate HTML/React each time
2. An `assets/hello-world/` template containing the boilerplate HTML/React project files would be helpful to store in the skill

Example: When building a `big-query` skill to handle queries like "How many users have logged in today?" the analysis shows:

1. Querying BigQuery requires re-discovering the table schemas and relationships each time
2. A `references/schema.md` file documenting the table schemas would be helpful to store in the skill

To establish the skill's contents, analyze each concrete example to create a list of the reusable resources to include: scripts, references, and assets.

## Step 3: Initializing the Skill

Skip this step only if the skill being developed already exists and iteration or packaging is needed.

When creating a new skill from scratch, always run the `init_skill.py` script:

```bash
scripts/init_skill.py <skill-name> --path <output-directory>
```

The script:

- Creates the skill directory at the specified path
- Generates a SKILL.md template with proper frontmatter and TODO placeholders
- Creates example resource directories: `scripts/`, `references/`, and `assets/`
- Adds example files in each directory that can be customized or deleted

After initialization, customize or remove the generated SKILL.md and example files as needed.

## Step 4: Edit the Skill

When editing the (newly-generated or existing) skill, remember that the skill is being created for another instance of Claude to use. Include information that would be beneficial and non-obvious to Claude. Consider what procedural knowledge, domain-specific details, or reusable assets would help another Claude instance execute these tasks more effectively.

### Learn Proven Design Patterns

Consult these guides based on your skill's needs:

- **Multi-step processes**: See `references/workflows.md` for sequential workflows and conditional logic
- **Specific output formats**: See `references/output-patterns.md` for template and example patterns
- **Testing and resilience**: See `references/testing-methodology.md` for skill validation, defensive writing, and rationalization prevention

### Start with Reusable Skill Contents

To begin implementation, start with the reusable resources identified above: `scripts/`, `references/`, and `assets/` files. Note that this step may require user input. For example, when implementing a `brand-guidelines` skill, the user may need to provide brand assets or templates to store in `assets/`, or documentation to store in `references/`.

Added scripts must be tested by actually running them to ensure there are no bugs and that the output matches what is expected. If there are many similar scripts, only a representative sample needs to be tested.

Any example files and directories not needed for the skill should be deleted.

### Update SKILL.md

**Writing Guidelines:** Always use imperative/infinitive form.

#### Frontmatter

Write the YAML frontmatter with `name` and `description`:

- `name`: The skill name
- `description`: This is the primary triggering mechanism for your skill.
  - Include both what the Skill does and specific triggers/contexts for when to use it.
  - Include all "when to use" information here — not in the body. The body is only loaded after triggering, so "When to Use This Skill" sections in the body are not helpful.
  - Example description for a `docx` skill: "Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction. Use when Claude needs to work with professional documents (.docx files) for: (1) Creating new documents, (2) Modifying or editing content, (3) Working with tracked changes, (4) Adding comments, or any other document tasks"

Only `name` and `description` are required. Optional fields: `license`, `hooks`, `allowed-tools`, `metadata`. Do not add unrecognized fields.

#### Body

Write instructions for using the skill and its bundled resources.

**Writing for resilience**: Agents optimize for speed and rationalize shortcuts. Good skills anticipate this:

- Name each step explicitly — vague ordering is where steps get dropped
- Include verification after any step that produces output ("Run X and verify Y")
- Prefer real examples from actual usage over hypothetical scenarios
- For discipline-enforcing skills, add a rationalization table: common excuses agents produce and explicit counters (see `references/testing-methodology.md`)
- For skills with scripts, test them by running them — not by reading the code

### What Not to Include

Do NOT create auxiliary documentation files beyond README.md and CHANGELOG.md:

- INSTALLATION_GUIDE.md (fold into README)
- QUICK_REFERENCE.md (fold into SKILL.md or references/)
- etc.

The skill should only contain files that serve a clear purpose: SKILL.md for the agent, README.md for the human, scripts/ for deterministic execution, references/ for on-demand context, and assets/ for output resources.

### Progressive Disclosure Patterns

Keep SKILL.md body to the essentials and under 500 lines. Split content into separate files when approaching this limit. When splitting, reference the files from SKILL.md and describe clearly when to read them.

**Key principle:** When a skill supports multiple variations, frameworks, or options, keep only the core workflow and selection guidance in SKILL.md. Move variant-specific details into separate reference files.

**Pattern 1: Domain-specific organization**

For skills with multiple domains, organize content by domain:

```
bigquery-skill/
├── SKILL.md (overview and navigation)
└── reference/
    ├── finance.md (revenue, billing metrics)
    ├── sales.md (opportunities, pipeline)
    └── marketing.md (campaigns, attribution)
```

When a user asks about sales metrics, Claude only reads sales.md.

**Pattern 2: Conditional details**

Show basic content, link to advanced content:

```markdown
# DOCX Processing

## Creating documents
Use docx-js for new documents. See [DOCX-JS.md](DOCX-JS.md).

## Editing documents
For simple edits, modify the XML directly.
**For tracked changes**: See [REDLINING.md](REDLINING.md)
**For OOXML details**: See [OOXML.md](OOXML.md)
```

**Important guidelines:**

- **Avoid deeply nested references** — keep references one level deep from SKILL.md
- **Structure longer reference files** — for files longer than 100 lines, include a table of contents

## Step 5: Validating

Run the validator before packaging:

```bash
scripts/quick_validate.py <path/to/skill-folder>
```

Checks required frontmatter fields (`name`, `description`), naming conventions, description quality, and YAML structure. Fix any errors before proceeding.

## Step 6: Packaging a Skill

Once development is complete, package into a distributable .skill file:

```bash
scripts/package_skill.py <path/to/skill-folder>
```

Optional output directory:

```bash
scripts/package_skill.py <path/to/skill-folder> ./dist
```

The packaging script will:

1. **Validate** the skill automatically, checking:
   - YAML frontmatter format and required fields
   - Skill naming conventions and directory structure
   - Description completeness and quality
   - File organization and resource references

2. **Package** the skill if validation passes, creating a .skill file named after the skill (e.g., `my-skill.skill`). The .skill file is a zip with a .skill extension.

If validation fails, fix errors and run again.

## Step 7: Iterate

Skills improve through use, not through speculation. The best time to iterate is right after using a skill, while the gaps are fresh.

**Iteration workflow:**

1. Use the skill on a real task
2. Notice where the agent struggled, skipped steps, or produced weak output
3. Identify root cause: missing context? ambiguous instruction? wrong degree of freedom?
4. Apply the RED-GREEN-REFACTOR cycle (see `references/testing-methodology.md`): observe failure, write the minimal fix, verify improvement
5. When an agent rationalizes skipping a step, add that rationalization and its counter to the skill

**What to capture from real usage:**

- Scenarios where the skill failed — add as examples so the same class of failure is prevented
- Agent excuses for shortcuts — add to a rationalization table
- Steps that consistently get dropped — make ordering explicit or add verification
- Context the agent needed but didn't have — add to references/

Over time, a well-iterated skill accumulates examples from real sessions that serve as both documentation and immune system.
