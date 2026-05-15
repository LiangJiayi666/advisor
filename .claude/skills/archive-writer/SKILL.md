     1|---
     2|name: archive-writer
     3|description: Summarize and archive substantive conversation sessions with structured metadata and state tracking.
     4|triggers: Session ending with substantive content (emotional intake, prism reading, job research, or multi-topic discussion).
     5|---
     6|
     7|# Archive Writer
     8|
     9|## Trigger
    10|A session ends with substantive content — emotional intake completed, prism reading delivered, job research finished, or a multi-topic conversation that produced insights, decisions, or action items.
    11|
    12|## Workflow
    13|
    14|1. **Summarize session in Chinese** — Produce a concise Chinese summary covering what was discussed, key insights, and outcomes. Omit pleasantries and procedural exchanges.
    15|
    16|2. **Extract action items** — List concrete next steps the user agreed to or that were identified. Mark each as agreed or suggested.
    17|
    18|3. **List follow-up questions** — Note any unresolved points, questions the user deferred, or topics that warrant revisiting.
    19|
    20|4. **Note prism chart version** — If a prism reading occurred, record:
    21|   - Chart version / generation timestamp
    22|   - Input source (user-provided solar date, estimated, etc.)
    23|   If no prism reading occurred, write "无".
    24|
    25|5. **Write archive file** — Save to `advisor_data/archives/{YYYY-MM-DD}/{session_id}.md`.
    26|
    27|6. **Set archive state flag** — Mark the session as archived to prevent duplicate archiving. This can be a simple metadata line in the archive file itself.
    28|
    29|## Output Format
    30|Save to `advisor_data/archives/{YYYY-MM-DD}/{session_id}.md`:
    31|
    32|```markdown
    33|# 会话归档 {session_id}
    34|**日期:** {date}
    35|**主题:** {main topics, comma-separated}
    36|**情绪状态:** {emotional calibration number if intake occurred, else "未评估"}
    37|
    38|## 摘要
    39|{Chinese summary, 3-8 sentences}
    40|
    41|## 行动项
    42|- [ ] {agreed action item}
    43|- [ ] {agreed action item}
    44|- {suggested action item} (建议)
    45|
    46|## 待追问
    47|- {follow-up question 1}
    48|- {follow-up question 2}
    49|
    50|## Prism 记录
    51|- 档案版本: {version or "无"}
    52|- 输入来源: {source or "无"}
    53|
    54|## 状态
    55|- [x] 已归档
    56|- [ ] 记忆已提炼
    57|- [ ] Prism 索引已更新
    58|```
    59|
    60|The status checkboxes are manual tracking. `已归档` is checked by this skill. `记忆已提炼` and `Prism 索引已更新` are checked when the memory-policy skill runs after archiving.
    61|
    62|## Constraints
    63|- Only archive sessions with substantive content. Brief Q&A or chitchat does not warrant archiving.
    64|- Summary must be in Chinese regardless of the session's language.
    65|- Never archive the same session twice. Check for existing archive before writing.
    66|- Action items must be concrete, not vague ("更新简历" not "改善求职状态").
    67|- If the session was primarily emotional support, handle with extra care in tone and framing of the summary.
    68|