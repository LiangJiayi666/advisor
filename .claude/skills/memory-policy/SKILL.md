---
name: memory-policy
description: Extract, classify, and persist stable facts from conversations into structured long-term memory.
triggers: End of substantive session, or user asks to recall, update, or review memories.
---

# Memory Policy

## Trigger
End of a substantive conversation session, or user explicitly asks to recall, update, review, or correct stored memories.

## Workflow

1. **Extract stable facts** — From the current conversation, identify:
   - Factual assertions about the user (birth date, location, job title, education)
   - Stated preferences (communication style, topic interests, advice format)
   - Observed personality traits or behavioral patterns
   - Explicit decisions or commitments made
   Do not extract transient emotional states or situational complaints as permanent memories.

2. **Classify sensitivity** — Tag each memory as:
   - `raw_sensitive`: birth datetime, birth location, government ID, financial specifics
   - `derived`: personality traits, preferences, behavioral patterns, prism-derived insights
   - `general`: job field, interests, communication preferences
   Raw sensitive data requires higher confidence and explicit user verification before marking `verified: true`.

3. **Check for conflicts** — Compare against existing entries in `advisor_data/memories/memory.jsonl`:
   - If a new fact contradicts an existing `verified: true` entry, flag for user resolution. Do not auto-overwrite.
   - If a new fact duplicates an existing entry with identical content, skip.
   - If a new fact updates an existing entry (same topic, newer data), create a new entry and mark the old one `superseded: true`.

4. **Write new entries** — Append to `advisor_data/memories/memory.jsonl`, one JSON object per line.

5. **Tag prism-related memories** — If any memory relates to prism profile data (birth info, chart corrections), add `prism_related` to the memory entry's `tags` field.

## Memory Schema
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

- `id`: `mem_{UnixTimestamp}_{first8charsOfSHA256(content)}`
- `confidence`: 0.0-1.0, based on how directly the user stated this vs inferred
- `verified`: `true` only after explicit user confirmation

## Constraints
- Never overwrite `verified: true` entries without user confirmation.
- Always classify sensitivity level. Raw sensitive data gets extra protection.
- Do not store verbatim conversation text. Only structured, generalized facts.
- Inferred traits must have `confidence < 0.8` and `verified: false` until confirmed.
- Memory file is append-only. Corrections are new entries with `superseded: true` on the old one.
