# Analysis Modes

Templates for analyzing YouTube video transcripts.

## Wisdom {#wisdom}

Extract actionable insights and key learnings.

### Output Format

**Key Ideas** (3-5 bullets)
- Core concepts the speaker emphasizes

**Actionable Insights** (3-5 bullets)
- Specific actions the viewer can take

**Memorable Quotes** (2-3 quotes)
- Direct quotes from the transcript

**One-Sentence Summary**
- The essential message

---

## Summary {#summary}

Concise overview of video content.

### Output Format

**Overview** (2-3 sentences)
- What the video covers

**Main Points** (bulleted list)
- Key topics discussed

**Conclusion**
- Final takeaway or call to action

---

## Q&A {#qa}

Generate questions for discussion or follow-up.

### Output Format

**Clarifying Questions**
- What needs more explanation?

**Discussion Questions**
- For group conversation about the topic

**Follow-up Questions**
- What would you ask the speaker?

---

## Quotes {#quotes}

Extract notable statements from the transcript.

**Note**: Use `--with-segments` flag to include timestamps for quote attribution.

### Output Format

For each quote:
- **Quote**: Exact text
- **Context**: What topic it relates to
- **Timestamp**: Approximate time (from segment data)

---

## Custom Analysis

When the user requests something specific not covered above, apply their instructions directly to the transcript content. Common custom requests:

- Extract technical details or specifications
- List resources/tools mentioned
- Identify counterarguments or criticisms
- Compare to another source
- Find specific information (names, dates, statistics)
