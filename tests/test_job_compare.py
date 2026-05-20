import json
from pathlib import Path

from scripts.job_store import JobStore
from scripts.job_compare import compare_jobs


def test_compare_jobs_applies_hard_city_penalty_and_reports_uncertainty(tmp_path):
    store = JobStore(tmp_path)
    good = store.upsert_from_extraction(
        raw_text="广州 AI 产品经理，金融科技方向，要求 Python。",
        source_url="https://example.com/good",
        source_type="web",
        extraction={
            "title": "AI 产品经理",
            "company": "A公司",
            "city": "广州",
            "job_family": "AI产品经理",
            "keywords": ["AI", "金融科技", "Python"],
            "requirements": ["Python"],
            "evidence": {"city": {"quote": "广州 AI 产品经理"}},
        },
    )
    bad_city = store.upsert_from_extraction(
        raw_text="北京 内容运营岗位。",
        source_url="https://example.com/bad",
        source_type="web",
        extraction={
            "title": "内容运营",
            "company": "B公司",
            "city": "北京",
            "job_family": "运营",
            "keywords": ["内容运营"],
        },
    )

    result = compare_jobs(
        list(store.list_jobs()),
        [good["job_id"], bad_city["job_id"]],
        user_preferences={
            "preferred_cities": ["广州", "深圳"],
            "target_keywords": ["AI", "金融科技", "Python"],
            "target_job_families": ["AI产品经理", "产品经理"],
        },
    )

    assert result["ranking"][0]["job_id"] == good["job_id"]
    assert result["ranking"][0]["total_score"] > result["ranking"][1]["total_score"]
    assert "city" in result["ranking"][1]["hard_constraints"]["penalties"]
    assert "evidence" in result["ranking"][1]["uncertainties"]
