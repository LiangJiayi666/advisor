import json
from pathlib import Path

import pytest

from scripts.job_store import JobStore
from scripts.resume_generator import (
    EvidenceStore,
    ResumeHarness,
    _merge_rewritten_bullets,
    build_resume_for_job,
    draft_resume,
    match_evidence_to_job,
    parse_job_card,
    prepare_resume,
    validate_resume,
)


def _write_evidence(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "evidence_id": "project_agent_network",
            "title": "agent_network",
            "type": "project",
            "claims": ["Flask + LangGraph 多 AI 博弈平台", "实现多 Agent 协作工作流"],
            "skills": ["Agent", "LangGraph", "Flask", "AI"],
            "proof": {"source_type": "user_profile", "confidence": 0.92},
            "risk": "low",
        },
        {
            "evidence_id": "intern_cmb_ib",
            "title": "招行投行部实习",
            "type": "internship",
            "claims": ["在招行投行部实习", "使用 Claude Code 多 agent 自动化处理材料整理"],
            "skills": ["金融", "投行", "Agent", "自动化"],
            "proof": {"source_type": "user_confirmed_memory", "confidence": 0.9},
            "risk": "medium",
        },
        {
            "evidence_id": "project_lingnan_ai_database",
            "title": "Lingnan-AI-Database",
            "type": "project",
            "claims": ["FastAPI + SQLite 全栈 Wiki", "支持 AI 资料结构化沉淀与检索"],
            "skills": ["FastAPI", "SQLite", "RAG", "知识库", "Python"],
            "proof": {"source_type": "project_directory", "confidence": 0.95},
            "risk": "low",
        },
    ]
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    return path


def _make_job(store_dir: Path) -> dict:
    store = JobStore(store_dir)
    return store.upsert_from_extraction(
        raw_text="广州 AI 产品经理实习，要求 Agent、Python、金融科技理解。",
        source_url="https://example.com/job/pm",
        source_type="web",
        extraction={
            "title": "AI 产品经理实习",
            "company": "A公司",
            "city": "广州",
            "job_family": "AI产品经理",
            "requirements": ["熟悉 Agent 产品", "掌握 Python", "理解金融科技场景"],
            "keywords": ["Agent", "Python", "金融科技"],
            "responsibilities": ["负责 AI 产品需求分析"],
        },
    )


# ---- Existing tests (preserved) ----


def test_evidence_store_loads_jsonl_and_searches_by_skills_and_claims(tmp_path):
    evidence_path = _write_evidence(tmp_path / "resume" / "evidence.jsonl")
    store = EvidenceStore(evidence_path)
    results = store.search(["Agent", "金融科技", "Python"], limit=2)
    assert results[0]["evidence_id"] in {"project_agent_network", "project_lingnan_ai_database", "intern_cmb_ib"}
    assert len(results) == 2
    assert all("match_score" in item for item in results)


def test_parse_job_card_extracts_requirements_keywords_and_top_requirements(tmp_path):
    job = _make_job(tmp_path)
    parsed = parse_job_card(job)
    assert parsed["job_id"] == job["job_id"]
    assert parsed["requirements"][0]["text"] == "熟悉 Agent 产品"
    assert parsed["keywords"] == ["Agent", "Python", "金融科技"]


def test_matcher_selects_evidence_covering_agent_python_and_fintech(tmp_path):
    evidence_path = _write_evidence(tmp_path / "resume" / "evidence.jsonl")
    evidence_store = EvidenceStore(evidence_path)
    job = {
        "job_id": "job_x",
        "title": "AI 产品经理实习",
        "company": "A公司",
        "requirements": [
            {"id": "req_1", "text": "熟悉 Agent 产品", "importance": 1.0, "keywords": ["Agent"]},
            {"id": "req_2", "text": "掌握 Python", "importance": 0.9, "keywords": ["Python"]},
            {"id": "req_3", "text": "理解金融科技场景", "importance": 0.8, "keywords": ["金融科技", "金融"]},
        ],
        "keywords": ["Agent", "Python", "金融科技"],
    }
    plan = match_evidence_to_job(job, evidence_store, max_evidence=3)
    selected_ids = {item["evidence_id"] for item in plan["selected_evidence"]}
    assert "project_agent_network" in selected_ids
    assert "project_lingnan_ai_database" in selected_ids


def test_writer_generates_evidence_bound_bullets(tmp_path):
    evidence_path = _write_evidence(tmp_path / "resume" / "evidence.jsonl")
    evidence_store = EvidenceStore(evidence_path)
    job = {
        "job_id": "job_x",
        "title": "AI 产品经理实习",
        "company": "A公司",
        "requirements": [{"id": "req_1", "text": "熟悉 Agent 产品", "importance": 1.0, "keywords": ["Agent"]}],
        "keywords": ["Agent"],
    }
    plan = match_evidence_to_job(job, evidence_store, max_evidence=2)
    draft = draft_resume(job, plan)
    assert draft["bullets"]
    assert all(bullet["evidence_ids"] for bullet in draft["bullets"])


def test_harness_rejects_missing_evidence_unsupported_number_exaggeration_and_low_coverage(tmp_path):
    evidence_path = _write_evidence(tmp_path / "resume" / "evidence.jsonl")
    evidence_store = EvidenceStore(evidence_path)
    harness = ResumeHarness(evidence_store)
    job = {
        "requirements": [
            {"id": "req_1", "text": "Agent", "keywords": ["Agent"]},
            {"id": "req_2", "text": "Python", "keywords": ["Python"]},
            {"id": "req_3", "text": "金融", "keywords": ["金融"]},
        ],
        "top_requirements": ["req_1", "req_2", "req_3"],
    }
    bad_draft = {
        "bullets": [
            {"text": "主导系统建设并提升效率 60%", "evidence_ids": [], "matched_requirements": ["req_1"]},
            {"text": "独立负责金融科技 Agent 平台", "evidence_ids": ["intern_cmb_ib"], "matched_requirements": ["req_1"]},
        ]
    }
    report = harness.validate(job, bad_draft)
    assert report["passed"] is False
    assert any(issue["code"] == "missing_evidence" for issue in report["issues"])
    assert any(issue["code"] == "unsupported_number" for issue in report["issues"])
    assert any(issue["code"] == "risky_exaggeration" for issue in report["issues"])
    assert any(issue["code"] == "low_jd_coverage" for issue in report["issues"])


def test_build_resume_for_job_writes_all_outputs_for_real_job_id(tmp_path):
    evidence_path = _write_evidence(tmp_path / "resume" / "evidence.jsonl")
    job = _make_job(tmp_path)
    output = build_resume_for_job(tmp_path, job["job_id"], evidence_path=evidence_path)
    assert output["harness_report"]["passed"] is True
    for filename in ["jd_parsed.json", "match_plan.json", "resume_draft.json", "harness_report.md", "resume_final.md"]:
        assert (Path(output["output_dir"]) / filename).exists()
    final_text = (Path(output["output_dir"]) / "resume_final.md").read_text(encoding="utf-8")
    assert "AI 产品经理实习" in final_text
    assert "evidence:" in final_text


# ---- New tests: prepare/validate split ----


def test_prepare_returns_structured_data_with_constraints(tmp_path):
    evidence_path = _write_evidence(tmp_path / "resume" / "evidence.jsonl")
    job = _make_job(tmp_path)
    prepared = prepare_resume(tmp_path, job["job_id"], evidence_path=evidence_path)

    assert prepared["job_id"] == job["job_id"]
    assert prepared["jd_parsed"]["title"] == "AI 产品经理实习"
    assert prepared["match_plan"]["selected_evidence"]
    assert prepared["draft"]["bullets"]
    assert prepared["draft"]["writer"] == "deterministic"
    assert "rules" in prepared["writer_constraints"]
    assert prepared["evidence_store"] is not None


def test_validate_accepts_rewritten_bullets_and_writes_output(tmp_path):
    evidence_path = _write_evidence(tmp_path / "resume" / "evidence.jsonl")
    job = _make_job(tmp_path)

    # Phase 1: prepare
    prepared = prepare_resume(tmp_path, job["job_id"], evidence_path=evidence_path)
    original_bullets = prepared["draft"]["bullets"]

    # Simulate LLM rewriting: only change text, keep metadata, stay within 90 chars
    rewritten = [
        {**bullet, "text": "改写后的简历条目，涵盖核心能力与匹配需求。"}
        for bullet in original_bullets
    ]

    # Phase 2: validate
    output = validate_resume(tmp_path, job["job_id"], rewritten, evidence_path=evidence_path, writer_name="hermes")

    assert output["harness_report"]["passed"] is True
    assert output["resume_draft"]["writer"] == "hermes"
    assert "改写" in output["resume_draft"]["bullets"][0]["text"]
    final_text = (Path(output["output_dir"]) / "resume_final.md").read_text(encoding="utf-8")
    assert "改写" in final_text


def test_validate_rejects_invented_evidence_ids(tmp_path):
    evidence_path = _write_evidence(tmp_path / "resume" / "evidence.jsonl")
    job = _make_job(tmp_path)

    prepared = prepare_resume(tmp_path, job["job_id"], evidence_path=evidence_path)
    original_bullets = prepared["draft"]["bullets"]

    rewritten = [
        {**bullet, "evidence_ids": ["totally_fake_eid"]}
        for bullet in original_bullets
    ]

    with pytest.raises(ValueError, match="totally_fake_eid"):
        validate_resume(tmp_path, job["job_id"], rewritten, evidence_path=evidence_path)


def test_validate_rejects_wrong_bullet_count(tmp_path):
    evidence_path = _write_evidence(tmp_path / "resume" / "evidence.jsonl")
    job = _make_job(tmp_path)

    with pytest.raises(ValueError, match="mismatch"):
        validate_resume(tmp_path, job["job_id"], [{"text": "x", "evidence_ids": ["a"], "matched_requirements": []}], evidence_path=evidence_path)


def test_merge_rewritten_bullets_preserves_original_on_empty_fields():
    original = [
        {
            "section": "项目经历",
            "text": "原文",
            "evidence_ids": ["project_agent_network"],
            "matched_requirements": ["req_1"],
        }
    ]
    rewritten = [{"text": "改写后的文本", "evidence_ids": [], "matched_requirements": []}]
    match_plan = {"selected_evidence": [{"evidence_id": "project_agent_network"}]}

    merged = _merge_rewritten_bullets(original, rewritten, match_plan)

    assert merged[0]["text"] == "改写后的文本"
    assert merged[0]["evidence_ids"] == ["project_agent_network"]
    assert merged[0]["matched_requirements"] == ["req_1"]
