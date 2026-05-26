"""Legacy/internal CLI wrapper for Advisor resume core.

Primary user-facing resume generation should go through
``scripts.generate_tailored_resumes``. This wrapper preserves the older
prepare/validate/build CLI for internal, compatibility, and debug-oriented use.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

if __package__ in {None, ""}:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.resume_core import (
    build_resume_for_job,
    ensure_default_evidence,
    prepare_resume,
    validate_resume,
)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Internal/legacy resume core CLI for deterministic prepare/validate/debug flows. "
            "Primary user-facing generation should go through scripts.generate_tailored_resumes."
        )
    )
    sub = parser.add_subparsers(dest="command")

    build_p = sub.add_parser("build", help="[internal/legacy] build deterministic markdown-oriented run artifacts")
    build_p.add_argument("job_id")
    build_p.add_argument("--advisor-data-dir", default="advisor_data")
    build_p.add_argument("--evidence-path", default=None)

    prep_p = sub.add_parser("prepare", help="[internal/legacy] prepare structured payload for constrained rewrite/debug flows")
    prep_p.add_argument("job_id")
    prep_p.add_argument("--advisor-data-dir", default="advisor_data")
    prep_p.add_argument("--evidence-path", default=None)

    val_p = sub.add_parser("validate", help="[internal/legacy] validate rewritten bullets and write harness/debug outputs")
    val_p.add_argument("job_id")
    val_p.add_argument("--advisor-data-dir", default="advisor_data")
    val_p.add_argument("--evidence-path", default=None)
    val_p.add_argument("--writer-name", default="llm")
    val_p.add_argument("--draft-json", required=True, help="JSON with rewritten bullets [{section, text, evidence_ids, matched_requirements}]")

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
