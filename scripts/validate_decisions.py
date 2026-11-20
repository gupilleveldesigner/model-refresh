#!/usr/bin/env python3
"""Validate a recorded Model Refresh decisions.json against report.json.

The packet is written by review_server.py (browser submit) or record_decisions.py
(chat or pasted decisions); nobody downloads or uploads it by hand.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


from validate_report import validate_report


VALID_DECISIONS = {"approve", "reject", "defer"}
VALID_SOURCES = {"review_server", "clipboard", "chat"}
DECISIONS_NAME = "decisions.json"


def canonical_hash(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def diff_hash(finding: dict) -> str:
    diff = str(finding.get("diff") or "")
    return hashlib.sha256(diff.encode("utf-8")).hexdigest() if diff else ""


def validate(report: dict, decisions: dict) -> dict:
    contract = validate_report(report)
    errors = list(contract["errors"])
    source = decisions.get("source")
    if source is not None and source not in VALID_SOURCES:
        errors.append(f"invalid decision source: {source}")
    if decisions.get("report_id") != report.get("report_id"):
        errors.append("report_id mismatch")
    expected_report_hash = canonical_hash(report)
    if decisions.get("report_sha256") != expected_report_hash:
        errors.append("report_sha256 mismatch")

    findings = {
        str(item.get("id")): item
        for item in (report.get("phase3", {}).get("findings") or [])
        if item.get("id")
    }
    approval_ids = {
        finding_id
        for finding_id, finding in findings.items()
        if finding.get("approval_required")
    }
    choices = decisions.get("choices") or []
    choice_ids = []
    approved = []
    rejected = []
    deferred = []
    for choice in choices:
        finding_id = str(choice.get("finding_id") or "")
        choice_ids.append(finding_id)
        if finding_id not in approval_ids:
            errors.append(f"unknown or non-approvable finding: {finding_id}")
            continue
        decision = choice.get("decision")
        if decision not in VALID_DECISIONS:
            errors.append(f"invalid decision for {finding_id}: {decision}")
        expected_diff_hash = diff_hash(findings[finding_id])
        if str(choice.get("diff_sha256") or "") != expected_diff_hash:
            errors.append(f"diff_sha256 mismatch for {finding_id}")
        if decision == "approve":
            approved.append(finding_id)
        elif decision == "reject":
            rejected.append(finding_id)
        elif decision == "defer":
            deferred.append(finding_id)

    if len(choice_ids) != len(set(choice_ids)):
        errors.append("duplicate finding choices")
    missing = sorted(approval_ids - set(choice_ids))
    unresolved_declared = sorted(str(item) for item in (decisions.get("unresolved") or []))
    if unresolved_declared != missing:
        errors.append("unresolved list does not match missing choices")
    executable = not errors and not missing
    if bool(decisions.get("executable")) != executable:
        errors.append("executable flag is inconsistent")
        executable = False

    return {
        "valid": not errors,
        "executable": executable,
        "report_id": report.get("report_id"),
        "report_sha256": expected_report_hash,
        "source": source,
        "approved": approved,
        "rejected": rejected,
        "deferred": deferred,
        "unresolved": missing,
        "errors": errors,
        "warnings": contract["warnings"],
        "authorization": "records a human choice made in the review page or the chat; a packet that reached the run directory any other way authorizes nothing",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report_json")
    parser.add_argument("decisions_json", nargs="?", help="defaults to decisions.json next to report.json")
    args = parser.parse_args()
    report_path = Path(args.report_json).expanduser()
    decisions_path = Path(args.decisions_json).expanduser() if args.decisions_json else report_path.with_name(DECISIONS_NAME)
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    decisions = json.loads(decisions_path.read_text(encoding="utf-8-sig"))
    result = validate(report, decisions)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
