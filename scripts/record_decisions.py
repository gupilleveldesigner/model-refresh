#!/usr/bin/env python3
"""Record decisions the user gave in chat as <RUN_DIR>/decisions.json.

The user never handles a JSON file. They answer in the chat ("approve 1 and 3,
reject 2") or paste the short text the report's copy button produced, and the
agent turns that message into the packet with this script. Hashes are computed
here from the current report.json, so the packet always matches what was shown.

Findings are named by id or by the #number shown next to the approval buttons.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from validate_decisions import DECISIONS_NAME, VALID_DECISIONS, canonical_hash, diff_hash, validate


def approval_findings(report: dict) -> list[dict]:
    """Approval-required findings in report order; index + 1 is the #number in the HTML."""
    return [
        finding
        for finding in (report.get("phase3", {}).get("findings") or [])
        if isinstance(finding, dict) and finding.get("id") and finding.get("approval_required")
    ]


def resolve(ref: str, findings: list[dict]) -> str:
    ids = [str(finding["id"]) for finding in findings]
    if ref in ids:
        return ref
    number = ref.lstrip("#")
    if number.isdigit() and 1 <= int(number) <= len(ids):
        return ids[int(number) - 1]
    raise ValueError(f"no approval item matches {ref!r}; valid: " + ", ".join(f"#{i} {fid}" for i, fid in enumerate(ids, 1)))


def build(report: dict, picks: dict[str, list[str]], rest: str | None, notes: dict[str, str], source: str) -> tuple[dict, list[str]]:
    findings = approval_findings(report)
    chosen: dict[str, str] = {}
    for decision, refs in picks.items():
        for ref in refs:
            finding_id = resolve(ref, findings)
            if chosen.get(finding_id, decision) != decision:
                raise ValueError(f"conflicting decisions for {finding_id}")
            chosen[finding_id] = decision
    resolved_notes = {resolve(ref, findings): text for ref, text in notes.items()}
    filled = []
    choices = []
    for finding in findings:
        finding_id = str(finding["id"])
        if finding_id not in chosen:
            if rest is None:
                continue
            chosen[finding_id] = rest
            filled.append(finding_id)
        choices.append({
            "finding_id": finding_id,
            "decision": chosen[finding_id],
            "note": resolved_notes.get(finding_id, ""),
            "diff_sha256": diff_hash(finding),
        })
    unresolved = [str(finding["id"]) for finding in findings if str(finding["id"]) not in chosen]
    packet = {
        "schema_version": "1.1",
        "report_id": report.get("report_id"),
        "report_sha256": canonical_hash(report),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "choices": choices,
        "unresolved": unresolved,
        "executable": not unresolved,
    }
    return packet, filled


def write_packet(path: Path, packet: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def parse_notes(pairs: list[str], notes_json: str | None) -> dict[str, str]:
    notes: dict[str, str] = {}
    if notes_json:
        loaded = json.loads(Path(notes_json).expanduser().read_text(encoding="utf-8-sig"))
        if not isinstance(loaded, dict):
            raise ValueError("--notes-json must hold an object of finding -> note")
        notes.update({str(key): str(value) for key, value in loaded.items()})
    for pair in pairs:
        ref, separator, text = pair.partition("=")
        if not separator or not ref:
            raise ValueError(f"--note expects FINDING=TEXT, got {pair!r}")
        notes[ref] = text
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report_json")
    for decision in sorted(VALID_DECISIONS):
        parser.add_argument(f"--{decision}", nargs="*", default=[], metavar="FINDING", help="finding ids or #numbers")
    parser.add_argument("--rest", choices=sorted(VALID_DECISIONS), default="defer",
                        help="decision for every item the user did not mention (default: defer, i.e. left untouched)")
    parser.add_argument("--no-rest", action="store_true", help="leave unmentioned items unresolved instead")
    parser.add_argument("--note", action="append", default=[], metavar="FINDING=TEXT")
    parser.add_argument("--notes-json", help="UTF-8 JSON object of finding -> note, for notes that are awkward on a command line")
    parser.add_argument("--expect-report-sha", metavar="PREFIX",
                        help="hash prefix from a pasted decision text (#abc123...); refuses if the report changed since")
    parser.add_argument("--source", choices=["chat", "clipboard"], default="chat")
    parser.add_argument("--output", help=f"defaults to {DECISIONS_NAME} next to report.json")
    args = parser.parse_args()

    report_path = Path(args.report_json).expanduser().resolve()
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    report_hash = canonical_hash(report)
    expected = (args.expect_report_sha or "").lstrip("#").lower()
    if expected and not report_hash.startswith(expected):
        raise ValueError("the pasted decisions were made on a different version of this report; re-render and ask again")

    picks = {decision: getattr(args, decision) for decision in VALID_DECISIONS}
    packet, filled = build(report, picks, None if args.no_rest else args.rest,
                           parse_notes(args.note, args.notes_json), args.source)
    result = validate(report, packet)
    result["defaulted"] = {"decision": args.rest, "findings": filled} if filled else None
    if result["valid"]:
        output = Path(args.output).expanduser().resolve() if args.output else report_path.with_name(DECISIONS_NAME)
        write_packet(output, packet)
        result["decisions"] = str(output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
