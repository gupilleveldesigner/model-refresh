#!/usr/bin/env python3
"""Check report evidence structure; never attest model behavior or authorization."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

AXES = {"reasoning", "context_compaction", "autonomy", "instruction_priority",
        "writing", "delegation", "verification", "capabilities"}
STAGES = {"audit", "application", "behavior", "effect"}


def validate_report(report: dict) -> dict:
    errors, warnings = [], []
    if not isinstance(report, dict):
        return {"valid": False, "errors": ["report must be an object"], "warnings": []}
    version = report.get("schema_version")
    if version == "1.0":
        warnings.append("Legacy report: model evidence/stage contract not checked; not proof of refresh completion.")
        return {"valid": True, "errors": [], "warnings": warnings}
    if version != "1.1":
        errors.append("schema_version must be 1.1 (1.0 is historical compatibility only)")
    if report.get("mode") not in {"migration", "setup"}:
        errors.append("mode must be migration or setup")
    phase3 = report.get("phase3")
    if not isinstance(phase3, dict) or not isinstance(phase3.get("findings"), list):
        errors.append("phase3.findings must be a list")
        phase3 = {"findings": []}
    findings = phase3["findings"]
    required = phase3.get("required_stages")
    if not isinstance(required, list) or "audit" not in required or any(not isinstance(s, str) or s not in STAGES for s in required):
        errors.append("phase3.required_stages must include audit and valid stage names")
        required = []
    ids = [f.get("id") for f in findings if isinstance(f, dict)]
    if len(ids) != len(findings) or any(not isinstance(i, str) or not i for i in ids) or len(set(str(i) for i in ids)) != len(ids):
        errors.append("finding ids must be nonempty unique strings")
    if report.get("mode") == "migration":
        target = report.get("target_model")
        if not isinstance(target, str) or target.strip().lower() in {"", "current", "latest"}:
            errors.append("migration requires a resolved target_model")
        review = report.get("model_review") or {}
        if not isinstance(review, dict):
            review = {}
        sources = review.get("sources") or []
        source_ids = set()
        target_source_found = False
        for source in sources if isinstance(sources, list) else []:
            if not isinstance(source, dict):
                errors.append("source must be an object")
                continue
            sid = source.get("id")
            if not isinstance(sid, str) or not sid or sid in source_ids:
                errors.append("source id missing or duplicated")
                continue
            source_ids.add(sid)
            target_source_found |= source.get("model") == target
            for field in ("model", "host", "section", "takeaway"):
                if not isinstance(source.get(field), str) or not source[field].strip():
                    errors.append(f"source {sid}: missing {field}")
            url = urlparse(str(source.get("url", "")))
            if url.scheme != "https" or not url.hostname:
                errors.append(f"source {sid}: HTTPS source URL required")
            try:
                date.fromisoformat(str(source.get("checked_at", "")))
            except ValueError:
                errors.append(f"source {sid}: checked_at must be YYYY-MM-DD")
        if not source_ids:
            errors.append("migration requires sources")
        if not target_source_found:
            errors.append("migration requires a source for the target model")
        axes = review.get("axes") or []
        seen = set()
        for row in axes if isinstance(axes, list) else []:
            if not isinstance(row, dict):
                errors.append("axis must be an object")
                continue
            axis = str(row.get("axis", ""))
            if axis in seen:
                errors.append(f"duplicate axis: {axis}")
            seen.add(axis)
            for field in ("current", "reason"):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    errors.append(f"axis {axis}: missing {field}")
            if row.get("decision") not in {"modify", "keep", "not_applicable", "unverified"}:
                errors.append(f"axis {axis}: invalid decision")
            refs = row.get("source_ids")
            if not isinstance(refs, list) or not refs or any(not isinstance(s, str) or s not in source_ids for s in refs):
                errors.append(f"axis {axis}: valid source_ids required")
        for axis in sorted(AXES - seen):
            errors.append(f"missing model axis: {axis}")
    phase5 = report.get("phase5")
    if phase5 is not None:
        if not isinstance(phase5, dict):
            errors.append("phase5 must be an object")
        else:
            if phase5.get("status") not in {"COMPLETE", "PARTIAL", "NO_CHANGES"}:
                errors.append("invalid phase5 status")
            stages = phase5.get("stages") or {}
            if not isinstance(stages, dict):
                stages = {}
            for name in sorted(STAGES):
                stage = stages.get(name) or {}
                if not isinstance(stage, dict):
                    stage = {}
                status = stage.get("status")
                if status not in {"pass", "fail", "unverified", "not_applicable"}:
                    errors.append(f"stage {name}: invalid status")
                if status == "pass" and not stage.get("evidence"):
                    errors.append(f"stage {name}: pass requires evidence")
                if status != "pass" and not stage.get("reason"):
                    errors.append(f"stage {name}: reason required")
            results = phase5.get("results") or []
            if not isinstance(results, list):
                errors.append("phase5.results must be a list")
                results = []
            result_ids = [r.get("finding_id") for r in results if isinstance(r, dict)]
            if len(result_ids) != len(results) or len(set(str(i) for i in result_ids)) != len(result_ids):
                errors.append("result ids must be unique")
            approved = []
            for r in results:
                if not isinstance(r, dict):
                    errors.append("result must be an object")
                    continue
                if r.get("finding_id") not in ids:
                    errors.append("result references unknown finding")
                if r.get("decision") not in {"approve", "reject", "defer"}:
                    errors.append("invalid result decision")
                if r.get("applied") and r.get("decision") != "approve":
                    errors.append("unapproved result cannot be applied")
                if r.get("decision") == "approve":
                    approved.append(r)
            if phase5.get("status") in {"COMPLETE", "NO_CHANGES"}:
                for f in findings:
                    if isinstance(f, dict) and f.get("approval_required") and f.get("id") not in result_ids:
                        errors.append("final report missing decision result")
                for name in required:
                    stage = stages.get(name)
                    if not isinstance(stage, dict) or stage.get("status") != "pass":
                        errors.append(f"completion requires stage {name} pass")
                if any(not r.get("applied") for r in approved):
                    errors.append("approved work remains unapplied")
                application = stages.get("application")
                if approved and (not isinstance(application, dict) or application.get("status") != "pass"):
                    errors.append("applied work requires application pass")
            if phase5.get("status") == "NO_CHANGES" and any(r.get("applied") for r in results if isinstance(r, dict)):
                errors.append("NO_CHANGES contradicts applied results")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report_json")
    args = parser.parse_args()
    result = validate_report(json.loads(Path(args.report_json).read_text(encoding="utf-8-sig")))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["valid"] else 1)
