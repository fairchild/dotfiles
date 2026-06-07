---
name: firecrawl-research-papers
description: Find and synthesize research papers, whitepapers, PDFs, technical reports, and academic sources with Firecrawl. Use when the user wants a literature review, paper summary, research landscape, or sourced synthesis from PDFs and scholarly/industry publications.
license: ISC
metadata:
  author: firecrawl
  version: "0.1.0"
  homepage: https://www.firecrawl.dev
  source: https://github.com/firecrawl/firecrawl-workflows
inputs:
  - name: FIRECRAWL_API_KEY
    description: Firecrawl API key for hosted Firecrawl requests.
    required: true
disable-model-invocation: true
---

# Firecrawl Research Papers

Use this to create a sourced literature review.

## Onboarding Interview

Infer the topic, source constraints, target count, and output format from context. If the topic is clear, proceed immediately.

Ask at most 1-3 concise questions only if blocked, such as the topic, target paper count, or required venue/date/method constraints.

## Firecrawl Collection Plan

Search for papers, PDFs, whitepapers, technical reports, and research blogs. Scrape PDF URLs directly when available; Firecrawl can extract PDFs.

Target source types:

- academic papers from arXiv, university sites, ACM/IEEE pages where accessible
- industry reports and whitepapers
- company research blogs
- technical articles and conference summaries

## Parallel Work

If appropriate, use sub-agents or equivalent parallel task runners:

- Academic Papers researcher
- Industry Reports researcher
- Technical Articles researcher
- Synthesis and citation reviewer

## Final Deliverable

```markdown
# Literature Review: [Topic]

## Abstract
[2-3 paragraph summary]

## Key Papers
[Title, authors, source URL, key findings, methodology, relevance]

## Themes And Consensus
[What sources agree on]

## Open Questions And Debates
[Disagreements and unresolved questions]

## Emerging Trends
[Recent developments]

## Sources
[Organized by paper/report/article]

## Rerun Inputs
workflow: firecrawl-research-papers
topic: [topic]
target_count: [number]
output: [markdown/brief]
```

## Quality Bar

- Every major claim should trace to a source.
- Note inaccessible or failed PDFs.
- Distinguish peer-reviewed work from blogs and vendor reports.
