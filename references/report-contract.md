# Model Refresh HTML 보고서 계약

이 계약은 Phase 3 감사 결과를 검토 가능한 단일 HTML로 만들고, Phase 5 적용 결과를 같은 보고서에 보존한다. 보고서는 로컬 전용이며 외부 서비스나 런타임 서버에 의존하지 않는다.

## 산출물과 생명주기

감사마다 스킬 폴더 밖의 고유 실행 디렉터리를 만든다.

```text
<AUDIT_ROOT>/runs/<run-id>/
├─ report.json
├─ report.html
└─ evidence/...
```

- Phase 3: `report.json.phase3`를 채우고 `report.html`을 생성한다. 상태는 `AWAITING_APPROVAL`이다.
- 사용자는 HTML에서 항목별 승인·거절·보류와 메모를 고르고 `decisions.json`을 다운로드한다.
- `decisions.json`은 선택 내용의 정본이지만 실행 권한 자체는 아니다. Phase 4 직전에 사용자가 현재 채팅에서 “보고서 결정대로 진행”처럼 다시 확인해야 한다.
- Phase 5: 같은 `report.json`에 `phase5`를 추가하고 같은 `report.html`을 다시 생성한다. Phase 3 제안은 변경하지 않는다.
- 변경이 없거나 전부 거절되면 `phase5.status: NO_CHANGES`로 확정한다.

보고서 생성 언어는 사용자 현재 대화 언어다. 한 실행은 한 언어의 HTML만 만든다. 사용자가 언어를 명시하면 그 언어가 우선하며, `locale`에 기록한다.

## 점수

높을수록 현재 모델에 잘 맞고 건강한 셋업이다. 각 값은 `0.0`~`1.0`이다.

이 점수와 문자 등급의 대상은 `model-refresh`가 감사한 **전체 셋업**이다. 개별 스킬, 스킬 사용 구간, 대화 세션에 점수나 문자 등급을 매기지 않는다. `skill_usage_fit`도 특정 스킬들의 평균 성적이 아니라, 후보 스킬을 실사용 증거로 적절히 보존·축소·통합·수정했는지를 나타내는 셋업 수준 지표다.

| 축 | 키 | 비중 |
|---|---|---:|
| 컨텍스트 적합성 | `context_fitness` | 0.25 |
| 런타임 위생 | `runtime_hygiene` | 0.25 |
| 도구 간 정합성 | `cross_tool_consistency` | 0.20 |
| 스킬 실사용 적합성 | `skill_usage_fit` | 0.20 |
| 완료 검사 신선도 | `eval_freshness` | 0.10 |

점수에는 `confidence: high|medium|low`와 근거를 남긴다. 근거가 부족한 축을 임의의 중간값으로 채우지 말고 `null`로 두며, 종합 점수는 확인된 축의 비중을 재정규화해 계산한다. 확인된 비중이 0.6 미만이면 문자 등급을 표시하지 않고 `INSUFFICIENT EVIDENCE`로 표시한다.

문자 등급은 원본 Agent Skill Report 기준을 사용한다.

```text
A+ ≥ .97, A ≥ .93, A- ≥ .90
B+ ≥ .87, B ≥ .83, B- ≥ .80
C+ ≥ .77, C ≥ .73, C- ≥ .70
D ≥ .60, 그 아래 F
```

Phase 5에는 적용 전과 적용 후 점수를 함께 표시한다. 점수 상승을 완료 조건으로 강제하지 않는다. 필요한 보존이나 안전 조치 때문에 점수가 같아도 성공일 수 있다.

## 최소 report.json

```json
{
  "schema_version": "1.0",
  "report_id": "model-refresh-20260830-190000",
  "generated_at": "2026-08-30T19:00:00+09:00",
  "locale": "ko-KR",
  "title": "Model Refresh Report",
  "target_model": "current",
  "hosts": ["claude", "codex"],
  "phase3": {
    "status": "AWAITING_APPROVAL",
    "summary": "현재 셋업은 적정하지만 완료 검사 3건이 만료 후보입니다.",
    "scores": {
      "context_fitness": {"value": 0.96, "confidence": "high", "evidence": "실측 /context"},
      "runtime_hygiene": {"value": 0.88, "confidence": "medium", "evidence": "훅·MCP 실물 확인"},
      "cross_tool_consistency": {"value": 0.92, "confidence": "high", "evidence": "정션·해시 비교"},
      "skill_usage_fit": {"value": 0.82, "confidence": "medium", "evidence": "후보 사용 구간 확인"},
      "eval_freshness": {"value": 0.60, "confidence": "high", "evidence": "3건 뮤테이션 미실행"}
    },
    "metrics": [
      {"label": "Resident context", "value": "41.4K / 1M", "ratio": 0.04, "tone": "good"}
    ],
    "host_lanes": [
      {"name": "CLAUDE", "summary": "훅·플러그인·커넥터", "status": "2 DECISIONS", "tone": "warn"}
    ],
    "findings": []
  },
  "phase5": null,
  "share": {
    "title": "Model Refresh",
    "subtitle": "Local setup audit",
    "findings": ["Context is lean", "Three evaluations are due"]
  }
}
```

## finding 계약

```json
{
  "id": "connector-gmail",
  "label": "DECIDE",
  "category": "Connectors",
  "severity": "major",
  "priority": 20,
  "highlight": true,
  "title": "커넥터 이름 불일치를 실증해야 합니다",
  "summary": "설정 이름과 런타임 UUID가 달라 비활성화가 반영되지 않았을 수 있습니다.",
  "evidence": ["settings key ...", "runtime UUID ..."],
  "scope": "global",
  "target": "Claude connector settings",
  "action": "런타임 확인 후 유지 또는 비활성화",
  "recovery": "기존 설정 백업 복원",
  "approval_required": true,
  "diff": "",
  "diff_sha256": ""
}
```

- `highlight: true`인 중요 발견만 Top findings 카드에 올라간다. 카드 수는 고정하지 않는다.
- `KEEP`, `REMOVE`, `NARROW`, `MERGE`, `DECIDE`, `DUE`, `RUNTIME EVIDENCE`를 모두 허용한다.
- 낮은 영향, 단순 미사용, 증거 부족은 보통 `highlight: false`다.
- `diff`가 있으면 unified diff 전체를 접힌 상태로 표시한다. 렌더 전 SHA-256을 계산해 `diff_sha256`과 대조한다.
- diff가 없는 앱 UI·외부 설정 항목은 `target`, `action`, `recovery`를 반드시 채운다.

## decisions.json

HTML이 내보내는 형식이다.

```json
{
  "schema_version": "1.0",
  "report_id": "model-refresh-20260830-190000",
  "report_sha256": "...",
  "generated_at": "...",
  "choices": [
    {
      "finding_id": "connector-gmail",
      "decision": "approve",
      "note": "런타임 확인 후 끄기",
      "diff_sha256": "..."
    }
  ],
  "unresolved": [],
  "executable": true
}
```

Phase 4 전 검증:

1. `report_id`가 현재 실행과 일치한다.
2. `report_sha256`이 현재 Phase 3 `report.json`과 일치한다.
3. 각 `finding_id`와 `diff_sha256`이 현재 보고서와 일치한다.
4. 모든 승인 필요 항목이 `approve|reject|defer` 중 하나다.
5. 사용자가 현재 채팅에서 이 결정 파일대로 진행하라고 명시한다.

외부 발송·삭제·구매·배포·권한 변경 등 별도 승인이 필요한 행위는 결정 JSON이나 일괄 채팅 확인으로 권한이 생기지 않는다. 실행 시점에 해당 행위의 승인을 다시 받는다.

## Phase 5

```json
{
  "status": "COMPLETE",
  "completed_at": "...",
  "scores": {"context_fitness": {"value": 0.98, "confidence": "high", "evidence": "재측정"}},
  "results": [
    {
      "finding_id": "connector-gmail",
      "decision": "approve",
      "applied": true,
      "verification": "PASS",
      "summary": "런타임 UUID 기준으로 비활성화 확인",
      "backup": "..."
    }
  ],
  "remaining": ["완료 검사 3건은 다음 감사로 이월"]
}
```

## 공유 PNG

- 1200×675, 브라우저 Canvas로 로컬 생성한다.
- 기본은 개인정보 보호 모드다. 절대경로, 프로젝트명, 구체적인 플러그인·커넥터 이름, 사용자 메모, diff를 제외한다.
- 공유 문구는 `share`의 사전 정제된 텍스트만 사용한다. 없으면 등급·상태·집계 수치만 표시한다.
- 외부 업로드는 하지 않는다.
