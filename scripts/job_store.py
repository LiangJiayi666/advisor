"""Structured job storage for Advisor.

Job records are business data, not advisor derived memory.  This module keeps
job cards, raw job text, and field evidence under advisor_data/jobs/ so the
memory JSONL can stay focused on user preferences and decisions.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

CORE_FIELDS = [
    "title",
    "company",
    "city",
    "job_family",
    "source",
    "source_url",
]

EXTENDED_FIELDS = [
    "responsibilities",
    "requirements",
    "keywords",
    "seniority",
    "compensation",
    "work_mode",
    "tags",
]


class JobStore:
    """Append-safe structured storage for job cards.

    The public API intentionally stays small: upsert, list, get, and update.
    This keeps the Advisor tool surface aligned with the minimal viable toolset
    recommended by the architecture review.
    """

    def __init__(self, advisor_data_dir: str | Path) -> None:
        self.advisor_data_dir = Path(advisor_data_dir)
        self.jobs_dir = self.advisor_data_dir / "jobs"
        self.raw_dir = self.jobs_dir / "raw"
        self.evidence_dir = self.jobs_dir / "evidence"
        self.comparisons_dir = self.jobs_dir / "comparisons"
        self.jobs_path = self.jobs_dir / "jobs.jsonl"
        for directory in [self.jobs_dir, self.raw_dir, self.evidence_dir, self.comparisons_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _stable_id(self, source_url: str, title: str, company: str, raw_text: str) -> str:
        basis = source_url or f"{title}|{company}|{raw_text[:200]}"
        digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:10]
        return f"job_{digest}"

    def list_jobs(self) -> Iterable[Dict[str, Any]]:
        if not self.jobs_path.exists():
            return []
        jobs = []
        with self.jobs_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                jobs.append(json.loads(line))
        return jobs

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        for job in self.list_jobs():
            if job.get("job_id") == job_id:
                return job
        return None

    def _write_all(self, jobs: Iterable[Dict[str, Any]]) -> None:
        with self.jobs_path.open("w", encoding="utf-8") as handle:
            for job in jobs:
                handle.write(json.dumps(job, ensure_ascii=False, sort_keys=True) + "\n")

    def upsert_from_extraction(
        self,
        raw_text: str,
        source_url: str = "",
        source_type: str = "manual",
        extraction: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        extraction = extraction or {}
        now = self._now()
        title = str(extraction.get("title") or "unknown")
        company = str(extraction.get("company") or "unknown")
        job_id = str(extraction.get("job_id") or self._stable_id(source_url, title, company, raw_text))

        existing_jobs = list(self.list_jobs())
        existing_index = next(
            (
                idx
                for idx, job in enumerate(existing_jobs)
                if job.get("job_id") == job_id or (source_url and job.get("source_url") == source_url)
            ),
            None,
        )
        created_at = existing_jobs[existing_index].get("created_at", now) if existing_index is not None else now

        job: Dict[str, Any] = {
            "job_id": job_id,
            "title": title,
            "company": company,
            "city": extraction.get("city") or "unknown",
            "job_family": extraction.get("job_family") or "unknown",
            "source": source_type,
            "source_url": source_url,
            "created_at": created_at,
            "updated_at": now,
            "raw_path": str(self.raw_dir / f"{job_id}.md"),
            "evidence_path": str(self.evidence_dir / f"{job_id}.json"),
        }
        for field in EXTENDED_FIELDS:
            job[field] = extraction.get(field, [] if field in {"responsibilities", "requirements", "keywords", "tags"} else None)

        if existing_index is None:
            existing_jobs.append(job)
        else:
            existing_jobs[existing_index] = job
        self._write_all(existing_jobs)

        (self.raw_dir / f"{job_id}.md").write_text(raw_text, encoding="utf-8")
        evidence = extraction.get("evidence") or {}
        (self.evidence_dir / f"{job_id}.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return job

    def update(self, job_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        jobs = list(self.list_jobs())
        for idx, job in enumerate(jobs):
            if job.get("job_id") == job_id:
                updated = dict(job)
                for key, value in patch.items():
                    if key in {"job_id", "created_at", "raw_path", "evidence_path"}:
                        continue
                    updated[key] = value
                updated["updated_at"] = self._now()
                jobs[idx] = updated
                self._write_all(jobs)
                return updated
        raise KeyError(f"job not found: {job_id}")
