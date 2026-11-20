# Model Refresh HTML 보고서 계약

이 계약은 Phase 3 감사 결과를 검토 가능한 단일 HTML로 만들고, Phase 5 적용 결과를 같은 보고서에 보존한다. 보고서는 로컬 전용이며 외부 서비스에 의존하지 않는다. `report.html`은 파일로 열어도 완전히 동작하고, 결정을 받는 동안에만 `review_server.py`가 같은 페이지를 루프백(127.0.0.1)으로 제공한다.

## 산출물과 생명주기

감사마다 스킬 폴더 밖의 고유 실행 디렉터리를 만든다.

```text
<AUDIT_ROOT>/runs/<run-id>/
├─ report.json
├─ report.html
├─ decisions.json      # 스크립트가 기록한다. 사용자가 옮기는 파일이 아니다
└─ evidence/...
```

- Phase 3: `report.json.phase3`를 채우고 `report.html`을 생성한다. 상태는 `AWAITING_APPROVAL`이다.
- 사용자는 HTML에서 항목별 승인·거절·보류와 메모를 고르고 **결정 제출**을 누르거나, 채팅으로 답한다. 어느 쪽이든 `decisions.json`은 스크립트가 실행 디렉터리에 기록한다. 사용자가 JSON을 내려받거나 올리는 단계는 없다.
- `decisions.json`은 사용자가 화면이나 채팅에서 한 선택의 기록이다. 승인의 근거는 그 제출 이벤트나 사용자 메시지이고, 다른 경로로 놓인 파일은 권한을 만들지 않는다. 받은 승인은 다시 확인받지 않으며, 변경된 범위·내용·추가 권한만 새로 확인한다.
- Phase 5: 같은 `report.json`에 `phase5`를 추가하고 `finalize_run.py`로 기록을 검증한 뒤 같은 `report.html`을 다시 생성한다. Phase 3 제안은 변경하지 않는다.
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
  "schema_version": "1.2",
  "mode": "setup",
  "report_id": "model-refresh-20260830-190000",
  "generated_at": "2026-08-30T19:00:00+09:00",
  "locale": "ko-KR",
  "title": "Model Refresh Report",
  "target_model": "current",
  "hosts": ["claude", "codex"],
  "phase3": {
    "status": "AWAITING_APPROVAL",
    "summary": "셋업 감사 예시. 아래 점수는 실측 결과가 아닙니다.",
    "required_stages": ["audit"],
    "scores": {
      "context_fitness": {"value": 0.96, "confidence": "high", "evidence": "실측 /context"},
      "runtime_hygiene": {"value": 0.88, "confidence": "medium", "evidence": "훅·MCP 실물 확인"},
      "cross_tool_consistency": {"value": 0.92, "confidence": "high", "evidence": "정션·해시 비교"},
      "skill_usage_fit": {"value": 0.82, "confidence": "medium", "evidence": "후보 사용 구간 확인"},
      "eval_freshness": {"value": null, "confidence": "low", "evidence": "검사 유효성 미확인"}
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

## 근거와 완료 계약 검증

새 보고서는 `schema_version: "1.2"`, `mode: "migration"|"setup"`을 사용한다. 1.2는 1.1에 Phase 5 항목별 근거 계약(아래 "Phase 5")을 더한 것이다. 1.1 기록은 그대로 읽는다. 모델 교체 요청은 `migration`이며 `model-evidence.md`의 `model_review`가 필수다. 일반 셋업 정리는 `setup`으로 불필요한 모델 조사를 생략한다. 과거 1.0 기록은 호환성 경고와 함께 읽되, 새 보고서를 1.0이나 1.1로 작성해 검사를 우회하지 않는다.

`python "<SKILL_ROOT>/scripts/validate_report.py" "<RUN_DIR>/report.json"`

렌더러와 결정 검증기도 이 계약을 확인한다. 검증은 근거 구조와 상태의 정합성만 확인하며 출처의 권위·인용의 정확성·모델 행동·실행 권한을 입증하지 않는다. 해당 의미 검토는 실행자의 책임이다.

Phase 3의 `required_stages`에 합의한 완료 범위(`audit`, 필요 시 `application`, `behavior`, `effect`)를 먼저 적는다. Phase 5에는 네 단계 모두 `pass|fail|unverified|not_applicable`과 근거 또는 이유를 기록한다. 필수 단계 미통과 또는 승인 작업 미적용은 `PARTIAL`; 충족하면 `COMPLETE`; 실제 적용이 없고 필수 단계를 충족하면 `NO_CHANGES`다. 거절·보류는 승인 작업 누락으로 세지 않는다. 동작·효과가 필수 범위 밖이면 미검증을 명시한 채 감사·적용을 완료할 수 있다. 효과 통과에는 실제 비교 측정 근거가 필요하다.

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
- `diff`가 있으면 unified diff 전체를 접힌 상태로 표시한다. 렌더 전 SHA-256을 계산해 `diff_sha256`과 대조한다. `+++` 헤더의 대상은 절대경로나 `~/…`로 적는다. `finalize_run.py`는 그 경로로 적용 결과를 디스크와 대조하며, 상대경로 diff는 대조하지 못한다.
- `approval_required: true`인 항목은 보고서 순서대로 `#1`부터 번호가 붙는다. HTML, 채팅 목록, `record_decisions.py`가 같은 번호를 쓴다.
- diff가 없는 앱 UI·외부 설정 항목은 `target`, `action`, `recovery`를 반드시 채운다.

## decisions.json

사용자가 직접 다루지 않는 기록 파일이다. 세 경로 중 하나로 `<RUN_DIR>/decisions.json`에 쓰인다.

| `source` | 사용자가 한 일 | 기록 주체 |
|---|---|---|
| `review_server` | 보고서 화면에서 **결정 제출** | `review_server.py` (루프백 POST 수신) |
| `clipboard` | 화면의 **결정 복사** 내용을 채팅에 붙여넣음 | `record_decisions.py --source clipboard` |
| `chat` | 채팅으로 답함 | `record_decisions.py` |

```json
{
  "schema_version": "1.1",
  "report_id": "model-refresh-20260830-190000",
  "report_sha256": "...",
  "generated_at": "...",
  "source": "review_server",
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

`source`가 없는 1.0 파일도 읽는다.

### 리뷰 서버

`review_server.py <RUN_DIR>/report.json`은 보고서를 렌더해 `127.0.0.1`의 임시 포트로 제공하고 브라우저를 연 뒤 제출을 기다린다. 승인할 항목이 없으면 서버 없이 HTML만 열고 끝난다.

- 주소에는 실행마다 새로 만든 토큰이 들어간다. 토큰이 없는 요청, 다른 `Host`·`Origin`의 요청은 거절한다.
- 제출 본문은 `validate_decisions`를 통과해야 기록된다. 미결정 항목이 남은 본문은 받지 않는다(화면이 제출 전에 남은 항목을 보류로 확정받는다).
- 한 번 받은 뒤에는 종료한다. 결정을 바꾸려면 서버를 다시 띄운다.
- 종료 코드: 0 제출 수신 또는 승인 항목 없음, 3 시간 초과, 1 오류. 진행 상황은 JSON 줄(`serving`, `submitted`, `timeout`, `no_approvals`)로 출력한다.
- `--detach`는 서버를 독립 프로세스로 남기고 즉시 반환한다. 실행 중에는 `<RUN_DIR>/review-server.json`에 주소가 있다.

파일로 연 `report.html`에서는 같은 버튼이 **결정 복사**가 되어, 채팅에 붙여넣을 짧은 텍스트를 클립보드에 넣는다.

```text
[model-refresh 결정] model-refresh-20260830-190000 #72fce402d259
승인: 1 connector-gmail
거절: 2 skill-y
보류: 없음
메모:
- 2 skill-y: 아직 사용 중
```

`#` 뒤는 보고서 해시 앞 12자리다. `record_decisions.py --expect-report-sha`에 넘기면, 사용자가 본 보고서와 지금의 `report.json`이 다를 때 기록을 거부한다.

### Phase 4 전 검증

`validate_decisions.py <RUN_DIR>/report.json`이 다음을 확인한다.

1. `report_id`가 현재 실행과 일치한다.
2. `report_sha256`이 현재 Phase 3 `report.json`과 일치한다.
3. 각 `finding_id`와 `diff_sha256`이 현재 보고서와 일치한다.
4. 모든 승인 필요 항목이 `approve|reject|defer` 중 하나다.

외부 발송·삭제·구매·배포·권한 변경은 사용자 승인이 해당 행위와 범위를 실제로 포함하는지 확인한다. 이미 명시적으로 승인된 동일 행위는 재승인하지 않으며, 새로운 행위나 범위 확대만 확인한다.

## Phase 5

```json
{
  "status": "COMPLETE",
  "completed_at": "...",
  "stages": {
    "audit": {"status": "pass", "evidence": ["공식 근거와 현재 설정 대조"]},
    "application": {"status": "pass", "evidence": ["승인 diff 적용 및 재파싱"]},
    "behavior": {"status": "pass", "evidence": ["대상 호스트의 새 세션 관찰"]},
    "effect": {"status": "unverified", "reason": "비용·품질 개선 미측정"}
  },
  "scores": {"context_fitness": {"value": 0.98, "confidence": "high", "evidence": "재측정"}},
  "results": [
    {
      "finding_id": "connector-gmail",
      "decision": "approve",
      "applied": true,
      "verification": "PASS",
      "verification_level": "runtime",
      "evidence": ["새 세션 init 이벤트에서 해당 서버가 disabled"],
      "summary": "런타임 UUID 기준으로 비활성화 확인",
      "backup": "..."
    },
    {"finding_id": "skill-y", "decision": "reject", "applied": false}
  ],
  "requires_new_session": ["Claude Code: 열려 있는 세션은 재시작 후 반영"],
  "remaining": ["완료 검사 3건은 다음 감사로 이월"]
}
```

### 항목별 근거 (1.2)

`results`에는 승인 필요 항목마다 한 줄이 있어야 하고, `decision`은 기록된 사용자 결정과 같아야 한다.

| 상황 | 필수 |
|---|---|
| 승인했고 적용함 | `applied: true`, `verification: PASS|FAIL|UNVERIFIED` |
| `PASS` | `evidence`(무엇을 관찰했는지 한 개 이상)와 `verification_level` |
| `FAIL`·`UNVERIFIED` | `summary`에 무엇이 빠졌는지 |
| 승인했지만 적용하지 못함 | `applied: false`와 `summary`에 이유. 사용자가 직접 할 일이면 `manual_action` |
| 거절·보류 | `applied: false` |

`verification_level`은 둘 중 하나다.

- `config`: 파일이나 CLI 상태에서 변경을 확인했다. 런타임이 그것을 읽는다는 증거는 아니다.
- `runtime`: 새 세션이 실제로 그렇게 동작하는 것을 관찰했다(`runtime-verify.md`).

적용한 항목 중 하나라도 `PASS`가 아니면 `COMPLETE`로 닫을 수 없고 `PARTIAL`이다. `config`만으로 `COMPLETE`는 가능하지만, 완료 보고에는 런타임 미확인으로 드러난다.

### 완료 보고

`python "<SKILL_ROOT>/scripts/finalize_run.py" "<RUN_DIR>/report.json"`은 위 계약, 사용자 결정과의 일치, Phase 3 제안의 불변, diff 대상 파일의 실제 상태를 확인하고 채팅에 전달할 완료 보고문을 출력한다. 하나라도 어긋나면 보고문 없이 종료 코드 1로 끝난다. 변경이 diff와 다른 형태로 반영되어 디스크 대조가 어긋나는 경우에만, 실제 확인 뒤 해당 결과에 `disk_check_note`로 경위를 남긴다.

보고문은 결정·적용·확인 건수, 항목별 상태, 네 단계의 상태와 근거, **이번 실행이 입증하지 않은 것**, 사용자가 직접 할 일, 새 세션이 필요한 변경, 남은 항목, 백업, 점수 변화를 담는다. 이 출력이 완료 보고의 정본이다.

## 공유 PNG

- 1200×675, 브라우저 Canvas로 로컬 생성한다.
- 기본은 개인정보 보호 모드다. 절대경로, 프로젝트명, 구체적인 플러그인·커넥터 이름, 사용자 메모, diff를 제외한다.
- 공유 문구는 `share`의 사전 정제된 텍스트만 사용한다. 없으면 등급·상태·집계 수치만 표시한다.
- 외부 업로드는 하지 않는다.
