---
name: job-research
description: Parse and research jobs, persist structured job cards, and support evidence-based fit analysis.
triggers: User pastes a JD, sends a job link, mentions job hunting, or asks about a company/position fit.
---

# Job Research

## Role

This skill defines the reusable method and constraints for job research tasks. It is not the source of truth for business storage or the place to redefine the whole application workflow.

Use this skill when the task involves any of the following:
- parse a JD into structured fields
- persist a job card into the job store
- do company / role / industry research
- assess fit against the user's profile
- compare jobs using deterministic evidence-aware logic

## Method

### 1. Normalize the input

Convert the user's input into a structured job target if possible:
- title
- company
- city / location
- source / source_url
- responsibilities
- requirements
- keywords

If the input is incomplete, ask targeted clarification questions rather than a generic request for more detail.

### 2. Use structured job storage, not free-form memory

Job postings are business objects, not long-term conversational memory.

Persist them under `advisor_data/jobs/{owner}/` using the job store convention:
- `jobs.jsonl` for normalized job cards
- `raw/` for original source material
- `evidence/` for field-level evidence
- `comparisons/` for reports

Owner rule:
- default `owner = "self"`
- use `owner = "partner"` only when the task is explicitly for the partner

### 3. Prefer deterministic job objects before narrative analysis

Before writing any fit judgment, make sure there is a structured job card. Narrative analysis should sit on top of persisted job facts, not replace them.

### 4. Separate three evidence levels in output

Every serious job research answer should distinguish:
- verified facts
- social / public sentiment findings
- model inferences

Do not blur these levels.

### 5. Use deterministic comparison when ranking jobs

When the task is comparison or prioritization, prefer deterministic scoring logic first and let the model explain the score second.

Relevant Python layer sources of truth include:
- `scripts.job_store.JobStore`
- `scripts.job_compare.compare_jobs`
- `scripts.job_batch_rank`

## Batch screening guidance

When many jobs are involved, apply a staged funnel before deep reading every item:

1. category exclusion
2. city deduplication
3. competency / qualification exclusion
4. structured storage or shortlist generation
5. only then deep fit analysis

The exact scoring or filtering implementation belongs in Python scripts where possible; the skill's role is to preserve the method and constraints.

## Media / public sentiment guidance

Public sentiment crawling is optional and opt-in.

Only do it after explicit user consent. If used, report:
- platforms used
- approximate sample size
- positive signals
- negative signals
- mixed / uncertain signals

If a platform fails, log the limitation and continue; do not turn retry loops into the main task.

## Output shape

A good job research result usually contains:
- a compact job card
- a research summary
- a fit judgment
- explicit uncertainty notes
- source links when factual claims are made

## Hard constraints

- Do not store full JD content in long-term memory files.
- Do not present inference as verified fact.
- Do not compare jobs from vague recollection alone when structured job objects should exist.
- Do not make social sentiment crawling the default path.
- Do not redefine business storage rules in prompt text when Python/storage conventions already exist.

## References

- Global project rules: `CLAUDE.md`
- Architecture boundary note: `AdvisorPrivate_ArchitectureRefactor_20260526.md`
- Business logic: `scripts/` and `advisor_data/jobs/`
