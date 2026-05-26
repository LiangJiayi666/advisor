---
name: memory-policy
description: Extract, classify, and persist stable long-term memory from substantive sessions.
triggers: End of substantive session, or user asks to recall, update, review, or correct stored memories.
---

# Memory Policy

## Role

This skill defines what counts as durable memory, how it should be classified, and how it should be written. It does not own full session-close orchestration.

## What qualifies as memory

Eligible long-term memory includes:
- stable facts about the user
- communication preferences
- recurring traits or patterns
- explicit decisions or commitments likely to matter later

Not eligible:
- raw conversation text
- transient frustrations or passing mood states
- ordinary procedural back-and-forth
- job posting content that belongs in the job store

## Method

### 1. Extract only durable information

From the session, identify information that is likely to remain useful across later conversations.

### 2. Classify sensitivity

Use these levels:
- `raw_sensitive`
- `derived`
- `general`

Raw sensitive items need the highest caution and should not be casually merged into broad summaries.

### 3. Check for duplication or conflict

Before writing:
- skip exact duplicates
- if new info updates an old memory, create a new entry and mark the old one superseded
- do not silently overwrite verified truths when there is a conflict

### 4. Write structured JSONL entries

Canonical storage:
- `advisor_data/memories/memory.jsonl`

Canonical schema:

```json
{
  "id": "mem_{timestamp}_{hash}",
  "kind": "fact|preference|trait|decision|pattern",
  "content": "...",
  "tags": [],
  "sensitivity": "raw_sensitive|derived|general",
  "confidence": 0.0,
  "verified": false,
  "superseded": false,
  "source_session_id": "...",
  "updated_at": "ISO8601"
}
```

## Recall mode guidance

When the task is recall rather than writing:
- read relevant memories
- group them by kind / theme
- summarize them for current context
- do not inflate uncertain memory into hard fact

## Hard constraints

- Never store raw transcript text as durable memory.
- Never treat job object data as memory when it belongs under `advisor_data/jobs/`.
- Never auto-overwrite a verified memory without explicit resolution.
- Inferred traits should remain lower-confidence until confirmed.

## References

- Session-close orchestration: `/close-session`
- Archive structure: `archive-writer`
- Global rules: `CLAUDE.md`
