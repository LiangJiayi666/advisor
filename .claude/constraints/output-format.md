# Output Format Rules

## Standard Advisory Output

Output must separate:

```
### 模式分析 / Pattern Perspective
[Interpretive framework: behavioral patterns, recurring themes, and situational dynamics.
 Clearly marked as analysis, not prediction.]

---

### 现实建议 / Practical Advice
[Evidence-based recommendations: market data, career frameworks, actionable steps.
 Grounded in real-world information and user's actual situation.]
```

## Session Archive Format

Each session archive (`advisor_data/archives/YYYY-MM-DD/{session_id}.md`):
```markdown
# Session: [topic]

Date: YYYY-MM-DD
Tags: [career, stress, research, ...]
Risk Level: GREEN | YELLOW | RED

## Key Points
- [bullet summaries of main discussion points]

## Decisions
- [any commitments or decisions user made]

## Follow-up
- [unresolved items to track]

## Memory Updates
- [list of profile updates made this session]
```

## Research Citation Format

When web research is used, cite sources inline:
```
根据 [来源名称](URL) 的数据，...
```

End of research-heavy responses must include a sources section:
```
---
Sources:
- [Title](URL)
- [Title](URL)
```

## General Formatting

- User-facing output in Chinese, unless user switches to English.
- Avoid jargon without explanation. If technical terms are needed, provide one-line clarification.
- Keep responses structured but conversational. Not academic, not chatty.
- When giving advice, lead with the actionable item, then explain reasoning.
