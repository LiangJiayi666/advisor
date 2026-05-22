# /compare-jobs — Compare Stored Job Cards

Compare two or more stored job cards from `advisor_data/jobs/{owner}/jobs.jsonl`.

Owner defaults to "self" (the user). If comparing the partner's jobs, use `owner="partner"`.

Workflow:
1. Determine the owner from context (default "self"). Resolve job IDs from the user's message. If the user refers to jobs by company/title instead of ID, search the owner's `jobs.jsonl` and show the matched candidates.
2. Use `scripts.job_compare.compare_jobs` for deterministic scoring before writing any narrative recommendation.
3. Present the result with:
   - Rank
   - Job ID / title / company / city
   - Total score and dimension scores
   - Hard-constraint penalties
   - Uncertainties / missing evidence
   - A short recommendation in the user's decision language
4. If evidence is missing or stale, say so explicitly. Do not turn low-confidence fields into firm conclusions.

Do not compare by free-form memory only. Job postings are business-object data and must come from `advisor_data/jobs/{owner}/`.
