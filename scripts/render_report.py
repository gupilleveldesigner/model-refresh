#!/usr/bin/env python3
"""Render a self-contained Model Refresh HTML report from report.json."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import sys
import webbrowser
from pathlib import Path


WEIGHTS = {
    "context_fitness": 0.25,
    "runtime_hygiene": 0.25,
    "cross_tool_consistency": 0.20,
    "skill_usage_fit": 0.20,
    "eval_freshness": 0.10,
}

GRADES = [
    (0.97, "A+"), (0.93, "A"), (0.90, "A-"),
    (0.87, "B+"), (0.83, "B"), (0.80, "B-"),
    (0.77, "C+"), (0.73, "C"), (0.70, "C-"),
    (0.60, "D"), (0.00, "F"),
]

UI = {
    "ko": {
        "prototype": "셋업 감사 보고서",
        "phase3": "승인",
        "phase5": "최종",
        "baseline": "기준선",
        "inventory": "인벤토리",
        "judgment": "판정",
        "approval": "승인",
        "record": "기록",
        "context": "감사 스냅샷",
        "lanes": "도구 레인",
        "top": "핵심 발견",
        "evidence_first": "근거 우선",
        "details": "상세 판정",
        "surface": "영역",
        "decision": "판정",
        "evidence": "근거",
        "action": "조치",
        "scope": "범위",
        "target": "대상",
        "recovery": "복구",
        "diff": "변경 diff",
        "approve": "승인",
        "reject": "거절",
        "defer": "보류",
        "note": "판단 메모 (선택)",
        "export": "decisions.json 내보내기",
        "share": "개인정보 보호 PNG",
        "approval_queue": "승인 큐",
        "resolved": "결정 완료",
        "unresolved": "미결정",
        "no_findings": "중요 발견 없음",
        "no_findings_body": "현재 감사에서 카드로 승격할 중요 발견이 없습니다.",
        "no_phase5": "Phase 5 결과가 아직 없습니다.",
        "before": "적용 전",
        "after": "적용 후",
        "confidence": "신뢰도",
        "insufficient": "근거 부족",
        "downloaded": "결정 파일을 다운로드했습니다. 현재 채팅에서 이 결정대로 진행한다고 다시 확인해야 적용됩니다.",
        "privacy": "공유 이미지는 경로·프로젝트·구체 명칭·메모·diff를 포함하지 않습니다.",
    },
    "en": {
        "prototype": "setup audit report",
        "phase3": "Approval",
        "phase5": "Final",
        "baseline": "Baseline",
        "inventory": "Inventory",
        "judgment": "Judgment",
        "approval": "Approval",
        "record": "Record",
        "context": "Audit snapshot",
        "lanes": "Tool lanes",
        "top": "Top findings",
        "evidence_first": "Evidence first",
        "details": "Detailed judgments",
        "surface": "Surface",
        "decision": "Judgment",
        "evidence": "Evidence",
        "action": "Action",
        "scope": "Scope",
        "target": "Target",
        "recovery": "Recovery",
        "diff": "Proposed diff",
        "approve": "Approve",
        "reject": "Reject",
        "defer": "Defer",
        "note": "Decision note (optional)",
        "export": "Export decisions.json",
        "share": "Privacy-safe PNG",
        "approval_queue": "Approval queue",
        "resolved": "Resolved",
        "unresolved": "Unresolved",
        "no_findings": "No major findings",
        "no_findings_body": "No finding crossed the threshold for a summary card.",
        "no_phase5": "Phase 5 results are not available yet.",
        "before": "Before",
        "after": "After",
        "confidence": "Confidence",
        "insufficient": "Insufficient evidence",
        "downloaded": "Decision file downloaded. Confirm in the current chat before changes are applied.",
        "privacy": "The share image excludes paths, project names, specific integrations, notes, and diffs.",
    },
}


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def canonical_hash(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def grade_for(score: float | None, coverage: float) -> str:
    if score is None or coverage < 0.60:
        return "—"
    for threshold, grade in GRADES:
        if score >= threshold:
            return grade
    return "F"


def compute_score(scores: dict | None) -> tuple[float | None, float, dict]:
    scores = scores or {}
    total = 0.0
    covered = 0.0
    normalized = {}
    for key, weight in WEIGHTS.items():
        entry = scores.get(key)
        value = entry.get("value") if isinstance(entry, dict) else entry
        if value is None:
            normalized[key] = {"value": None, "confidence": "low", "evidence": ""}
            continue
        value = max(0.0, min(1.0, float(value)))
        total += value * weight
        covered += weight
        normalized[key] = {
            "value": value,
            "confidence": entry.get("confidence", "medium") if isinstance(entry, dict) else "medium",
            "evidence": entry.get("evidence", "") if isinstance(entry, dict) else "",
        }
    return (total / covered if covered else None), covered, normalized


def diff_hash(finding: dict) -> str:
    diff = str(finding.get("diff") or "")
    return hashlib.sha256(diff.encode("utf-8")).hexdigest() if diff else ""


def tone_class(value: str) -> str:
    value = str(value or "").lower()
    if value in {"good", "keep", "pass", "complete", "aligned"}:
        return "good"
    if value in {"bad", "remove", "fail", "blocking", "due"}:
        return "bad"
    return "warn"


def finding_cards(findings: list[dict], t: dict) -> str:
    highlights = sorted(
        [f for f in findings if f.get("highlight")],
        key=lambda f: (int(f.get("priority", 100)), str(f.get("id", ""))),
    )
    if not highlights:
        return (
            '<article class="finding empty"><span class="finding-label">OK</span>'
            f'<h3>{esc(t["no_findings"])}</h3><p>{esc(t["no_findings_body"])}</p></article>'
        )
    cards = []
    for index, finding in enumerate(highlights, 1):
        cards.append(
            f'<a class="finding" href="#finding-{esc(finding.get("id"))}" data-no="{index}">'
            f'<span class="finding-label {tone_class(finding.get("label"))}">{esc(finding.get("label"))}</span>'
            f'<h3>{esc(finding.get("title"))}</h3><p>{esc(finding.get("summary"))}</p></a>'
        )
    return "".join(cards)


def metric_html(metrics: list[dict]) -> str:
    rows = []
    for metric in metrics:
        ratio = max(0.0, min(1.0, float(metric.get("ratio", 0))))
        rows.append(
            '<div class="metric">'
            f'<span>{esc(metric.get("label"))}</span><div class="track"><i class="{tone_class(metric.get("tone"))}" style="width:{ratio*100:.1f}%"></i></div>'
            f'<b>{esc(metric.get("value"))}</b></div>'
        )
    return "".join(rows)


def lanes_html(lanes: list[dict]) -> str:
    return "".join(
        '<div class="lane">'
        f'<span class="tool">{esc(lane.get("name"))}</span>'
        f'<span class="lane-note">{esc(lane.get("summary"))}</span>'
        f'<span class="tag {tone_class(lane.get("tone"))}">{esc(lane.get("status"))}</span></div>'
        for lane in lanes
    )


def findings_html(findings: list[dict], t: dict) -> str:
    rows = []
    for finding in findings:
        fid = str(finding.get("id") or "finding")
        evidence = finding.get("evidence") or []
        evidence_html = "".join(f"<li>{esc(item)}</li>" for item in evidence)
        diff = str(finding.get("diff") or "")
        actual_diff_hash = diff_hash(finding)
        declared = str(finding.get("diff_sha256") or "")
        if declared and actual_diff_hash and declared != actual_diff_hash:
            raise ValueError(f"diff hash mismatch for {fid}")
        approval = ""
        if finding.get("approval_required"):
            approval = (
                f'<div class="approval-box" data-approval="{esc(fid)}" data-diff-hash="{actual_diff_hash}">'
                '<div class="choice-row">'
                f'<button type="button" data-choice="approve">{esc(t["approve"])}</button>'
                f'<button type="button" data-choice="reject">{esc(t["reject"])}</button>'
                f'<button type="button" data-choice="defer">{esc(t["defer"])}</button></div>'
                f'<textarea rows="2" placeholder="{esc(t["note"])}"></textarea></div>'
            )
        diff_block = (
            f'<details><summary>{esc(t["diff"])}</summary><pre class="diff">{esc(diff)}</pre></details>'
            if diff else ""
        )
        rows.append(
            f'<article class="finding-row" id="finding-{esc(fid)}">'
            '<div class="finding-grid">'
            f'<div><span class="category">{esc(finding.get("category"))}</span><h3>{esc(finding.get("title"))}</h3></div>'
            f'<div><span class="judgment {tone_class(finding.get("label"))}">{esc(finding.get("label"))}</span><small>{esc(finding.get("severity"))}</small></div>'
            f'<div class="finding-evidence"><p>{esc(finding.get("summary"))}</p><ul>{evidence_html}</ul></div>'
            f'<div class="finding-action"><b>{esc(finding.get("action"))}</b><small>{esc(finding.get("scope"))}</small></div></div>'
            '<div class="finding-extra">'
            f'<dl><div><dt>{esc(t["target"])}</dt><dd>{esc(finding.get("target"))}</dd></div><div><dt>{esc(t["recovery"])}</dt><dd>{esc(finding.get("recovery"))}</dd></div></dl>'
            f'{diff_block}{approval}</div></article>'
        )
    return "".join(rows)


def phase5_html(phase5: dict | None, findings: list[dict], t: dict) -> str:
    if not phase5:
        return f'<div class="phase5-empty">{esc(t["no_phase5"])}</div>'
    by_id = {str(f.get("id")): f for f in findings}
    rows = []
    for result in phase5.get("results") or []:
        finding = by_id.get(str(result.get("finding_id")), {})
        rows.append(
            '<div class="result-row">'
            f'<b>{esc(finding.get("title") or result.get("finding_id"))}</b>'
            f'<span>{esc(result.get("decision"))}</span>'
            f'<span class="{tone_class(result.get("verification"))}">{esc(result.get("verification"))}</span>'
            f'<p>{esc(result.get("summary"))}</p></div>'
        )
    for name, stage in (phase5.get("stages") or {}).items():
        rows.append(f'<p><b>{esc(name)}</b>: {esc(stage.get("status"))} — {esc(stage.get("reason") or stage.get("evidence"))}</p>')
    remaining = "".join(f"<li>{esc(item)}</li>" for item in phase5.get("remaining") or [])
    return f'<div class="results">{"".join(rows)}<ul>{remaining}</ul></div>'


def render(data: dict, report_hash: str) -> str:
    from validate_report import validate_report
    contract = validate_report(data)
    if not contract["valid"]:
        raise ValueError("; ".join(contract["errors"]))
    for key in ("schema_version", "report_id", "locale", "phase3"):
        if key not in data:
            raise ValueError(f"missing required field: {key}")
    phase3 = data["phase3"]
    phase5 = data.get("phase5")
    findings = phase3.get("findings") or []
    ids = [str(f.get("id")) for f in findings]
    if len(ids) != len(set(ids)) or any(not item for item in ids):
        raise ValueError("finding ids must be present and unique")
    lang = "ko" if str(data.get("locale", "")).lower().startswith("ko") else "en"
    t = UI[lang]
    before_score, before_coverage, before_dimensions = compute_score(phase3.get("scores"))
    after_score, after_coverage, after_dimensions = compute_score((phase5 or {}).get("scores"))
    before_grade = grade_for(before_score, before_coverage)
    after_grade = grade_for(after_score, after_coverage) if phase5 else "—"
    score_payload = {
        "before": before_score,
        "after": after_score,
        "beforeGrade": before_grade,
        "afterGrade": after_grade,
        "beforeCoverage": before_coverage,
        "afterCoverage": after_coverage,
        "beforeDimensions": before_dimensions,
        "afterDimensions": after_dimensions,
    }
    approval_count = sum(1 for f in findings if f.get("approval_required"))
    top_cards = finding_cards(findings, t)
    details = findings_html(findings, t)
    metrics = metric_html(phase3.get("metrics") or [])
    for warning in contract["warnings"]:
        metrics += f"<p>{esc(warning)}</p>"
    review = data.get("model_review") or {}
    if review:
        metrics += "<details><summary>모델 근거 / Model evidence</summary><pre>" + esc(json.dumps(review, ensure_ascii=False, indent=2)) + "</pre></details>"
    lanes = lanes_html(phase3.get("host_lanes") or [])
    final_results = phase5_html(phase5, findings, t)
    safe_data = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    safe_scores = json.dumps(score_payload, ensure_ascii=False).replace("</", "<\\/")
    safe_ui = json.dumps(t, ensure_ascii=False).replace("</", "<\\/")
    title = esc(data.get("title") or "Model Refresh Report")
    target = esc(data.get("target_model") or "current")
    state = esc(phase3.get("status") or "AWAITING_APPROVAL")
    pct = "—" if before_score is None else f"{round(before_score * 100)}%"
    phase5_disabled = "" if phase5 else " disabled"

    template = r'''<!doctype html>
<html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title><style>
:root{--bg:#e9e7df;--ink:#16211b;--green:#0b6845;--lime:#b9e769;--red:#b7472d;--amber:#bd741d;--paper:#f7f5ee;--line:#b7b8ae;--mono:"Cascadia Mono",Consolas,monospace;--display:"Bahnschrift SemiCondensed","Arial Narrow",sans-serif}
*{box-sizing:border-box}html{background:var(--bg);color:var(--ink);font-family:var(--mono);scroll-behavior:smooth}body{margin:0;background:linear-gradient(90deg,transparent 49px,#c9cac0 50px,transparent 51px),linear-gradient(#d9d8d0 1px,transparent 1px);background-size:100% 100%,100% 24px}.wrap{width:min(1260px,calc(100% - 36px));margin:18px auto 70px;border:1px solid var(--ink);background:var(--paper);box-shadow:10px 10px 0 #16211b1c}.mast{display:grid;grid-template-columns:1.2fr .8fr;background:var(--ink);color:#f6f5ed}.mast-main{padding:28px 32px}.kicker{font-size:11px;color:var(--lime);letter-spacing:.18em}.mast h1{font:700 clamp(45px,7vw,92px)/.82 var(--display);letter-spacing:-.04em;text-transform:uppercase;margin:18px 0 14px}.mast p{margin:0;color:#bac5bd;font-size:12px}.mast-side{display:grid;grid-template-rows:1fr auto;border-left:1px solid #68766e}.status{display:flex;align-items:center;justify-content:center;padding:25px}.status div{width:185px;height:185px;border:16px solid var(--lime);border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;transform:rotate(-4deg);text-align:center}.status b{font:700 34px var(--display)}.status span{font-size:9px;margin-top:4px}.switch{display:flex;border-top:1px solid #68766e}.switch button{flex:1;padding:13px;border:0;border-right:1px solid #68766e;background:transparent;color:#aab4ad;font:10px var(--mono);cursor:pointer}.switch button:last-child{border:0}.switch button.active{background:var(--lime);color:var(--ink)}.switch button:disabled{opacity:.4;cursor:not-allowed}
.phase-rail{display:grid;grid-template-columns:repeat(5,1fr);border-bottom:1px solid var(--ink)}.phase{padding:14px 18px;border-right:1px solid var(--line);position:relative}.phase:last-child{border:0}.phase i{display:block;font-style:normal;color:#767d78;font-size:9px}.phase b{display:block;font:600 16px var(--display);margin-top:5px}.phase.done:after,.phase.current:after{content:"";position:absolute;left:0;right:0;bottom:0;height:5px;background:var(--green)}.phase.current:after{background:var(--lime)}.body{padding:30px}.snapshot{display:grid;grid-template-columns:1.05fr .95fr;gap:22px}.panel{border:1px solid var(--ink);background:#fdfbf3}.panel-head{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid var(--ink);background:#dedfd6}.panel-head h2{font:650 18px var(--display);margin:0;text-transform:uppercase}.panel-head span{font-size:9px}.score-box{padding:25px;display:grid;grid-template-columns:180px 1fr;gap:28px;align-items:center}.dial{height:180px;border:1px solid var(--ink);border-radius:50%;display:flex;align-items:center;justify-content:center;position:relative;background:conic-gradient(var(--green) 0 calc(var(--score)*3.6deg),#d5d4cc 0)}.dial:after{content:"";position:absolute;inset:14px;border-radius:50%;background:var(--paper);border:1px solid var(--ink)}.dial div{z-index:1;text-align:center}.dial strong{display:block;font:700 45px var(--display)}.dial small{font-size:9px}.metric-list{display:grid;gap:12px}.metric{display:grid;grid-template-columns:135px 1fr 75px;gap:10px;align-items:center;font-size:10px}.track{height:8px;border:1px solid var(--ink);background:#dad9d0}.track i{display:block;height:100%;background:var(--amber)}.track i.good{background:var(--green)}.track i.bad{background:var(--red)}.lanes{padding:0 20px 20px}.lane{display:grid;grid-template-columns:105px 1fr 100px;gap:12px;padding:13px 0;border-bottom:1px dashed var(--line);align-items:center}.lane:last-child{border:0}.lane .tool{font:700 17px var(--display)}.lane-note{font-family:"Segoe UI",sans-serif;font-size:12px}.tag{justify-self:end;font-size:9px;padding:5px 7px;border:1px solid}.tag.good{background:#d8edc7;color:#174d2b}.tag.warn{background:#f3dfb9;color:#6d4310}.tag.bad{background:#efd0c9;color:#742d20}
.section{margin-top:28px}.section-title{display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid var(--ink);padding-bottom:9px}.section-title h2{font:700 25px var(--display);margin:0;text-transform:uppercase}.section-title span{font-size:9px}.finding-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:14px}.finding{display:block;position:relative;min-height:205px;border:1px solid var(--ink);background:#fdfbf3;padding:22px;color:inherit;text-decoration:none;overflow:hidden}.finding:after{content:attr(data-no);position:absolute;right:-4px;bottom:-28px;font:700 100px var(--display);color:#16211b0b}.finding-label{font-size:9px;color:var(--amber)}.finding-label.good{color:var(--green)}.finding-label.bad{color:var(--red)}.finding h3{font:650 21px var(--display);margin:18px 0 10px}.finding p{font:13px/1.55 "Segoe UI",sans-serif;color:#4f5852;margin:0}.finding.empty{grid-column:1/-1;min-height:120px}.finding-row{border:1px solid var(--ink);border-bottom:0;background:#fdfbf3;scroll-margin-top:20px}.finding-row:last-child{border-bottom:1px solid var(--ink)}.finding-grid{display:grid;grid-template-columns:190px 120px 1fr 190px}.finding-grid>div{padding:14px;border-right:1px solid var(--line)}.finding-grid>div:last-child{border:0}.category{font-size:9px;text-transform:uppercase;color:#6b736d}.finding-grid h3{font:650 17px var(--display);margin:8px 0 0}.judgment{display:block;font-size:10px;color:var(--amber)}.judgment.good{color:var(--green)}.judgment.bad{color:var(--red)}.finding-grid small{display:block;margin-top:8px;color:#747b76}.finding-evidence p,.finding-evidence li,.finding-action{font:12px/1.45 "Segoe UI",sans-serif}.finding-evidence ul{padding-left:18px;margin:8px 0 0}.finding-action b{display:block}.finding-action small{font-family:var(--mono)}.finding-extra{padding:0 14px 14px;border-top:1px dashed var(--line)}dl{display:flex;gap:24px;flex-wrap:wrap}dl div{min-width:220px}dt{font-size:9px;color:#747b76;text-transform:uppercase}dd{margin:5px 0;font:12px "Segoe UI",sans-serif}details{border-top:1px solid var(--line);padding:10px 0}summary{cursor:pointer;font-size:10px}.diff{overflow:auto;max-height:340px;background:#111a15;color:#e4e9e2;padding:14px;font:11px/1.5 var(--mono)}.approval-box{border-top:1px solid var(--line);padding-top:13px}.choice-row{display:flex;gap:7px}.choice-row button{border:1px solid var(--ink);background:transparent;padding:7px 11px;font:10px var(--mono);cursor:pointer}.choice-row button.active{background:var(--lime)}textarea{margin-top:10px;width:100%;resize:vertical;background:#fffef7;border:1px solid var(--line);padding:10px;font:12px "Segoe UI",sans-serif}.action-bar{position:sticky;bottom:0;margin:26px -30px -30px;padding:14px 30px;border-top:1px solid var(--ink);background:#16211bf2;color:#fff;display:flex;gap:12px;align-items:center;z-index:5}.action-bar button{border:1px solid #aebbaf;background:transparent;color:#fff;padding:10px 14px;font:10px var(--mono);cursor:pointer}.action-bar button.primary{background:var(--lime);color:var(--ink);border-color:var(--lime)}.action-bar .counter{margin-left:auto;font-size:10px}.notice{font-size:9px;color:#bdc6bf}.phase5-empty{padding:25px;border:1px solid var(--ink);background:#fdfbf3}.result-row{display:grid;grid-template-columns:1fr 100px 100px 1.5fr;gap:15px;padding:13px;border:1px solid var(--line);border-bottom:0}.result-row:last-of-type{border-bottom:1px solid var(--line)}.result-row p{margin:0;font:12px "Segoe UI",sans-serif}.results>ul{font:12px "Segoe UI",sans-serif}.footer{display:flex;justify-content:space-between;margin-top:28px;font-size:9px;color:#5c645f}.toast{position:fixed;right:20px;bottom:80px;background:var(--ink);color:#fff;padding:12px 15px;font-size:10px;display:none}.toast.show{display:block}
body:not(.final) [data-final-only]{display:none!important}body.final [data-draft-only]{display:none!important}body.final [data-final-only]{display:block!important}body.final .phase.current:after{background:var(--green)}body.final .phase.current{background:#e5f0d8}
@media(max-width:850px){.mast,.snapshot{grid-template-columns:1fr}.mast-side{border-left:0;border-top:1px solid #68766e}.phase-rail{grid-template-columns:1fr}.phase{border-right:0;border-bottom:1px solid var(--line)}.score-box{grid-template-columns:1fr}.dial{width:180px;margin:auto}.finding-grid,.result-row{grid-template-columns:1fr}.finding-grid>div{border-right:0;border-bottom:1px solid var(--line)}.action-bar{flex-wrap:wrap}.action-bar .counter{margin-left:0;width:100%}}
</style></head><body><main class="wrap">
<header class="mast"><div class="mast-main"><span class="kicker">CLAUDE CODE ↔ CODEX / SYSTEM AUDIT</span><h1>MODEL<br>REFRESH</h1><p>__TARGET__ · __REPORT_ID__ · __PROTOTYPE__</p></div><div class="mast-side"><div class="status"><div><b id="grade">__GRADE__</b><span id="score-label">__PCT__ · __STATE__</span></div></div><div class="switch"><button class="active" data-state="draft">__PHASE3__</button><button data-state="final"__PHASE5_DISABLED__>__PHASE5__</button></div></div></header>
<nav class="phase-rail"><div class="phase done"><i>00</i><b>__BASELINE__</b></div><div class="phase done"><i>01</i><b>__INVENTORY__</b></div><div class="phase done"><i>02</i><b>__JUDGMENT__</b></div><div class="phase current"><i>03</i><b>__APPROVAL__</b></div><div class="phase"><i>05</i><b>__RECORD__</b></div></nav>
<div class="body"><section class="snapshot"><article class="panel"><div class="panel-head"><h2>__CONTEXT__</h2><span id="coverage-label">__CONFIDENCE__</span></div><div class="score-box"><div class="dial" id="dial" style="--score:__SCORE_NUMBER__"><div><strong id="dial-grade">__GRADE__</strong><small id="dial-pct">__PCT__</small></div></div><div class="metric-list">__METRICS__</div></div></article><article class="panel"><div class="panel-head"><h2>__LANES_TITLE__</h2><span>ONE CANON / TWO HOSTS</span></div><div class="lanes">__LANES__</div></article></section>
<section class="section"><div class="section-title"><h2>__TOP__</h2><span>__EVIDENCE_FIRST__</span></div><div class="finding-cards">__TOP_CARDS__</div></section>
<section class="section" data-draft-only><div class="section-title"><h2>__DETAILS__</h2><span>__APPROVAL_QUEUE__ · __APPROVAL_COUNT__</span></div><div class="finding-rows">__FINDINGS__</div></section>
<section class="section" data-final-only><div class="section-title"><h2>__PHASE5__</h2><span>__AFTER__</span></div>__PHASE5_RESULTS__</section>
<div class="action-bar" data-draft-only><button class="primary" id="export-decisions">__EXPORT__</button><button id="share-png">__SHARE__</button><span class="notice">__PRIVACY__</span><span class="counter"><b id="resolved-count">0</b>/__APPROVAL_COUNT__ __RESOLVED__ · <b id="unresolved-count">__APPROVAL_COUNT__</b> __UNRESOLVED__</span></div>
<footer class="footer"><span>STATEFUL · REVERSIBLE · EVIDENCE-SEALED</span><span>__REPORT_ID__</span></footer></div></main><div class="toast" id="toast"></div>
<script>const REPORT=__REPORT_JSON__;const SCORES=__SCORES_JSON__;const UI=__UI_JSON__;const REPORT_HASH="__REPORT_HASH__";const STORAGE_KEY=`model-refresh:${REPORT.report_id}:${REPORT_HASH}`;const boxes=[...document.querySelectorAll('[data-approval]')];let decisions={};try{decisions=JSON.parse(localStorage.getItem(STORAGE_KEY)||'{}')}catch(e){decisions={}};
function save(){localStorage.setItem(STORAGE_KEY,JSON.stringify(decisions));renderChoices()}
function renderChoices(){boxes.forEach(box=>{const id=box.dataset.approval;const item=decisions[id]||{};box.querySelectorAll('[data-choice]').forEach(b=>b.classList.toggle('active',b.dataset.choice===item.decision));box.querySelector('textarea').value=item.note||''});const resolved=boxes.filter(b=>decisions[b.dataset.approval]?.decision).length;document.getElementById('resolved-count').textContent=resolved;document.getElementById('unresolved-count').textContent=boxes.length-resolved}
boxes.forEach(box=>{const id=box.dataset.approval;box.querySelectorAll('[data-choice]').forEach(b=>b.onclick=()=>{decisions[id]={...(decisions[id]||{}),decision:b.dataset.choice,diff_sha256:box.dataset.diffHash||''};save()});box.querySelector('textarea').oninput=e=>{decisions[id]={...(decisions[id]||{}),note:e.target.value,diff_sha256:box.dataset.diffHash||''};save()}});renderChoices();
function toast(msg){const el=document.getElementById('toast');el.textContent=msg;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),3200)}
document.getElementById('export-decisions').onclick=()=>{const unresolved=boxes.map(b=>b.dataset.approval).filter(id=>!decisions[id]?.decision);const choices=boxes.filter(b=>decisions[b.dataset.approval]?.decision).map(b=>({finding_id:b.dataset.approval,decision:decisions[b.dataset.approval].decision,note:decisions[b.dataset.approval].note||'',diff_sha256:b.dataset.diffHash||''}));const payload={schema_version:'1.0',report_id:REPORT.report_id,report_sha256:REPORT_HASH,generated_at:new Date().toISOString(),choices,unresolved,executable:unresolved.length===0};const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`model-refresh-decisions-${REPORT.report_id}.json`;a.click();URL.revokeObjectURL(a.href);toast(UI.downloaded)};
function setState(finalState){if(finalState&&!REPORT.phase5)return;document.body.classList.toggle('final',finalState);document.querySelectorAll('[data-state]').forEach(b=>b.classList.toggle('active',(b.dataset.state==='final')===finalState));const score=finalState?SCORES.after:SCORES.before;const grade=finalState?SCORES.afterGrade:SCORES.beforeGrade;document.getElementById('grade').textContent=grade;document.getElementById('dial-grade').textContent=grade;document.getElementById('dial-pct').textContent=score==null?'—':`${Math.round(score*100)}%`;document.getElementById('score-label').textContent=`${score==null?'—':Math.round(score*100)+'%'} · ${finalState?REPORT.phase5.status:REPORT.phase3.status}`;document.getElementById('dial').style.setProperty('--score',score==null?0:score*100)}document.querySelectorAll('[data-state]').forEach(b=>b.onclick=()=>setState(b.dataset.state==='final'));
document.getElementById('share-png').onclick=()=>{const share=REPORT.share||{};const c=document.createElement('canvas');c.width=1200;c.height=675;const x=c.getContext('2d');x.fillStyle='#122019';x.fillRect(0,0,1200,675);x.fillStyle='#b9e769';x.fillRect(0,0,18,675);x.fillStyle='#f7f5ee';x.font='700 70px Bahnschrift, sans-serif';x.fillText(share.title||'MODEL REFRESH',70,110);x.font='24px Cascadia Mono, monospace';x.fillStyle='#aeb9b1';x.fillText(share.subtitle||'PRIVACY-SAFE LOCAL AUDIT',72,150);x.strokeStyle='#758079';x.strokeRect(72,205,230,230);x.font='700 100px Bahnschrift, sans-serif';x.fillStyle='#b9e769';x.textAlign='center';x.fillText(SCORES.beforeGrade,187,350);x.font='18px Cascadia Mono, monospace';x.fillStyle='#f7f5ee';x.fillText(SCORES.before==null?'—':Math.round(SCORES.before*100)+'%',187,395);x.textAlign='left';const items=(share.findings||[]).slice(0,4);x.font='700 25px Bahnschrift, sans-serif';x.fillStyle='#f7f5ee';items.forEach((item,i)=>{x.fillText(`${i+1}. ${item}`,360,235+i*75)});x.font='16px Cascadia Mono, monospace';x.fillStyle='#87938b';x.fillText(UI.privacy,72,620);const a=document.createElement('a');a.href=c.toDataURL('image/png');a.download=`model-refresh-share-${REPORT.report_id}.png`;a.click()};
</script></body></html>'''
    replacements = {
        "__LANG__": lang, "__TITLE__": title, "__TARGET__": target,
        "__REPORT_ID__": esc(data["report_id"]), "__PROTOTYPE__": esc(t["prototype"]),
        "__GRADE__": esc(before_grade), "__PCT__": esc(pct), "__STATE__": state,
        "__PHASE3__": esc(t["phase3"]), "__PHASE5__": esc(t["phase5"]),
        "__PHASE5_DISABLED__": phase5_disabled, "__BASELINE__": esc(t["baseline"]),
        "__INVENTORY__": esc(t["inventory"]), "__JUDGMENT__": esc(t["judgment"]),
        "__APPROVAL__": esc(t["approval"]), "__RECORD__": esc(t["record"]),
        "__CONTEXT__": esc(t["context"]), "__CONFIDENCE__": esc(t["confidence"]),
        "__SCORE_NUMBER__": "0" if before_score is None else f"{before_score*100:.1f}",
        "__METRICS__": metrics, "__LANES_TITLE__": esc(t["lanes"]), "__LANES__": lanes,
        "__TOP__": esc(t["top"]), "__EVIDENCE_FIRST__": esc(t["evidence_first"]),
        "__TOP_CARDS__": top_cards, "__DETAILS__": esc(t["details"]),
        "__APPROVAL_QUEUE__": esc(t["approval_queue"]), "__APPROVAL_COUNT__": str(approval_count),
        "__FINDINGS__": details, "__AFTER__": esc(t["after"]), "__PHASE5_RESULTS__": final_results,
        "__EXPORT__": esc(t["export"]), "__SHARE__": esc(t["share"]),
        "__PRIVACY__": esc(t["privacy"]), "__RESOLVED__": esc(t["resolved"]),
        "__UNRESOLVED__": esc(t["unresolved"]), "__REPORT_JSON__": safe_data,
        "__SCORES_JSON__": safe_scores, "__UI_JSON__": safe_ui, "__REPORT_HASH__": report_hash,
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report_json")
    parser.add_argument("--output")
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    report_path = Path(args.report_json).expanduser().resolve()
    raw = report_path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    report_hash = canonical_hash(data)
    output = Path(args.output).expanduser().resolve() if args.output else report_path.with_suffix(".html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(data, report_hash), encoding="utf-8")
    print(json.dumps({"report": str(output), "report_id": data.get("report_id"), "sha256": report_hash}, ensure_ascii=False))
    if args.open:
        webbrowser.open(output.as_uri())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
