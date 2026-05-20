"""Deterministic job comparison helpers for Advisor.

LLMs may explain the result, but the score itself should be reproducible and
inspectable.  This module intentionally uses simple transparent heuristics.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

DEFAULT_WEIGHTS = {
    "hard_constraints": 0.25,
    "skill_fit": 0.25,
    "growth_fit": 0.20,
    "industry_fit": 0.15,
    "cost_risk": 0.10,
    "evidence_confidence": 0.05,
}


def _norm_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _contains_any(haystack: Iterable[str], needles: Iterable[str]) -> int:
    hay = " ".join(_norm_list(list(haystack))).lower()
    count = 0
    for needle in needles:
        needle_s = str(needle).strip().lower()
        if needle_s and needle_s in hay:
            count += 1
    return count


def _ratio(count: int, total: int) -> float:
    if total <= 0:
        return 0.5
    return max(0.0, min(1.0, count / total))


def _evidence_is_present(job: Dict[str, Any]) -> bool:
    evidence_path = job.get("evidence_path")
    if not evidence_path:
        return False
    path = Path(str(evidence_path))
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return bool(payload)


def score_job(job: Dict[str, Any], user_preferences: Dict[str, Any] | None = None) -> Dict[str, Any]:
    prefs = user_preferences or {}
    preferred_cities = _norm_list(prefs.get("preferred_cities"))
    target_keywords = _norm_list(prefs.get("target_keywords"))
    target_job_families = _norm_list(prefs.get("target_job_families"))

    penalties: Dict[str, str] = {}
    city = str(job.get("city") or "unknown")
    if preferred_cities and city not in preferred_cities:
        penalties["city"] = f"城市 {city} 不在偏好城市 {preferred_cities} 中"
    hard_constraints = 1.0 - 0.5 * len(penalties)
    hard_constraints = max(0.0, hard_constraints)

    searchable = []
    for key in ["title", "job_family", "keywords", "requirements", "responsibilities"]:
        searchable.extend(_norm_list(job.get(key)))

    skill_fit = _ratio(_contains_any(searchable, target_keywords), len(target_keywords))
    growth_fit = _ratio(_contains_any(_norm_list(job.get("job_family")) + _norm_list(job.get("title")), target_job_families), len(target_job_families))
    industry_fit = _ratio(_contains_any(searchable, ["金融", "金融科技", "银行", "证券", "量化", "投研"]), 2)

    cost_risk = 0.7
    work_mode = str(job.get("work_mode") or "").lower()
    if any(token in work_mode for token in ["高强度", "出差", "996", "加班"]):
        cost_risk = 0.35

    evidence_present = _evidence_is_present(job)
    evidence_confidence = 1.0 if evidence_present else 0.3

    dimensions = {
        "hard_constraints": hard_constraints,
        "skill_fit": skill_fit,
        "growth_fit": growth_fit,
        "industry_fit": industry_fit,
        "cost_risk": cost_risk,
        "evidence_confidence": evidence_confidence,
    }
    total = sum(DEFAULT_WEIGHTS[key] * dimensions[key] for key in DEFAULT_WEIGHTS)

    uncertainties = []
    for key in ["city", "job_family", "requirements", "compensation", "work_mode"]:
        value = job.get(key)
        if value in [None, "", "unknown", []]:
            uncertainties.append(key)
    if not evidence_present:
        uncertainties.append("evidence")

    return {
        "job_id": job.get("job_id"),
        "title": job.get("title"),
        "company": job.get("company"),
        "city": city,
        "total_score": round(total, 4),
        "dimensions": {key: round(value, 4) for key, value in dimensions.items()},
        "hard_constraints": {"penalties": penalties},
        "uncertainties": uncertainties,
    }


def compare_jobs(
    jobs: Iterable[Dict[str, Any]],
    job_ids: Iterable[str],
    user_preferences: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    ids = list(job_ids)
    selected = [job for job in jobs if job.get("job_id") in ids]
    ranking = [score_job(job, user_preferences) for job in selected]
    ranking.sort(key=lambda item: item["total_score"], reverse=True)
    return {
        "weights": DEFAULT_WEIGHTS,
        "ranking": ranking,
        "missing_job_ids": [job_id for job_id in ids if not any(job.get("job_id") == job_id for job in selected)],
    }
