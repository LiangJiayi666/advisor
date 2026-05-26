# Memory Rules

## Memory Architecture

Two categories of memory data:

### Raw Memory (conversation content)
- The actual text of user messages, emotional tone, decisions discussed.
- **Never written to files directly.** Raw conversation stays in session context.
- Exception: user explicitly asks to record something ("记住这个").

### Derived Memory (processed insights)
- Extracted user profile facts (career stage, preferences, recurring themes).
- Session summaries with key decisions and emotional state.
- Research bookmarks and citation chains.
- **Written to `advisor_data/memories/memory.jsonl`** as JSONL entries.

### Business Object Data (structured external facts)
- Structured records about external objects, such as job postings, companies, source pages, and comparison artifacts.
- **Never store full business objects in `memory.jsonl`.** These are not derived user memories.
- Job postings belong in `advisor_data/jobs/`: `jobs.jsonl` for normalized job cards, `raw/` for original JD text, `evidence/` for field-level evidence, and `comparisons/` for comparison reports.
- Memory may contain only high-level user preferences or decisions derived from job work, for example: "用户当前优先考虑广州/深圳的 AI 产品经理岗位". Do not duplicate entire JD content in memory.

## Extraction Triggers

At the end of each substantive exchange, consider extracting:
- New factual information about the user (job change, life event, preference).
- Explicit decisions or commitments made by the user.
- Recurring emotional patterns or stress themes.

## Write Standards

Derived memory is stored as JSONL entries in `advisor_data/memories/memory.jsonl`. Each line is a JSON object with this schema:

```json
{"id": "mem_{timestamp}_{hash}", "kind": "fact|preference|trait|decision|pattern", "content": "...", "tags": [], "sensitivity": "raw_sensitive|derived|general", "confidence": 0.0-1.0, "verified": false, "superseded": false, "source_session_id": "...", "updated_at": "ISO8601"}
```

- `kind`: category of the memory entry (fact, preference, trait, decision, pattern).
- `sensitivity`: `raw_sensitive` for crisis/health data, `derived` for processed insights, `general` for non-sensitive facts.
- `confidence`: 0.0-1.0 numeric. Use low values (below 0.5) for inferred rather than explicitly stated information.
- `superseded`: set to `true` when a newer entry replaces this one.
- **No raw conversation text** — only synthesized insights in `content`.
- **No assumptions** — mark confidence below 0.5 if inferred rather than explicitly stated.

## Sensitive Data Classification

- **CRISIS_FLAG**: Only a boolean + date. No narrative. Stored as a JSONL entry with `sensitivity: raw_sensitive` and `kind: fact`.
- **Personal facts**: Career details, relationships, health disclosures — stored as JSONL entries with `kind: fact` or `kind: trait`, factual assertions only.
- **Never store**: passwords, account numbers, ID numbers, addresses, or any PII beyond what's needed for advisory context.

## Memory Loading

- `session_start` hook reads `advisor_data/memories/memory.jsonl`.
- Session archives in `advisor_data/archives/` are loaded on-demand when contextually relevant, not at session start.
- If memory.jsonl doesn't exist, first session creates it after sufficient interaction.

## Memory Hygiene

- Profile facts older than 6 months without reconfirmation should be flagged as "stale" (set `superseded: true` with a new entry noting the staleness).
- Session archives are append-only. Never edit past archives.
- Memory JSONL entries are append-only. To correct or update a fact, add a new entry and set `superseded: true` on the old one.
- If the user asks "你记得什么", provide a transparent summary of stored derived memory (non-superseded entries from memory.jsonl).
