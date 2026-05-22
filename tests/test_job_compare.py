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


def test_company_soft_cap_penalises_overflow_jobs(tmp_path):
    store = JobStore(tmp_path)
    # 5 jobs for A公司 (all same score since same extraction)
    for i in range(5):
        store.upsert_from_extraction(
            raw_text=f"广州 AI岗位{i}",
            source_url=f"https://example.com/a{i}",
            source_type="web",
            extraction={
                "title": f"AI岗位{i}",
                "company": "A公司",
                "city": "广州",
                "job_family": "AI产品经理",
                "keywords": ["AI", "Python"],
                "requirements": ["Python"],
            },
        )
    # 2 jobs for B公司
    for i in range(2):
        store.upsert_from_extraction(
            raw_text=f"广州 后端岗位{i}",
            source_url=f"https://example.com/b{i}",
            source_type="web",
            extraction={
                "title": f"后端岗位{i}",
                "company": "B公司",
                "city": "广州",
                "job_family": "后端",
                "keywords": ["Python", "SQL"],
                "requirements": ["Python"],
            },
        )

    all_jobs = list(store.list_jobs())
    all_ids = [j["job_id"] for j in all_jobs]

    # cap=0: no penalty, all 7 in ranking, no overflow
    result_no_cap = compare_jobs(all_jobs, all_ids, max_per_company=0)
    assert len(result_no_cap["ranking"]) == 7
    assert result_no_cap["overflow"] == []

    # cap=3: A公司 has 5 jobs → top 3 keep full score, 4th gets *0.7, 5th gets *0.49
    result_cap = compare_jobs(all_jobs, all_ids, max_per_company=3)
    assert len(result_cap["ranking"]) == 7  # soft cap: all still present
    a_items = [r for r in result_cap["ranking"] if r["company"] == "A公司"]
    assert len(a_items) == 5

    # First 3 from A公司 should be unpenalised (same score)
    unpenalised_a = [r for r in a_items if "company_overflow" not in r.get("penalties", {})]
    penalised_a = [r for r in a_items if "company_overflow" in r.get("penalties", {})]
    assert len(unpenalised_a) == 3
    assert len(penalised_a) == 2

    # Penalised scores must be strictly lower
    base_score = unpenalised_a[0]["total_score"]
    assert penalised_a[0]["total_score"] < base_score
    assert penalised_a[1]["total_score"] < penalised_a[0]["total_score"]

    # Overflow list tracks which jobs were penalised
    assert len(result_cap["overflow"]) == 2


def test_company_cap_3_is_default(tmp_path):
    store = JobStore(tmp_path)
    for i in range(5):
        store.upsert_from_extraction(
            raw_text=f"广州 岗位{i}",
            source_url=f"https://example.com/x{i}",
            source_type="web",
            extraction={
                "title": f"岗位{i}", "company": "X公司", "city": "广州",
                "job_family": "AI", "keywords": ["AI"], "requirements": ["AI"],
            },
        )
    all_jobs = list(store.list_jobs())
    all_ids = [j["job_id"] for j in all_jobs]
    # Call without explicit max_per_company → should default to 3
    result = compare_jobs(all_jobs, all_ids)
    assert result["max_per_company"] == 3
    penalised = [r for r in result["ranking"] if "company_overflow" in r.get("penalties", {})]
    assert len(penalised) == 2  # 5 jobs, cap 3 → 2 penalised
