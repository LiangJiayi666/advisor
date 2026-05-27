"""Deterministic job comparison and ranking for Advisor.

Delegates all scoring logic to job_batch_rank so that there is a single
source of truth for track classification, keyword weights, and dimension
scoring.  This module provides the public API that the compare-jobs command
calls: compare by job_id subset, or rank the full corpus.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from scripts.job_batch_rank import (
    UserPreferences,
    _apply_company_soft_cap,
    _dedupe_group,
    _derive_keywords,
    _derive_track,
    _completeness,
    link_raw,
    _normalize_city,
    _normalize_company,
    _normalize_title,
    _norm_text,
    _norm_list,
    _primary_rows,
    _score_job,
    default_preferences,
    load_evidence_terms,
    load_jobs,
    load_raw_index,
)


def _resolve_jobs(
    jobs_jsonl: Path,
    raw_dir: Path,
    evidence_jsonl: Path,
    job_ids: List[str] | None = None,
    today: date | None = None,
) -> Dict[str, Any]:
    """Load, normalize, score, and optionally filter jobs.

    Returns a dict with:
      - "ranking": scored rows (possibly filtered by job_ids)
      - "total_in_corpus": count before filtering
      - "filtered_count": how many were kept
    """
    today = today or date.today()
    prefs = default_preferences()
    jobs = load_jobs(jobs_jsonl)
    raw_index = load_raw_index(raw_dir, today=today)
    evidence_terms = load_evidence_terms(evidence_jsonl)

    # --- normalize & score all jobs (same pipeline as batch_rank) ---
    normalized: List[Dict[str, Any]] = []
    for idx, job in enumerate(jobs, start=1):
        raw_match = link_raw(job, raw_index)
        city = _normalize_city(
            raw_match.get("city") if raw_match and raw_match.get("city") else job.get("city")
        )
        keywords = _derive_keywords(job, raw_match)
        requirements = raw_match.get("requirements", []) if raw_match else _norm_list(job.get("requirements"))
        responsibilities = raw_match.get("responsibilities", []) if raw_match else _norm_list(job.get("responsibilities"))
        deadline_text = raw_match.get("deadline_text", "") if raw_match else ""
        deadline_date = raw_match.get("deadline_date", "") if raw_match else ""
        deadline_confidence = raw_match.get("deadline_confidence", "none") if raw_match else "none"
        record = {
            "row_id": idx,
            "job_id": _norm_text(job.get("job_id")),
            "title": _norm_text(job.get("title")),
            "normalized_title": _normalize_title(job.get("title")),
            "company": _normalize_company(job.get("company")),
            "city": city,
            "recruit_type": job.get("recruit_type", ""),
            "job_family": _norm_text(job.get("job_family")),
            "source": _norm_text(job.get("source")),
            "source_url": _norm_text(job.get("source_url")),
            "bucket": _norm_text(job.get("bucket")),
            "reason": _norm_text(job.get("reason")),
            "raw_path": raw_match.get("raw_path", "") if raw_match else "",
            "requirements": requirements,
            "responsibilities": responsibilities,
            "keywords": keywords,
            "deadline_text": deadline_text,
            "deadline_date": deadline_date,
            "deadline_confidence": deadline_confidence,
        }
        record["completeness_score"] = _completeness(job, raw_match)
        record["target_track"] = _derive_track(
            " ".join([record["title"], record["job_family"], " ".join(record["keywords"])])
        )
        record["dedupe_group"] = _dedupe_group(record)
        normalized.append({**record, **_score_job(record, prefs, evidence_terms, today)})

    # --- dedupe: keep primary per group ---
    primary_by_group: Dict[str, Dict[str, Any]] = {}
    for row in normalized:
        group = row["dedupe_group"]
        score = (
            float(row.get("completeness_score") or 0.0),
            1.0 if row.get("raw_path") else 0.0,
            1.0 if row.get("source_url") else 0.0,
            1.0 if row.get("job_id") else 0.0,
        )
        if group not in primary_by_group or score > primary_by_group[group]["_primary_score"]:
            primary_by_group[group] = {**row, "_primary_score": score}
    for row in normalized:
        row["is_primary_in_group"] = primary_by_group[row["dedupe_group"]]["row_id"] == row["row_id"]

    # --- filter by job_ids if specified ---
    total_in_corpus = len(normalized)
    if job_ids:
        id_set = set(job_ids)
        # Also match by title/company for fuzzy resolution
        title_company_set = set()
        for jid in job_ids:
            # Try to find matches by partial title or company
            for row in normalized:
                rt = _normalize_title(row.get("title", ""))
                rc = _normalize_company(row.get("company", ""))
                if jid.lower() in rt.lower() or jid.lower() in rc.lower():
                    title_company_set.add(row["row_id"])

        filtered = [
            row for row in normalized
            if row.get("job_id") in id_set
            or row.get("normalized_job_id", row.get("job_id")) in id_set
            or row["row_id"] in title_company_set
        ]
        # If still empty, try keyword substring match against title
        if not filtered:
            for row in normalized:
                row_text = f"{row.get('title', '')} {row.get('company', '')}".lower()
                if any(jid.lower() in row_text for jid in job_ids):
                    filtered.append(row)
    else:
        filtered = normalized

    filtered.sort(key=lambda item: item["priority_score"], reverse=True)
    ranked = _apply_company_soft_cap(filtered)

    return {
        "ranking": ranked,
        "total_in_corpus": total_in_corpus,
        "filtered_count": len(ranked),
        "evidence_term_count": len(evidence_terms),
        "track_distribution": _track_distribution(ranked),
    }


def _track_distribution(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    from collections import Counter
    return dict(Counter(row.get("target_track", "unknown") for row in rows))


def compare_jobs(
    jobs_jsonl: Path,
    raw_dir: Path,
    evidence_jsonl: Path,
    job_ids: List[str] | None = None,
    max_per_company: int = 3,
    today: date | None = None,
) -> Dict[str, Any]:
    """Score and rank jobs.

    If job_ids is None or empty: rank the full corpus.
    If job_ids is provided: only rank the matching subset.
    """
    today = today or date.today()
    result = _resolve_jobs(jobs_jsonl, raw_dir, evidence_jsonl, job_ids=job_ids, today=today)
    ranking = result["ranking"]

    # Build a compact output for CC consumption
    output_lines: List[Dict[str, Any]] = []
    for idx, row in enumerate(ranking, start=1):
        dims = row.get("dimensions", {})
        output_lines.append({
            "rank": idx,
            "job_id": row.get("job_id") or row.get("normalized_job_id"),
            "title": row.get("title"),
            "company": row.get("company"),
            "city": row.get("city"),
            "target_track": row.get("target_track"),
            "fit_score": row.get("fit_score"),
            "priority_score": row.get("priority_score"),
            "skill_fit": dims.get("skill_fit"),
            "experience_fit": dims.get("experience_fit"),
            "industry_fit": dims.get("industry_fit"),
            "growth_fit": dims.get("growth_fit"),
            "deadline_date": row.get("deadline_date"),
            "strengths": row.get("top_strengths"),
            "risks": row.get("top_risks"),
            "penalties": row.get("hard_constraint_penalties"),
        })

    return {
        "mode": "full_corpus" if not job_ids else "filtered",
        "requested_ids": job_ids,
        "total_in_corpus": result["total_in_corpus"],
        "returned_count": len(output_lines),
        "track_distribution": result["track_distribution"],
        "ranking": output_lines,
    }


def main() -> int:
    """CLI entry point for quick testing."""
    import argparse
    parser = argparse.ArgumentParser(description="Score and rank jobs using the batch_rank scoring pipeline.")
    parser.add_argument("--jobs-jsonl", default="advisor_data/jobs/self/jobs.jsonl")
    parser.add_argument("--raw-dir", default="advisor_data/jobs/self/raw")
    parser.add_argument("--evidence-jsonl", default="advisor_data/resume/evidence.jsonl")
    parser.add_argument("job_ids", nargs="*", help="Optional job IDs or title/company fragments to filter. Omit for full corpus.")
    args = parser.parse_args()
    result = compare_jobs(
        Path(args.jobs_jsonl),
        Path(args.raw_dir),
        Path(args.evidence_jsonl),
        job_ids=args.job_ids or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
