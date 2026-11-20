#!/usr/bin/env python3
"""Check a finished run against its own records and print the completion report.

The completion message in chat is where a refresh most easily overstates itself:
"done" for something that was applied but never observed, a count that drifted
from the record, a rejected item reported as handled. This script derives the
message from report.json instead of from memory, and refuses to produce one when
the record contradicts the user's recorded decisions, the Phase 3 proposal, or
the files on disk.

Exit code 0 = the printed report may be relayed as is. 1 = the record is not
reportable yet; fix what the errors name and run again.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import webbrowser
from pathlib import Path

from record_decisions import approval_findings
from render_report import canonical_hash, compute_score, grade_for, load_saved, render
from validate_decisions import DECISIONS_NAME, validate
from validate_report import STAGES, validate_report

STAGE_ORDER = ("audit", "application", "behavior", "effect")

TEXT = {
    "ko": {
        "title": "model-refresh 완료 보고",
        "status": {"COMPLETE": "완료", "PARTIAL": "부분 완료", "NO_CHANGES": "변경 없음"},
        "decisions": "결정", "approved": "승인", "rejected": "거절", "deferred": "보류",
        "applied": "적용", "of_approved": "승인 {n}건 중 {k}건 적용",
        "verified": "확인", "runtime": "런타임 확인", "config": "설정·파일 확인", "unverified": "미확인", "failed": "실패",
        "items": "항목별 결과", "not_applied": "미적용", "untouched": "건드리지 않음",
        "stages": "단계", "stage": {"audit": "감사", "application": "적용", "behavior": "동작", "effect": "효과"},
        "stage_status": {"pass": "통과", "fail": "실패", "unverified": "미검증", "not_applicable": "해당 없음"},
        "required": "필수", "not_claimed": "이번 실행이 입증하지 않은 것",
        "no_behavior": "변경 후 런타임 동작은 확인하지 않았습니다.",
        "config_only": "{n}건은 설정·파일 상태만 확인했고, 새 세션에서 실제로 반영되는지는 보지 않았습니다.",
        "no_effect": "비용·속도·품질 개선은 측정하지 않았습니다.",
        "manual": "직접 처리할 일", "restart": "새 세션이 필요한 변경", "remaining": "남은 항목",
        "backups": "백업", "score": "셋업 건강도", "report": "보고서", "explained": "디스크 대조 메모",
        "blocked": "완료 보고를 만들 수 없습니다. 아래를 바로잡은 뒤 다시 실행하세요.",
    },
    "en": {
        "title": "model-refresh completion report",
        "status": {"COMPLETE": "complete", "PARTIAL": "partially complete", "NO_CHANGES": "no changes"},
        "decisions": "Decisions", "approved": "approved", "rejected": "rejected", "deferred": "deferred",
        "applied": "Applied", "of_approved": "{k} of {n} approved items applied",
        "verified": "Verified", "runtime": "observed at runtime", "config": "config/file state only", "unverified": "unverified", "failed": "failed",
        "items": "Per item", "not_applied": "not applied", "untouched": "left untouched",
        "stages": "Stages", "stage": {"audit": "audit", "application": "application", "behavior": "behavior", "effect": "effect"},
        "stage_status": {"pass": "pass", "fail": "fail", "unverified": "unverified", "not_applicable": "n/a"},
        "required": "required", "not_claimed": "What this run does not establish",
        "no_behavior": "Runtime behavior after the change was not observed.",
        "config_only": "{n} item(s) were checked in config/file state only, not in a fresh session.",
        "no_effect": "Cost, speed and quality effects were not measured.",
        "manual": "Left for you to do", "restart": "Changes that need a new session", "remaining": "Remaining",
        "backups": "Backups", "score": "Setup health", "report": "Report", "explained": "Disk check notes",
        "blocked": "No completion report can be produced yet. Fix the following and run again.",
    },
}


def phase3_hashes(report: dict) -> set[str]:
    """Hashes report.json could have had when the user decided (phase5 absent or null)."""
    absent = copy.deepcopy(report)
    absent.pop("phase5", None)
    return {canonical_hash(absent), canonical_hash({**absent, "phase5": None})}


def check_decisions(report: dict, decisions: dict | None, errors: list[str]) -> dict[str, str]:
    """The final record may not disagree with what the user actually decided."""
    needed = [str(finding["id"]) for finding in approval_findings(report)]
    results = {str(r.get("finding_id")): r for r in (report.get("phase5") or {}).get("results") or [] if isinstance(r, dict)}
    if decisions is None:
        if needed:
            errors.append(f"{DECISIONS_NAME} is missing: there is no record of the user's decisions for this run")
        return {}
    if decisions.get("report_sha256") not in phase3_hashes(report):
        errors.append("the Phase 3 proposal changed after the user decided; the decisions no longer match this report")
    proposal = copy.deepcopy(report)
    proposal.pop("phase5", None)
    structural = validate(proposal, {**decisions, "report_sha256": canonical_hash(proposal)})
    errors.extend(f"{DECISIONS_NAME}: {error}" for error in structural["errors"])
    recorded = {str(c.get("finding_id")): str(c.get("decision")) for c in decisions.get("choices") or [] if isinstance(c, dict)}
    for finding_id in needed:
        decision = recorded.get(finding_id)
        result = results.get(finding_id)
        if decision is None:
            if result is not None and result.get("decision") == "approve":
                errors.append(f"{finding_id}: reported as approved but the user never decided it")
            continue
        if result is None:
            errors.append(f"{finding_id}: the user chose {decision} but phase5.results has no entry for it")
        elif result.get("decision") != decision:
            errors.append(f"{finding_id}: phase5 says {result.get('decision')} but the user chose {decision}")
    return recorded


def diff_targets(diff: str) -> dict[Path, dict[str, list[str]]]:
    """Added/removed lines per target file, for diffs whose paths can be resolved."""
    targets: dict[Path, dict[str, list[str]]] = {}
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            raw = line[4:].split("\t")[0].strip()
            if raw.startswith(("a/", "b/")) and not Path(raw).expanduser().is_absolute():
                raw = raw[2:]
            path = Path(raw).expanduser()
            current = targets.setdefault(path, {"added": [], "removed": []}) if path.is_absolute() else None
        elif line.startswith("--- "):
            continue
        elif current is not None and line[:1] in "+-" and len(line.strip()) > 3:
            current["added" if line[0] == "+" else "removed"].append(line[1:].strip())
    return targets


def check_disk(finding: dict, result: dict, errors: list[str], notes: list[str]) -> None:
    """An item recorded as applied must be visible in the file its diff names."""
    finding_id = finding.get("id")
    explained = str(result.get("disk_check_note") or "").strip()
    for path, lines in diff_targets(str(finding.get("diff") or "")).items():
        try:
            present = {line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines()}
        except (OSError, UnicodeDecodeError):
            problem = f"{finding_id}: recorded as applied, but {path} could not be read"
        else:
            missing = [line for line in lines["added"] if line and line not in present]
            # A removed line may legitimately survive elsewhere in the file, so only the
            # case where every removed line is still there counts as "nothing was removed".
            removed = [line for line in lines["removed"] if line and line not in lines["added"]]
            if missing:
                problem = f"{finding_id}: recorded as applied, but {path} lacks {len(missing)} added line(s), e.g. {missing[0][:80]!r}"
            elif removed and all(line in present for line in removed):
                problem = f"{finding_id}: recorded as applied, but {path} still holds all {len(removed)} removed line(s), e.g. {removed[0][:80]!r}"
            else:
                continue
        if explained:
            notes.append(f"{problem} — {explained}")
        else:
            errors.append(problem + " (re-check the file; if the change landed in another form, say how in disk_check_note)")


def as_list(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(item) for item in value or [] if str(item).strip()]


def summarize(report: dict, recorded: dict[str, str], notes: list[str], html_path: Path) -> str:
    lang = "ko" if str(report.get("locale", "")).lower().startswith("ko") else "en"
    t = TEXT[lang]
    phase3, phase5 = report["phase3"], report["phase5"]
    findings = {str(f.get("id")): f for f in phase3.get("findings") or [] if isinstance(f, dict)}
    numbers = {str(f["id"]): index for index, f in enumerate(approval_findings(report), 1)}
    results = [r for r in phase5.get("results") or [] if isinstance(r, dict)]
    approved = [r for r in results if r.get("decision") == "approve"]
    applied = [r for r in approved if r.get("applied")]
    count = lambda decision: sum(1 for r in results if r.get("decision") == decision)
    passed = [r for r in applied if r.get("verification") == "PASS"]
    runtime = [r for r in passed if r.get("verification_level") == "runtime"]
    config_only = [r for r in passed if r.get("verification_level") != "runtime"]
    unverified = [r for r in applied if r.get("verification") not in {"PASS", "FAIL"}]
    failed = [r for r in applied if r.get("verification") == "FAIL"]
    stages = phase5.get("stages") or {}
    required = set(phase3.get("required_stages") or [])

    out = [f"## {t['title']} — {t['status'].get(phase5.get('status'), phase5.get('status'))}", ""]
    out.append(f"- {t['decisions']}: {t['approved']} {count('approve')} · {t['rejected']} {count('reject')} · {t['deferred']} {count('defer')}")
    out.append(f"- {t['applied']}: " + t["of_approved"].format(n=len(approved), k=len(applied)))
    if applied:
        out.append(f"- {t['verified']}: {t['runtime']} {len(runtime)} · {t['config']} {len(config_only)} · {t['unverified']} {len(unverified)} · {t['failed']} {len(failed)}")

    if results:
        out += ["", f"### {t['items']}"]
        for result in sorted(results, key=lambda r: numbers.get(str(r.get("finding_id")), 10**6)):
            finding_id = str(result.get("finding_id"))
            title = findings.get(finding_id, {}).get("title") or finding_id
            decision = result.get("decision")
            if decision != "approve":
                state = f"{t['rejected' if decision == 'reject' else 'deferred']} · {t['untouched']}"
            elif not result.get("applied"):
                state = f"{t['approved']} · {t['not_applied']}"
            else:
                verification = result.get("verification")
                level = t["runtime"] if result.get("verification_level") == "runtime" else t["config"]
                how = level if verification == "PASS" else t["failed"] if verification == "FAIL" else t["unverified"]
                state = f"{t['approved']} · {t['applied']} · {how}"
            line = f"- #{numbers[finding_id]} " if finding_id in numbers else "- "
            line += f"{title} — {state}"
            if result.get("summary"):
                line += f". {result['summary']}"
            out.append(line)

    out += ["", f"### {t['stages']}"]
    for name in STAGE_ORDER:
        stage = stages.get(name) if isinstance(stages.get(name), dict) else {}
        status = stage.get("status")
        detail = "; ".join(as_list(stage.get("evidence"))) if status == "pass" else str(stage.get("reason") or "")
        mark = f" ({t['required']})" if name in required else ""
        out.append(f"- {t['stage'][name]}{mark}: {t['stage_status'].get(status, status)}" + (f" — {detail}" if detail else ""))

    limits = []
    behavior = (stages.get("behavior") or {}).get("status")
    if applied and behavior != "pass":
        limits.append(t["no_behavior"] if not runtime else t["config_only"].format(n=len(config_only)) if config_only else "")
    elif config_only:
        limits.append(t["config_only"].format(n=len(config_only)))
    if (stages.get("effect") or {}).get("status") != "pass":
        limits.append(t["no_effect"])
    limits = [line for line in limits if line]
    if limits:
        out += ["", f"### {t['not_claimed']}"] + [f"- {line}" for line in limits]

    sections = (
        ("manual", [f"{findings.get(str(r.get('finding_id')), {}).get('title') or r.get('finding_id')}: {r['manual_action']}"
                    for r in results if str(r.get("manual_action") or "").strip()]),
        ("restart", as_list(phase5.get("requires_new_session"))),
        ("remaining", as_list(phase5.get("remaining"))),
        ("backups", sorted({str(r["backup"]) for r in applied if str(r.get("backup") or "").strip()})),
        ("explained", notes),
    )
    for key, lines in sections:
        if lines:
            out += ["", f"### {t[key]}"] + [f"- {line}" for line in lines]

    before, before_coverage, _ = compute_score(phase3.get("scores"))
    after, after_coverage, _ = compute_score(phase5.get("scores"))
    if before is not None and after is not None:
        out += ["", f"{t['score']}: {grade_for(before, before_coverage)} {round(before * 100)}% → {grade_for(after, after_coverage)} {round(after * 100)}%"]
    out += ["", f"{t['report']}: {html_path}"]
    return "\n".join(out)


def finalize(report_path: Path) -> tuple[list[str], str]:
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    errors: list[str] = []
    notes: list[str] = []
    phase5 = report.get("phase5")
    if not isinstance(phase5, dict):
        return ["phase5 is missing: record the outcome in report.json before reporting completion"], ""
    contract = validate_report(report)
    errors.extend(contract["errors"])
    if report.get("schema_version") == "1.0":
        errors.append("a 1.0 record carries no stage or evidence contract; it cannot back a completion report")
    stages = phase5.get("stages") if isinstance(phase5.get("stages"), dict) else {}
    errors.extend(f"stage {name} is not recorded" for name in sorted(STAGES - set(stages)) if not contract["errors"])

    decisions_path = report_path.with_name(DECISIONS_NAME)
    decisions = None
    if decisions_path.is_file():
        try:
            decisions = json.loads(decisions_path.read_text(encoding="utf-8-sig"))
        except ValueError:
            errors.append(f"{DECISIONS_NAME} is not valid JSON")
        if decisions is not None and not isinstance(decisions, dict):
            errors.append(f"{DECISIONS_NAME} must be an object")
            decisions = None
    recorded = check_decisions(report, decisions, errors)

    findings = {str(f.get("id")): f for f in (report.get("phase3") or {}).get("findings") or [] if isinstance(f, dict)}
    for result in phase5.get("results") or []:
        if isinstance(result, dict) and result.get("decision") == "approve" and result.get("applied"):
            finding = findings.get(str(result.get("finding_id")))
            if finding:
                check_disk(finding, result, errors, notes)
    if errors:
        return errors, ""
    return [], summarize(report, recorded, notes, report_path.with_suffix(".html"))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("report_json")
    parser.add_argument("--open", action="store_true", help="open the final report.html in the browser")
    args = parser.parse_args()
    report_path = Path(args.report_json).expanduser().resolve()
    errors, summary = finalize(report_path)
    if errors:
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
        lang = "ko" if str(report.get("locale", "")).lower().startswith("ko") else "en"
        print(TEXT[lang]["blocked"], file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    html_path = report_path.with_suffix(".html")
    html_path.write_text(render(report, canonical_hash(report), load_saved_for_final(report_path, report)), encoding="utf-8")
    print(summary)
    if args.open:
        webbrowser.open(html_path.as_uri())
    return 0


def load_saved_for_final(report_path: Path, report: dict) -> dict:
    """decisions.json was hashed against the Phase 3 proposal, so load it against that."""
    proposal = copy.deepcopy(report)
    proposal.pop("phase5", None)
    for candidate in (proposal, {**proposal, "phase5": None}):
        saved = load_saved(report_path, candidate)
        if saved:
            return saved
    return {}


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
