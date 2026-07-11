---
name: excalidraw-diagrams
description: Create diagrams and visual artifacts using Excalidraw with real-time canvas preview. Use when the user asks to create, draw, or visualize diagrams, flowcharts, architecture diagrams, system designs, or any visual representation. Supports creating elements programmatically, Mermaid diagram conversion, and visual verification via screenshots.
license: Apache-2.0
disable-model-invocation: true
---

# Excalidraw Diagrams

Create diagrams using the Excalidraw canvas server and verify output with screenshots.

## Prerequisites

1. **Canvas server running** at http://localhost:3000
   ```bash
   cd ${MCP_EXCALIDRAW_PATH:-~/code/mcp_excalidraw} && npm run canvas
   ```
   
   Set `MCP_EXCALIDRAW_PATH` in your global mise config (`~/.config/mise/config.toml`) if the path differs.

2. **MCP server configured** in project `.mcp.json` (for MCP tool access)

## Creating Diagrams

### Via HTTP API (Recommended)

Create elements directly via the canvas server API:

```bash
curl -X POST http://localhost:3000/api/elements/batch \
  -H "Content-Type: application/json" \
  -d @/tmp/elements.json
```

Element JSON structure:
```json
{
  "elements": [
    {"type": "rectangle", "x": 100, "y": 100, "width": 150, "height": 80, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2"},
    {"type": "text", "x": 120, "y": 130, "text": "Label", "fontSize": 20}
  ]
}
```

### Element Types

| Type | Required Props | Optional Props |
|------|---------------|----------------|
| `rectangle` | x, y, width, height | backgroundColor, strokeColor, strokeWidth |
| `ellipse` | x, y, width, height | backgroundColor, strokeColor |
| `diamond` | x, y, width, height | backgroundColor, strokeColor |
| `text` | x, y, text | fontSize, fontFamily |
| `arrow` | x, y, width, height | strokeColor, strokeWidth |
| `line` | x, y, width, height | strokeColor, strokeWidth |

### Color Palette

- Blue: `#a5d8ff` (bg), `#1971c2` (stroke)
- Green: `#b2f2bb` (bg), `#2f9e44` (stroke)
- Red: `#ffc9c9` (bg), `#e03131` (stroke)
- Yellow: `#ffec99` (bg), `#f08c00` (stroke)
- Purple: `#d0bfff` (bg), `#7950f2` (stroke)
- Gray: `#dee2e6` (bg), `#495057` (stroke)

## Verifying Output

Take a screenshot to verify the diagram rendered correctly:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('http://localhost:3000')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(2000)
    page.screenshot(path='/tmp/diagram.png', full_page=True)
    browser.close()
```

Run with: `uv run python /tmp/screenshot_script.py`

Then read the screenshot to verify: `Read /tmp/diagram.png`

## Common Patterns

### Flowchart (Vertical)

```json
{
  "elements": [
    {"type": "rectangle", "x": 100, "y": 50, "width": 120, "height": 60, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2"},
    {"type": "text", "x": 130, "y": 70, "text": "Start", "fontSize": 16},
    {"type": "arrow", "x": 160, "y": 110, "width": 0, "height": 40, "strokeColor": "#495057"},
    {"type": "rectangle", "x": 100, "y": 150, "width": 120, "height": 60, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44"},
    {"type": "text", "x": 120, "y": 170, "text": "Process", "fontSize": 16},
    {"type": "arrow", "x": 160, "y": 210, "width": 0, "height": 40, "strokeColor": "#495057"},
    {"type": "rectangle", "x": 100, "y": 250, "width": 120, "height": 60, "backgroundColor": "#ffc9c9", "strokeColor": "#e03131"},
    {"type": "text", "x": 135, "y": 270, "text": "End", "fontSize": 16}
  ]
}
```

### Architecture Boxes (Horizontal)

```json
{
  "elements": [
    {"type": "rectangle", "x": 50, "y": 100, "width": 100, "height": 80, "backgroundColor": "#a5d8ff", "strokeColor": "#1971c2"},
    {"type": "text", "x": 70, "y": 130, "text": "Client", "fontSize": 14},
    {"type": "arrow", "x": 150, "y": 140, "width": 50, "height": 0, "strokeColor": "#495057"},
    {"type": "rectangle", "x": 200, "y": 100, "width": 100, "height": 80, "backgroundColor": "#b2f2bb", "strokeColor": "#2f9e44"},
    {"type": "text", "x": 225, "y": 130, "text": "API", "fontSize": 14},
    {"type": "arrow", "x": 300, "y": 140, "width": 50, "height": 0, "strokeColor": "#495057"},
    {"type": "rectangle", "x": 350, "y": 100, "width": 100, "height": 80, "backgroundColor": "#d0bfff", "strokeColor": "#7950f2"},
    {"type": "text", "x": 385, "y": 130, "text": "DB", "fontSize": 14}
  ]
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/elements` | GET | List all elements |
| `/api/elements` | POST | Create single element |
| `/api/elements/batch` | POST | Create multiple elements |
| `/api/elements/:id` | PUT | Update element |
| `/api/elements/:id` | DELETE | Delete element |
| `/api/elements/from-mermaid` | POST | Convert Mermaid to elements |
| `/health` | GET | Server health check |

## Workflow

1. Check canvas server is running: `curl http://localhost:3000/health`
2. Clear canvas if needed: Click "Clear Canvas" in browser or restart server
3. Create elements via API batch endpoint
4. Take screenshot to verify
5. Show screenshot to user for confirmation
6. Iterate if needed

## Mermaid Conversion

Convert Mermaid diagrams to Excalidraw:

```bash
curl -X POST http://localhost:3000/api/elements/from-mermaid \
  -H "Content-Type: application/json" \
  -d '{"mermaidDiagram": "graph TD; A-->B; B-->C;"}'
```

Note: Mermaid conversion requires the browser canvas to be open for rendering.
