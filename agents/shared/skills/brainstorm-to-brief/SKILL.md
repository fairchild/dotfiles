---
name: brainstorm-to-brief
license: Apache-2.0
description: Wide→Narrow design workflow taking UI/UX concepts from exploration to polished design brief. Four phases - Context, Explore, Iterate, Refine. Use for visual design exploration, user story mockups, and creating shareable design briefs.
disable-model-invocation: true
---

# Brainstorm to Brief

Go wide, then narrow. Explore many options freely, then converge to one polished design brief.

```
WIDE                                    NARROW
┌──────────────────────────────────────────────┐
│  Context   Explore     Iterate      Refine   │
│    ↓         ↓↓↓         ↓↓          ↓       │
│  [doc]    [many]      [fewer]      [one]     │
│           options     options      brief     │
└──────────────────────────────────────────────┘
```

## Phase Overview

| Phase | Purpose | Output |
|-------|---------|--------|
| **1. Context** | Define what we're building | `docs/product_overview.md` |
| **2. Explore** | Generate many options | `user-stories.md` + `brainstorm/*.png` |
| **3. Iterate** | Pick winners, develop consistency | `stories/*.png` + `wireflows/*.jpg` |
| **4. Refine** | Polish into cohesive brief | `design-brief.html` + `brief/` assets |

---

## Phase 1: Context

Create `docs/product_overview.md` — the canonical product definition.

**Contents:**
- Problem statement (what pain exists)
- Solution summary (how the product solves it)
- Core capabilities (bulleted feature list)
- Target users (who benefits)
- Design principles (guiding constraints)

**Key rule:** No implementation details. Focus on *what* and *why*, not *how*.

---

## Phase 2: Explore (Wide)

Generate many options. Don't worry about consistency yet.

### User Stories (`docs/user-stories.md`)

```markdown
# [Product] User Stories

## Product Context
[2-3 sentences - enough to understand stories without reading full docs]

---

## Story 1: [Title]

**As a** [user type]
**I want to** [action]
**So that** [benefit]

### Flow Diagram

\`\`\`mermaid
sequenceDiagram
    actor User
    participant App
    User->>App: Opens app
    App-->>User: Shows home
    User->>App: Takes action
\`\`\`

### ASCII Wireframe

\`\`\`
┌─────────────────────────┐
│  App Name          [+]  │
├─────────────────────────┤
│                         │
│    Content area         │
│                         │
├─────────────────────────┤
│  [Tab1] [Tab2] [Tab3]   │
└─────────────────────────┘
\`\`\`

### Steps

1. **[Step name]** — [What happens]
2. **[Step name]** — [What happens]
```

### Screen Exploration (`docs/design/brainstorm/`)

Generate many mockup variations. Use `assets/index.html` for gallery view.

```bash
mkdir -p docs/design/brainstorm
cp ~/.claude/skills/brainstorm-to-brief/assets/index.html docs/design/brainstorm/
# Generate images with image-gen skill, add to gallery
```

**Tips for exploration:**
- Try different layouts for the same screen
- Vary color schemes, typography
- Generate 3-5 options per key screen
- Rate and annotate favorites

---

## Phase 3: Iterate (Narrowing)

Pick promising directions. Develop consistency across screens.

### Story Flows (`docs/design/stories/`)

Sequential mockups showing complete user journeys. Use `assets/stories.html`.

```bash
mkdir -p docs/design/stories/s1
cp ~/.claude/skills/brainstorm-to-brief/assets/stories.html docs/design/stories/index.html
# Generate sequential images with continuity (see Image Generation below)
```

### Wireflows (`docs/design/wireflows/`)

Composite images showing screen + interaction flow. Generated with image-gen skill.

**Wireflow prompt pattern:**
```
Create a wireflow showing [user journey]. Layout: 3 phone screens
connected by arrows. Screen 1: [state]. Arrow: "[action]".
Screen 2: [state]. Arrow: "[action]". Screen 3: [state].
Clean diagram style, subtle shadows, white background.
```

---

## Phase 4: Refine (Narrow)

Polish into one cohesive design brief.

### Design Brief (`docs/design/design-brief.html`)

The final output — a shareable HTML page that ties everything together.

```bash
cp ~/.claude/skills/brainstorm-to-brief/assets/design-brief.html docs/design/
mkdir -p docs/design/brief
# Generate hero image, app icon, persona images
# Customize HTML with project details
```

### Brief Assets (`docs/design/brief/`)

- `hero.jpg` — Hero banner image
- `app-icon.jpg` — App icon
- `persona-*.jpg` — User persona images

---

## Directory Structure

```
docs/
├── product_overview.md       # Phase 1: Context
├── user-stories.md           # Phase 2: Explore (text)
└── design/
    ├── brainstorm/           # Phase 2: Explore (images)
    │   ├── index.html        # Gallery viewer
    │   └── *.png
    ├── stories/              # Phase 3: Iterate (flows)
    │   ├── index.html        # Story flow viewer
    │   └── s*-*.png
    ├── wireflows/            # Phase 3: Iterate (wireflows)
    │   └── *.jpg
    ├── brief/                # Phase 4: Refine (assets)
    │   ├── hero.jpg
    │   ├── app-icon.jpg
    │   └── persona-*.jpg
    └── design-brief.html     # Phase 4: Refine (output)
```

---

## Image Generation

### Provider Options

| Provider | Model | Best For |
|----------|-------|----------|
| Google Imagen 4 | imagen-4.0-generate-001 | Independent screens |
| OpenAI | gpt-image-1.5 | Sequential flows (continuity) |
| fal.ai Flux | flux-pro | Fast iteration |

### OpenAI Continuity for Story Flows

For consistent screens across a user story:

**Step 1 (establish style):**
```python
from openai import OpenAI
client = OpenAI()

response = client.images.generate(
    model="gpt-image-1.5",
    prompt="Mobile app UI mockup: [description]. Clean iOS style, blue accent, white background.",
    size="1024x1536"
)
# Save as stories/s1-01.png
```

**Step 2+ (reference previous):**
```python
import base64

with open("stories/s1-01.png", "rb") as f:
    prev_image = base64.standard_b64encode(f.read()).decode("utf-8")

response = client.images.edit(
    model="gpt-image-1.5",
    image=[{"type": "base64", "media_type": "image/png", "data": prev_image}],
    prompt="Same app, same visual style. Now showing: [describe changes]. Keep header, colors identical.",
)
# Save as stories/s1-02.png
```

**Prompt tips:**
- Reference specific elements: "same blue header", "same card style"
- Describe only what changed: "bottom sheet now open"
- Include style anchors: "iOS 17 style", "material design 3"

---

## Feedback Workflow

### During Explore
1. Generate multiple options
2. Rate and annotate in gallery
3. Identify promising directions

### During Iterate
1. **CLARIFY** — Ask about unclear feedback
2. **CONFIRM** — Summarize understanding
3. **ITERATE** — Refine selected directions

### During Refine
1. Review brief with stakeholders
2. Update sections based on feedback
3. Polish visuals and copy

---

## Templates

| Template | Purpose | Location |
|----------|---------|----------|
| `index.html` | Screen exploration gallery | `assets/index.html` |
| `stories.html` | Story flow viewer | `assets/stories.html` |
| `design-brief.html` | Final design brief | `assets/design-brief.html` |

All templates support dark mode, responsive layout, and navigation between views.
