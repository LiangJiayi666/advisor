import json
from pathlib import Path

from scripts.job_store import JobStore
from scripts.job_compare import compare_jobs


def test_job_research_skill_documents_business_object_storage():
    text = Path(".claude/skills/job-research/SKILL.md").read_text(encoding="utf-8")

    assert "advisor_data/jobs/{owner}/jobs.jsonl" in text
    assert "scripts.job_store.JobStore" in text
    assert "do not save full JD content" in text.lower() or "不要" in text


def test_compare_jobs_command_uses_deterministic_compare_module():
    text = Path(".claude/commands/compare-jobs.md").read_text(encoding="utf-8")

    assert "scripts.job_compare.compare_jobs" in text
    assert "Do not compare by free-form memory only" in text
