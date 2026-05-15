     1|# /recall-memory — Recall Long-Term Memory
     2|
     3|Activate the `memory-policy` skill in recall mode.
     4|
     5|Read `advisor_data/memories/memory.jsonl` (JSONL format, one JSON object per line) and locate memories relevant to the current conversation context. Summarize and present the key points to the user — past concerns, decisions, recurring themes, or anything that connects to what they're discussing now.
     6|
     7|When summarizing, group results by `kind` (fact, preference, trait, decision, pattern) and `tags` categories to give a structured overview. If profile-related memories are found (tagged `profile_related`), also check for the corresponding profile data in `advisor_data/profiles/prism/` and include relevant chart context.
     8|
     9|If no memory file exists yet, let the user know this is a fresh start and memories will accumulate over sessions.