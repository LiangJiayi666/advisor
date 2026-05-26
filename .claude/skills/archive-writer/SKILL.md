---
name: archive-writer
description: Summarize and archive substantive advisor sessions into structured archive files.
triggers: Session ending after substantive advisory, research, or intake work.
---

# Archive Writer

## Role

This skill defines the archive method and required output structure for substantive sessions. It does not own session-close orchestration; that belongs to the session-close entry point.

## When to Use

Use this skill when a session has produced meaningful content such as:
- emotional intake or support
- job research or comparison
- major decision discussion
- multi-topic advisory progress worth preserving

Do not use it for trivial chitchat or ultra-short exchanges.

## Method

### 1. Summarize the session in Chinese

The archive should capture:
- what the session was mainly about
- what changed in the user's understanding, decision, or emotional state
- what concrete outcomes or next steps emerged

Omit pleasantries and purely procedural back-and-forth.

### 2. Extract action items

Separate:
- agreed actions
- suggested actions

Action items should be concrete enough that a later session can revisit them.

### 3. Record unresolved points

List follow-up questions, uncertainties, or postponed decisions.

### 4. Write in the canonical archive format

Save archives under:
- `advisor_data/archives/{YYYY-MM-DD}/{session_id}.md`

## Canonical output skeleton

```markdown
# 会话归档 {session_id}
**日期:** {date}
**主题:** {topics}
**情绪状态:** {calibration or 未评估}

## 摘要
{summary}

## 行动项
- [ ] {agreed item}
- {suggested item} (建议)

## 待追问
- {follow-up}

## 状态
- [x] 已归档
- [ ] 记忆已提炼
```

## Hard constraints

- Archive only substantive sessions.
- Summary must be Chinese.
- Do not duplicate the same archive if it already exists.
- Keep the archive structured; do not dump raw transcript text.
- If the session is emotionally sensitive, summarize with care and compression rather than replaying vulnerable wording.

## References

- Session-close orchestration: `/close-session`
- Memory extraction policy: `memory-policy`
- Global project rules: `CLAUDE.md`
