"""Evidence-constrained resume generation for Advisor.

This module keeps resume generation deterministic by default: every generated
bullet is tied to explicit evidence atoms, and the harness rejects unsupported
claims before any final Markdown is emitted.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.job_store import JobStore

RISKY_TERMS = ["主导", "独立负责", "显著提升", "大幅提升", "精通", "专家级", "首创"]
NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?\s*(?:%|％|人|万|元|个月|年|项|个|名|倍|k|K)?")

WRITER_CONSTRAINTS = {
    "max_bullet_chars": 90,
    "risky_terms": RISKY_TERMS,
    "rules": [
        "不得新增 evidence 中没有的事实、数字、技能、项目、岗位、成果",
        "每条 bullet 必须保留 evidence_ids 与 matched_requirements",
        "不得使用高风险词：主导、独立负责、显著提升、大幅提升、精通、专家级、首创",
        f"每条 bullet 不超过 {90} 个中文字符",
    ],
}


@dataclass
class EvidenceStore:
    """JSONL-backed evidence atom store."""

    path: str | Path

    def __post_init__(self) -> None:
        self.path_obj = Path(self.path)
        self._items = self._load()
        self._by_id = {str(item["evidence_id"]): item for item in self._items}

    def _load(self) -> List[Dict[str, Any]]:
        if not self.path_obj.exists():
            raise FileNotFoundError(f"evidence file not found: {self.path_obj}")
        items: List[Dict[str, Any]] = []
        with self.path_obj.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if not item.get("evidence_id"):
                    raise ValueError(f"missing evidence_id at {self.path_obj}:{line_no}")
                item.setdefault("claims", [])
                item.setdefault("skills", [])
                item.setdefault("proof", {})
                items.append(item)
        return items

    def all(self) -> List[Dict[str, Any]]:
        return list(self._items)

    def get(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        return self._by_id.get(evidence_id)

    def search(self, query_terms: Iterable[str], limit: int = 5) -> List[Dict[str, Any]]:
        terms = _normalize_terms(query_terms)
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for item in self._items:
            score = _score_text_against_terms(_evidence_search_text(item), terms)
            if score > 0:
                enriched = dict(item)
                enriched["match_score"] = round(score, 4)
                scored.append((score, enriched))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:limit]]


def _norm_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _normalize_terms(values: Iterable[str]) -> List[str]:
    seen = []
    for value in values:
        token = str(value).strip()
        if token and token not in seen:
            seen.append(token)
    return seen


def _evidence_search_text(item: Dict[str, Any]) -> str:
    parts = [item.get("title", ""), item.get("type", "")]
    parts.extend(_norm_list(item.get("claims")))
    parts.extend(_norm_list(item.get("skills")))
    return " ".join(parts).lower()


def _score_text_against_terms(text: str, terms: List[str]) -> float:
    if not terms:
        return 0.0
    text_l = text.lower()
    score = 0.0
    for term in terms:
        term_l = term.lower()
        if not term_l:
            continue
        if term_l in text_l:
            score += 1.0
        else:
            # Weak character-overlap support for Chinese phrases like 金融科技 vs 金融.
            chars = {ch for ch in term_l if not ch.isspace()}
            if chars:
                overlap = sum(1 for ch in chars if ch in text_l) / len(chars)
                if overlap >= 0.5:
                    score += 0.35 * overlap
    return score / max(1, len(terms))


def parse_job_card(job: Dict[str, Any]) -> Dict[str, Any]:
    requirements_raw = _norm_list(job.get("requirements"))
    keywords = _normalize_terms(_norm_list(job.get("keywords")))
    responsibilities = _norm_list(job.get("responsibilities"))
    if not requirements_raw:
        requirements_raw = responsibilities[:5]
    requirements = []
    for idx, text in enumerate(requirements_raw, start=1):
        req_keywords = [kw for kw in keywords if kw.lower() in text.lower()]
        if not req_keywords:
            req_keywords = _extract_requirement_terms(text, keywords)
        requirements.append(
            {
                "id": f"req_{idx}",
                "text": text,
                "importance": round(max(0.5, 1.0 - (idx - 1) * 0.08), 4),
                "keywords": req_keywords,
            }
        )
    return {
        "job_id": job.get("job_id"),
        "title": job.get("title", "unknown"),
        "company": job.get("company", "unknown"),
        "city": job.get("city", "unknown"),
        "job_family": job.get("job_family", "unknown"),
        "responsibilities": responsibilities,
        "requirements": requirements,
        "keywords": keywords,
        "top_requirements": [req["id"] for req in requirements[:5]],
        "source_url": job.get("source_url", ""),
    }


def _extract_requirement_terms(text: str, global_keywords: List[str]) -> List[str]:
    terms = []
    for kw in global_keywords:
        if any(ch in text for ch in kw):
            terms.append(kw)
    if terms:
        return terms[:3]
    # Fallback terms are only used for scoring, not as new facts.
    return [piece for piece in re.split(r"[，,、\s]+", text) if piece][:3]


def match_evidence_to_job(job: Dict[str, Any], evidence_store: EvidenceStore, max_evidence: int = 5) -> Dict[str, Any]:
    requirements = job.get("requirements", [])
    global_terms = _normalize_terms(job.get("keywords", []))
    evidence_scores: Dict[str, Dict[str, Any]] = {}
    coverage: Dict[str, List[str]] = {req.get("id"): [] for req in requirements}

    for req in requirements:
        req_id = req.get("id")
        req_terms = _normalize_terms(req.get("keywords", [])) or _normalize_terms([req.get("text", "")])
        terms = _normalize_terms(list(req_terms) + global_terms)
        for evidence in evidence_store.all():
            score = _score_text_against_terms(_evidence_search_text(evidence), terms)
            score *= float(req.get("importance", 1.0))
            if score <= 0:
                continue
            entry = evidence_scores.setdefault(
                evidence["evidence_id"],
                {
                    **evidence,
                    "match_score": 0.0,
                    "matched_requirements": [],
                    "matched_terms": [],
                },
            )
            entry["match_score"] += score
            if req_id not in entry["matched_requirements"]:
                entry["matched_requirements"].append(req_id)
            entry["matched_terms"] = _normalize_terms(entry["matched_terms"] + terms)
            if req_id and evidence["evidence_id"] not in coverage[req_id]:
                coverage[req_id].append(evidence["evidence_id"])

    selected = list(evidence_scores.values())
    selected.sort(key=lambda item: (len(item["matched_requirements"]), item["match_score"]), reverse=True)
    selected = selected[:max_evidence]
    selected_ids = {item["evidence_id"] for item in selected}
    selected_coverage = {
        req_id: [eid for eid in ids if eid in selected_ids]
        for req_id, ids in coverage.items()
    }
    return {
        "job_id": job.get("job_id"),
        "selected_evidence": [
            {**item, "match_score": round(float(item["match_score"]), 4)} for item in selected
        ],
        "coverage": selected_coverage,
        "uncovered_requirements": [req_id for req_id, ids in selected_coverage.items() if not ids],
    }


def draft_resume(job: Dict[str, Any], match_plan: Dict[str, Any]) -> Dict[str, Any]:
    bullets = []
    for item in match_plan.get("selected_evidence", []):
        claims = _norm_list(item.get("claims"))
        skills = _norm_list(item.get("skills"))
        title = str(item.get("title") or item.get("evidence_id"))
        claim_text = "；".join(claims[:2]) if claims else title
        skill_text = "、".join(skills[:4])
        if skill_text:
            text = f"围绕{title}，沉淀{skill_text}相关能力：{claim_text}。"
        else:
            text = f"围绕{title}，完成相关经历沉淀：{claim_text}。"
        bullets.append(
            {
                "section": _section_for_type(item.get("type")),
                "text": _shrink_bullet(text, 90),
                "evidence_ids": [item["evidence_id"]],
                "matched_requirements": item.get("matched_requirements", []),
                "risk_flags": [],
            }
        )
    return {
        "job_id": job.get("job_id"),
        "target_title": job.get("title"),
        "company": job.get("company"),
        "positioning": _positioning(job),
        "bullets": bullets,
    }


def _section_for_type(value: Any) -> str:
    mapping = {"project": "项目经历", "internship": "实习经历", "paper": "研究经历", "education": "教育背景"}
    return mapping.get(str(value), "相关经历")


def _positioning(job: Dict[str, Any]) -> str:
    title = str(job.get("title") or "目标岗位")
    family = str(job.get("job_family") or "")
    if "产品" in title or "产品" in family:
        return "金融与 AI 应用交叉背景，强调需求理解、产品原型和技术落地能力。"
    if "量化" in title or "投研" in title:
        return "经济金融背景结合数学建模与 Python/R 能力，强调研究和数据分析能力。"
    return "结合经济金融背景、AI 工具链和项目落地经验进行岗位定制。"


def _shrink_bullet(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip("；，、 ") + "。"


class ResumeHarness:
    def __init__(self, evidence_store: EvidenceStore) -> None:
        self.evidence_store = evidence_store

    def validate(self, job: Dict[str, Any], draft: Dict[str, Any]) -> Dict[str, Any]:
        issues: List[Dict[str, Any]] = []
        bullets = draft.get("bullets", [])
        for idx, bullet in enumerate(bullets, start=1):
            text = str(bullet.get("text") or "")
            evidence_ids = _norm_list(bullet.get("evidence_ids"))
            if not evidence_ids:
                issues.append({"code": "missing_evidence", "bullet_index": idx, "message": "bullet 缺少 evidence_ids"})
            evidence_items = []
            for eid in evidence_ids:
                item = self.evidence_store.get(eid)
                if item is None:
                    issues.append({"code": "unknown_evidence", "bullet_index": idx, "message": f"未知 evidence_id: {eid}"})
                else:
                    evidence_items.append(item)

            numbers = [n.strip() for n in NUMBER_PATTERN.findall(text) if n.strip()]
            if numbers:
                evidence_text = " ".join(" ".join(_norm_list(item.get("claims"))) for item in evidence_items)
                for number in numbers:
                    if number and number not in evidence_text:
                        issues.append({"code": "unsupported_number", "bullet_index": idx, "message": f"未证实数字: {number}"})

            if any(term in text for term in RISKY_TERMS):
                if not evidence_items or max(_confidence(item) for item in evidence_items) < 0.9:
                    issues.append({"code": "risky_exaggeration", "bullet_index": idx, "message": "高风险表达缺少高置信证据"})

            if len(text) > 90:
                issues.append({"code": "bullet_too_long", "bullet_index": idx, "message": "bullet 超过 90 字"})

        top_requirements = _norm_list(job.get("top_requirements"))
        if not top_requirements:
            top_requirements = [req.get("id") for req in job.get("requirements", [])[:5]]
        covered = set()
        for bullet in bullets:
            covered.update(_norm_list(bullet.get("matched_requirements")))
        if top_requirements:
            needed = min(len(top_requirements), 3) if len(top_requirements) >= 3 else 1
            covered_count = len([req_id for req_id in top_requirements if req_id in covered])
            if covered_count < needed:
                issues.append(
                    {
                        "code": "low_jd_coverage",
                        "message": f"核心需求覆盖不足: {covered_count}/{len(top_requirements)}，最低需要 {needed}",
                    }
                )

        return {
            "passed": not issues,
            "issues": issues,
            "metrics": {
                "bullet_count": len(bullets),
                "top_requirement_count": len(top_requirements),
                "covered_top_requirement_count": len([req_id for req_id in top_requirements if req_id in covered]),
            },
        }


def _confidence(item: Dict[str, Any]) -> float:
    proof = item.get("proof") or {}
    try:
        return float(proof.get("confidence", 0.0))
    except (TypeError, ValueError):
        return 0.0


def build_resume_for_job(advisor_data_dir: str | Path, job_id: str, evidence_path: str | Path | None = None) -> Dict[str, Any]:
    """Deterministic full pipeline: prepare + draft + harness + write files."""
    advisor_data_dir = Path(advisor_data_dir)
    prepared = prepare_resume(advisor_data_dir, job_id, evidence_path=evidence_path)
    draft = prepared["draft"]
    harness_report = ResumeHarness(prepared["evidence_store"]).validate(prepared["jd_parsed"], draft)
    return _write_output(advisor_data_dir, job_id, prepared["jd_parsed"], prepared["match_plan"], draft, harness_report)


def prepare_resume(advisor_data_dir: str | Path, job_id: str, evidence_path: str | Path | None = None) -> Dict[str, Any]:
    """Phase 1: load evidence, parse JD, match, produce deterministic draft.
    Returns everything the LLM writer needs plus the draft for validation.
    """
    advisor_data_dir = Path(advisor_data_dir)
    store = JobStore(advisor_data_dir)
    job_card = store.get(job_id)
    if not job_card:
        raise KeyError(f"job not found: {job_id}")
    evidence_path = Path(evidence_path) if evidence_path else advisor_data_dir / "resume" / "evidence.jsonl"
    evidence_store = EvidenceStore(evidence_path)

    jd_parsed = parse_job_card(job_card)
    match_plan = match_evidence_to_job(jd_parsed, evidence_store)
    draft = draft_resume(jd_parsed, match_plan)
    draft["writer"] = "deterministic"
    return {
        "job_id": job_id,
        "jd_parsed": jd_parsed,
        "match_plan": match_plan,
        "draft": draft,
        "evidence_store": evidence_store,
        "writer_constraints": WRITER_CONSTRAINTS,
    }


def validate_resume(
    advisor_data_dir: str | Path,
    job_id: str,
    rewritten_bullets: List[Dict[str, Any]],
    evidence_path: str | Path | None = None,
    writer_name: str = "llm",
) -> Dict[str, Any]:
    """Phase 2: take LLM-rewritten bullets, validate against evidence, write output."""
    advisor_data_dir = Path(advisor_data_dir)
    evidence_path = Path(evidence_path) if evidence_path else advisor_data_dir / "resume" / "evidence.jsonl"
    evidence_store = EvidenceStore(evidence_path)

    store = JobStore(advisor_data_dir)
    job_card = store.get(job_id)
    if not job_card:
        raise KeyError(f"job not found: {job_id}")
    jd_parsed = parse_job_card(job_card)
    match_plan = match_evidence_to_job(jd_parsed, evidence_store)
    deterministic_draft = draft_resume(jd_parsed, match_plan)

    merged_bullets = _merge_rewritten_bullets(deterministic_draft["bullets"], rewritten_bullets, match_plan)
    draft = {**deterministic_draft, "bullets": merged_bullets, "writer": writer_name}
    harness_report = ResumeHarness(evidence_store).validate(jd_parsed, draft)
    return _write_output(advisor_data_dir, job_id, jd_parsed, match_plan, draft, harness_report)


def _merge_rewritten_bullets(
    original_bullets: List[Dict[str, Any]],
    rewritten_bullets: List[Dict[str, Any]],
    match_plan: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Merge LLM-rewritten bullet texts with original metadata, enforcing evidence constraints."""
    if len(rewritten_bullets) != len(original_bullets):
        raise ValueError(f"rewritten bullet count mismatch: {len(rewritten_bullets)} != {len(original_bullets)}")

    allowed_evidence_ids = {str(item.get("evidence_id")) for item in match_plan.get("selected_evidence", [])}
    merged = []
    for idx, (original, new) in enumerate(zip(original_bullets, rewritten_bullets), start=1):
        evidence_ids = _norm_list(new.get("evidence_ids"))
        matched_requirements = _norm_list(new.get("matched_requirements"))
        original_eids = set(_norm_list(original.get("evidence_ids")))
        unknown = [eid for eid in evidence_ids if eid not in allowed_evidence_ids or eid not in original_eids]
        if unknown:
            raise ValueError(f"rewritten bullet {idx} changed evidence_id: {', '.join(unknown)}")
        original_reqs = set(_norm_list(original.get("matched_requirements")))
        invalid = [r for r in matched_requirements if r not in original_reqs]
        if invalid:
            raise ValueError(f"rewritten bullet {idx} changed matched_requirements: {', '.join(invalid)}")
        text = str(new.get("text") or "").strip()
        if not text:
            raise ValueError(f"rewritten bullet {idx} has empty text")
        merged.append({
            **original,
            "section": str(new.get("section") or original.get("section") or "相关经历"),
            "text": text,
            "evidence_ids": evidence_ids or _norm_list(original.get("evidence_ids")),
            "matched_requirements": matched_requirements or _norm_list(original.get("matched_requirements")),
        })
    return merged


def _write_output(
    advisor_data_dir: Path,
    job_id: str,
    jd_parsed: Dict[str, Any],
    match_plan: Dict[str, Any],
    draft: Dict[str, Any],
    harness_report: Dict[str, Any],
) -> Dict[str, Any]:
    output_dir = advisor_data_dir / "resume" / "outputs" / f"{job_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "jd_parsed.json", jd_parsed)
    _write_json(output_dir / "match_plan.json", match_plan)
    _write_json(output_dir / "resume_draft.json", draft)
    (output_dir / "harness_report.md").write_text(_render_harness_report(harness_report), encoding="utf-8")
    (output_dir / "resume_final.md").write_text(_render_resume_markdown(draft, harness_report), encoding="utf-8")
    return {
        "output_dir": str(output_dir),
        "jd_parsed": jd_parsed,
        "match_plan": match_plan,
        "resume_draft": draft,
        "harness_report": harness_report,
    }


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _render_harness_report(report: Dict[str, Any]) -> str:
    lines = ["# Resume Harness Report", "", f"Status: {'PASS' if report.get('passed') else 'FAIL'}", "", "## Metrics"]
    for key, value in report.get("metrics", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Issues"])
    if not report.get("issues"):
        lines.append("- 无")
    else:
        for issue in report.get("issues", []):
            loc = f" bullet={issue.get('bullet_index')}" if issue.get("bullet_index") else ""
            lines.append(f"- [{issue.get('code')}]{loc} {issue.get('message')}")
    return "\n".join(lines) + "\n"


def _render_resume_markdown(draft: Dict[str, Any], report: Dict[str, Any]) -> str:
    lines = [f"# {draft.get('target_title')} - 定制简历草稿", "", f"目标公司：{draft.get('company')}", "", f"定位：{draft.get('positioning')}", ""]
    if not report.get("passed"):
        lines.extend(["> 注意：Harness 未通过，此草稿仅供修订，不建议直接投递。", ""])
    sections: Dict[str, List[Dict[str, Any]]] = {}
    for bullet in draft.get("bullets", []):
        sections.setdefault(bullet.get("section", "相关经历"), []).append(bullet)
    for section, bullets in sections.items():
        lines.extend([f"## {section}", ""])
        for bullet in bullets:
            evidence = ", ".join(bullet.get("evidence_ids", []))
            reqs = ", ".join(bullet.get("matched_requirements", []))
            lines.append(f"- {bullet.get('text')}  ")
            lines.append(f"  evidence: {evidence}; matched_requirements: {reqs}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _default_evidence_rows() -> List[Dict[str, Any]]:
    return [
        {
            "evidence_id": "project_lingnan_ai_database",
            "title": "Lingnan-AI-Database",
            "type": "project",
            "claims": ["FastAPI + SQLite 全栈 Wiki", "支持 AI 资料结构化沉淀与检索"],
            "skills": ["FastAPI", "SQLite", "RAG", "知识库", "Python", "AI"],
            "proof": {"source_type": "user_profile", "confidence": 0.95},
            "risk": "low",
        },
        {
            "evidence_id": "project_agent_network",
            "title": "agent_network",
            "type": "project",
            "claims": ["Flask + LangGraph 多 AI 博弈平台", "实现多 Agent 协作工作流"],
            "skills": ["Agent", "LangGraph", "Flask", "AI", "多智能体"],
            "proof": {"source_type": "user_profile", "confidence": 0.92},
            "risk": "low",
        },
        {
            "evidence_id": "intern_cmb_investment_banking",
            "title": "招行投行部实习",
            "type": "internship",
            "claims": ["在招行投行部实习", "使用 Claude Code 多 agent 自动化处理业务材料整理与信息归纳任务"],
            "skills": ["金融", "投行", "Agent", "自动化", "材料整理"],
            "proof": {"source_type": "user_profile", "confidence": 0.9},
            "risk": "medium",
        },
        {
            "evidence_id": "paper_network_foundation_power_law",
            "title": "Network Foundation of Power Law",
            "type": "paper",
            "claims": ["第一作者研究 Network Foundation of Power Law", "围绕势博弈、幂律分布和比较静态进行数学建模"],
            "skills": ["数学建模", "博弈论", "比较静态", "研究", "Python"],
            "proof": {"source_type": "user_profile", "confidence": 0.93},
            "risk": "low",
        },
    ]


def ensure_default_evidence(advisor_data_dir: str | Path) -> Path:
    path = Path(advisor_data_dir) / "resume" / "evidence.jsonl"
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in _default_evidence_rows()) + "\n", encoding="utf-8")
    return path


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evidence-constrained resume generator.")
    sub = parser.add_subparsers(dest="command")

    # build: deterministic full pipeline (backward compatible)
    build_p = sub.add_parser("build", help="Build deterministic resume draft")
    build_p.add_argument("job_id")
    build_p.add_argument("--advisor-data-dir", default="advisor_data")
    build_p.add_argument("--evidence-path", default=None)

    # prepare: phase 1 — evidence + matching, output JSON for LLM
    prep_p = sub.add_parser("prepare", help="Prepare structured data for LLM rewriting")
    prep_p.add_argument("job_id")
    prep_p.add_argument("--advisor-data-dir", default="advisor_data")
    prep_p.add_argument("--evidence-path", default=None)

    # validate: phase 2 — take LLM-rewritten bullets, run harness, write files
    val_p = sub.add_parser("validate", help="Validate LLM-rewritten bullets and write output")
    val_p.add_argument("job_id")
    val_p.add_argument("--advisor-data-dir", default="advisor_data")
    val_p.add_argument("--evidence-path", default=None)
    val_p.add_argument("--writer-name", default="llm")
    val_p.add_argument("--draft-json", required=True, help="JSON with rewritten bullets [{section, text, evidence_ids, matched_requirements}]")

    # backward compat: bare job_id → build
    args = parser.parse_args(argv)
    if args.command == "build" or (args.command is None and hasattr(args, "job_id")):
        job_id = getattr(args, "job_id", None)
        if not job_id:
            parser.print_help()
            return 1
        evidence_path = Path(args.evidence_path) if getattr(args, "evidence_path", None) else ensure_default_evidence(args.advisor_data_dir)
        output = build_resume_for_job(args.advisor_data_dir, job_id, evidence_path=evidence_path)
        print(json.dumps({"output_dir": output["output_dir"], "passed": output["harness_report"]["passed"]}, ensure_ascii=False, indent=2))
        return 0 if output["harness_report"]["passed"] else 2

    if args.command == "prepare":
        evidence_path = Path(args.evidence_path) if args.evidence_path else ensure_default_evidence(args.advisor_data_dir)
        prepared = prepare_resume(args.advisor_data_dir, args.job_id, evidence_path=evidence_path)
        # Output everything except the in-memory evidence_store object
        out = {
            "job_id": prepared["job_id"],
            "jd_parsed": prepared["jd_parsed"],
            "match_plan": {
                "job_id": prepared["match_plan"]["job_id"],
                "selected_evidence": prepared["match_plan"]["selected_evidence"],
                "coverage": prepared["match_plan"]["coverage"],
                "uncovered_requirements": prepared["match_plan"]["uncovered_requirements"],
            },
            "draft": prepared["draft"],
            "writer_constraints": prepared["writer_constraints"],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.command == "validate":
        evidence_path = Path(args.evidence_path) if args.evidence_path else ensure_default_evidence(args.advisor_data_dir)
        rewritten_bullets = json.loads(args.draft_json)
        output = validate_resume(
            args.advisor_data_dir, args.job_id, rewritten_bullets,
            evidence_path=evidence_path, writer_name=args.writer_name,
        )
        print(json.dumps({"output_dir": output["output_dir"], "passed": output["harness_report"]["passed"]}, ensure_ascii=False, indent=2))
        return 0 if output["harness_report"]["passed"] else 2

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
