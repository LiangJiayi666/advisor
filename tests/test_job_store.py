import json
from pathlib import Path

from scripts.job_store import JobStore


def test_upsert_creates_job_card_raw_and_evidence_files(tmp_path):
    store = JobStore(tmp_path)

    job = store.upsert_from_extraction(
        raw_text="某银行金融科技产品经理，地点广州，要求 Python 和 AI 产品经验。",
        source_url="https://example.com/job/1",
        source_type="web",
        extraction={
            "title": "金融科技产品经理",
            "company": "某银行",
            "city": "广州",
            "job_family": "AI产品经理",
            "requirements": ["Python", "AI 产品经验"],
            "evidence": {
                "city": {"quote": "地点广州", "source_url": "https://example.com/job/1"}
            },
        },
    )

    assert job["job_id"].startswith("job_")
    assert job["title"] == "金融科技产品经理"
    assert job["company"] == "某银行"
    assert job["city"] == "广州"
    assert job["source_url"] == "https://example.com/job/1"
    assert job["requirements"] == ["Python", "AI 产品经验"]

    jobs_path = tmp_path / "jobs" / "jobs.jsonl"
    raw_path = tmp_path / "jobs" / "raw" / f"{job['job_id']}.md"
    evidence_path = tmp_path / "jobs" / "evidence" / f"{job['job_id']}.json"

    assert jobs_path.exists()
    assert raw_path.read_text(encoding="utf-8") == "某银行金融科技产品经理，地点广州，要求 Python 和 AI 产品经验。"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["city"]["quote"] == "地点广州"


def test_upsert_by_source_url_updates_existing_job_instead_of_duplicating(tmp_path):
    store = JobStore(tmp_path)
    first = store.upsert_from_extraction(
        raw_text="旧 JD",
        source_url="https://example.com/job/1",
        source_type="web",
        extraction={"title": "产品经理", "company": "A公司", "city": "深圳"},
    )
    second = store.upsert_from_extraction(
        raw_text="新 JD",
        source_url="https://example.com/job/1",
        source_type="web",
        extraction={"title": "高级产品经理", "company": "A公司", "city": "广州"},
    )

    assert second["job_id"] == first["job_id"]
    assert second["title"] == "高级产品经理"
    assert second["city"] == "广州"
    jobs = list(store.list_jobs())
    assert len(jobs) == 1
