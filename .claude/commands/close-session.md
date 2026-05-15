     1|# /close-session — Archive & Close
     2|
     3|Activate the `archive-writer` skill to run the full session closing workflow:
     4|
     5|1. **Check state flag** — if session is already archived (flag in `advisor_data/state/state.json`), skip to prevent duplicate archiving.
     6|2. **Archive session** — write the session transcript summary to `advisor_data/archives/`.
     7|3. **Extract memories** — identify key facts, decisions, and emotional notes from this session. Append to `advisor_data/memories/memory.jsonl`.
     8|4. **Update session state** — After archive and memory extraction succeed, update `advisor_data/state/state.json`:
     9|   - Set `archive_state` to `"archived"`
    10|   - Set `last_session_id` and `last_session_date` to the current session's values
    11|   - Increment `session_count` by 1
    12|   - Update `recent_topics` with this session's key topics
    13|   - Set `current_session_id` to `null`
    14|   This state update is the final step. Do not execute it if archive or memory extraction failed.
    15|
    16|5. **SessionEnd duties** — Since Claude Code has no dedicated SessionEnd event, perform these closing actions here:
    17|   - Update `recent_topics` in `advisor_data/state/state.json` with this session's key topics.
    18|   - If a profile snapshot was generated this session, update `prism_profile_version` with the generation timestamp.
    19|   - Lightweight log: append one line to `advisor_data/state/session_log.jsonl` with `{date, session_id, topics, risk_level}`.
    20|
    21|Report a brief summary of what was archived and any notable extractions.