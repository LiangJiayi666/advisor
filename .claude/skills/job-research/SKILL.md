---
name: job-research
description: Parse and persist job postings into structured job cards. Scoring and ranking are handled by /compare-jobs.
triggers: User pastes a JD, sends a job link, mentions job hunting, or asks about a company/position.
---

# Job Research

## Role

This skill defines the reusable method for **collecting and persisting** job postings into the structured job store. It does not handle scoring or ranking — that belongs to `/compare-jobs`.

Use this skill when the task involves any of the following:
- parse a JD into structured fields
- persist a job card into the job store
- do company / role / industry background research
- extract and normalize job metadata (title, company, city, requirements, etc.)

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

Owner rule:
- default `owner = "self"`
- use `owner = "partner"` only when the task is explicitly for the partner

### 3. Persist first, analyze later

Every job input should result in a persisted job card. If the user asks "is this a fit?", persist the card first, then direct them to `/compare-jobs` for scoring.

### 4. Separate three evidence levels in output

When presenting background research on a company or role, distinguish:
- verified facts
- social / public sentiment findings
- model inferences

Do not blur these levels.

### 5. Scoring and ranking are not part of this skill

When the user asks for ranking, comparison, or "which one should I pick", direct them to `/compare-jobs`.

The scoring pipeline lives in `scripts/job_batch_rank.py` and is accessed through `scripts.job_compare.compare_jobs()`. This skill does not call those functions.

## Output shape

A good job research result contains:
- a compact job card (title / company / city / key requirements)
- whether it was newly saved or already existed
- any missing fields that couldn't be extracted
- if the user asked for background: a research summary with source links

## Hard constraints

- Do not store full JD content in long-term memory files.
- Do not call `_score_job`, `normalize_jobs`, or any ranking function.
- Do not present inference as verified fact.
- Do not compare jobs from vague recollection alone when structured job objects should exist.
- Do not make social sentiment crawling the default path.
- Do not redefine business storage rules in prompt text when Python/storage conventions already exist.

## References

- Global project rules: `CLAUDE.md`
- Architecture boundary note: `AdvisorPrivate_ArchitectureRefactor_20260526.md`
- Business logic: `scripts/` and `advisor_data/jobs/`
- Scoring and ranking: `/compare-jobs` command and `scripts.job_compare`
