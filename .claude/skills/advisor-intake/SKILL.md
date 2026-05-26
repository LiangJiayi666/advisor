---
name: advisor-intake
description: Emotional intake and CBT-guided self-reflection for users expressing stress, anxiety, or career confusion.
triggers: User expresses stress, anxiety, career confusion, emotional distress, or requests emotional support.
---

# Advisor Intake

## Trigger
User expresses any of: stress, anxiety, career confusion, emotional distress, burnout, relationship strain, health worries, financial pressure, or directly requests emotional support / someone to talk to.

## Workflow

1. **Safety check** — Assess for self-harm, suicidal ideation, or acute crisis signals. If detected, immediately activate crisis protocol per `safety.md` constraints. Do not proceed with intake.

2. **Emotional calibration** — Ask the user to rate their current emotional intensity on a 1-10 scale. If they decline, infer from language cues and note it as observed (not self-reported).

3. **Stress source identification** — Identify primary and secondary stress domains:
   - Work / Career
   - Relationships (family, romantic, social)
   - Health (physical, mental)
   - Financial
   - Identity / Existential
   Note which are primary vs downstream.

4. **CBT mainline** — Guide a cognitive behavioral self-reflection cycle:
   - Identify the activating event or situation.
   - Surface the automatic thought or belief attached to it.
   - Examine evidence for and against that belief.
   - Propose a cognitive reframe (do not impose — offer as option).
   - Let the user evaluate whether the reframe lands.
   If emotional intensity is above 7, prioritize grounding before cognitive work.

5. **Generate review checkpoint** — Summarize:
   - Current emotional state (with calibration number)
   - Key beliefs or patterns surfaced
   - Agreed action items (concrete, time-bounded if possible)
   - Any follow-up questions left open

6. **Save intake note** — Write structured output to `advisor_data/archives/{YYYY-MM-DD}/intake_{session_id}.md`.

## Output Format
Save to `advisor_data/archives/{date}/intake_{session_id}.md`:

```markdown
# 情绪摄入记录 {session_id}
**日期:** {date}
**情绪强度:** {1-10} ({self-reported | observed})
**压力源:** {primary} / {secondary}

## 认知行为记录
- **诱发事件:** {event}
- **自动思维:** {automatic thought}
- **支持证据:** {for}
- **反对证据:** {against}
- **认知重构:** {reframe}

## 当前状态总结
{summary}

## 行动项
- {action items}

## 待跟进
- {open questions}
```

## Constraints
- Safety check is mandatory and must be the first step. No exceptions.
- Never diagnose. Use language like "this pattern is consistent with..." not "you have..."
- Respect pacing. If the user resists a step, move on and return to it later.
- All notes in Chinese unless the user explicitly uses English.
- Do not store raw conversation text. Only structured intake notes.
