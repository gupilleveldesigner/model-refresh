# evals — model-refresh 품질 계측

이 디렉토리는 `package_skill.py`의 `ROOT_EXCLUDE_DIRS`에 포함돼 **패키징에서 제외된다.** 배포본에는 실려 나가지 않으므로 받는 사람의 비용은 0이다. 제작자가 스킬 품질을 실측하기 위한 장치다.

## 왜 픽스처를 쓰는가

이 스킬은 실제 셋업 파일을 감사하고 고친다. eval을 실제 홈(`~/.claude`)에 대고 돌리면 테스트가 사용자의 진짜 설정을 바꾼다. 그래서 결함을 미리 심어 둔 합성 홈을 대상으로 돌린다.

`fixture-home/`은 실제 사람의 셋업이 아니라 전부 지어낸 것이다 — 개인 경로·프로젝트명이 들어가지 않도록 유지할 것.

## 심어 둔 결함 (전부 이진 판정)

| # | 위치 | 심은 것 | 통과 조건 |
|---|---|---|---|
| 1 | `fixture-home/.claude.json` | 같은 폴더가 `D:\work\alpha-app` 와 `D:/work/alpha-app` 두 키로 존재 | 보고서가 이중 키를 지적 |
| 2 | `fixture-home/.claude/hooks/guard.js` | 안내문과 `permissionDecision: "deny"` 가드레일이 한 스크립트에 동거 | 통째 비활성이 아니라 좁히기를 제안 |
| 3 | `fixture-home/.claude/skills/puzzle-*` | `beta-puzzle` 프로젝트 전용 스킬 3개 | 삭제 후보 줄에 프로젝트 스코프 명시 |
| 4 | `fixture-home/.claude/hooks/reader-nudge.js` | 5분 쿨다운 + 확장자 목록에 `.md/.txt/.rst` | 빈도를 "매번"이라 단정하지 않음 + 확장자 오탐 지적 |
| 5 | `fixture-audits/2026-05-01-model-4.md` | `permissions.defaultMode` 거절 이력 | 재제안하지 않음 |

음성 케이스(id 3~5)는 near-miss 트리거다 — `update-config`, 코드베이스 탐색, 컴팩트 요청에 이 스킬이 잘못 발동하지 않는지 본다.

**현재 커버리지 경계:** eval 6은 스킬 실사용 증거가 독립 성적표가 아니라 기존 `model-refresh` 후보 판정에 결합되는지, 세션 전체가 아니라 스킬 사용 구간으로 귀속하는지 검사한다. 개별 스킬·사용 구간·대화에는 등급을 매기지 않지만, 전체 셋업 건강도 다섯 축은 별도 지표로 허용한다. 실제 세션 수집기의 구현·호스트별 로그 포맷은 이 프롬프트 eval의 대상이 아니다. 정적 Codex 설정 인벤토리(`config.toml`·`AGENTS.md`), 도구 간 정션 전환, Phase 4 실제 적용도 계속 사람 승인 전용이다.

## 실행

### 트리거 측정 — 하니스보다 직접 측정을 권한다

`skill-creator`의 `run_eval`/`run_loop`는 **환경에 따라 조용히 전부 0을 반환한다.** 2026-08-01 Windows에서 실측한 장애가 셋이다:

1. `run_eval.py`가 `select.select()`를 파이프에 쓴다 — Windows는 소켓만 받으므로 `OSError [WinError 10093]`. 매 쿼리가 즉시 `False`.
2. `run_loop.py`와 `utils.py`가 `read_text()`를 인코딩 없이 호출한다 — 한국어 로케일에서 UTF-8 파일을 cp949로 읽다 죽는다. `PYTHONUTF8=1`로 우회.
3. `find_project_root()`가 cwd에서 위로 올라가며 첫 `.claude/`를 찾는데, 홈 디렉토리를 잡으면 세션이 극단적으로 느려진다(실측 180초 초과 vs 가벼운 디렉토리 6초). 매 쿼리 타임아웃 → 역시 전부 `False`.

4. (2026-08-01 저녁 추가, 위 셋보다 결정적) 셋을 다 우회해도 전부 0이었다. 원인은 스텁 등록 실패가 아니다 — 스텁은 정상 등록된다(`stub_in_slash_commands=True`). **모델이 스텁 대신 이미 설치된 진짜 스킬을 호출한다.** 하니스는 자기가 만든 해시 이름이 불렸을 때만 성공으로 세므로, 매번 정상 발동하는 스킬이 매번 실패로 집계된다. 진단 3건 전부 `stub_hit=False` / `real_hit=True`로 일치했다. `model-refresh`처럼 `~/.claude/skills`에 사용자 스코프로 설치된 스킬은 모든 프로젝트에서 로드되므로 항상 이 조건에 걸린다.

**해법**: 측정용 임시 디렉토리의 `.claude/settings.local.json`에 `skillOverrides`로 대상 스킬을 측정 중에만 끈다. 적용 즉시 하루 종일 0이던 트리거가 `rate=1/1`로 잡혔다. 스킬 폴더를 rename하는 방식보다 안전하다 — 프로세스가 죽어도 원상태가 유지된다.

> `skillOverrides`를 실제 프로젝트 설정에 남기면 스킬이 조용히 꺼진다. **반드시 임시 측정 디렉토리에서만** 쓸 것.

**중요**: 실패 방식이 예외가 아니라 "전부 0"이다. 음성 케이스는 0에서 자동 통과하므로 그럴듯한 점수가 나오고, 이를 description 품질 결과로 오독하기 쉽다. 실제로 그런 오독이 한 번 있었다.

### 권장 — 직접 측정

스텁을 거치지 않고, 실제 등록된 스킬이 트리거되는지 스트리밍으로 본다:

```
claude -p "<쿼리>" --output-format stream-json --verbose --include-partial-messages
```

`content_block_start`에 `tool_use` / `name: "Skill"`이 나오면 그때부터 `input_json_delta`의 `partial_json`을 이어 붙여 스킬 이름을 확인하고, 확인되는 즉시 프로세스를 죽인다. 트리거되면 6~13초, 안 되면 타임아웃까지 간다 — 이 시간 차 자체가 신호다.

주의: 작업 디렉토리는 **가벼운 임시 폴더**로 둘 것. 홈 디렉토리에서 띄우면 측정이 아니라 인내심 시험이 된다.

### 참고 (하니스를 굳이 쓸 경우)

```
cd <가벼운 작업 폴더>
PYTHONPATH=<skill-creator 경로> PYTHONUTF8=1 python -m scripts.run_eval \
  --eval-set <이 폴더>/trigger-evals.json --skill-path <이 스킬 경로> --timeout 180
```

### 실행 전 필수 확인 — 패치가 살아 있는가

로컬 `run_eval.py`는 위 장애 1을 고친 **패치본**이다(스레드+큐 리더). 업스트림 `anthropics/skills` main에는 2026-08-01 기준 여전히 `select.select`가 있고 관련 PR 10건 이상이 미머지다 — 즉 **skill-creator를 재설치/업데이트하면 패치가 사라진다.** 실패 방식이 예외가 아니라 "전부 0"이라 조용한 회귀가 된다.

경고 장치는 없다. 원본 사양을 바꾸지 않기로 해서 의도적으로 심지 않았다. 대신 실행 전에 직접 확인한다:

```
grep -n "PATCH (local)" <skill-creator 경로>/scripts/run_eval.py
```

- 한 줄 나오면 패치본이다. 그대로 진행.
- **아무것도 안 나오면 재설치로 패치가 날아간 것이다.** 점수를 읽지 말고 먼저 복구할 것.

복구본과 원본 보관 위치:

- 패치본 사본: `~/.claude/audits/model-refresh/run_eval.py.patched-20260801` (스킬 폴더 **밖**이라 재설치에도 살아남는다)
- 업스트림 원본: `<skill-creator 경로>/scripts/run_eval.py.orig` (스킬 폴더 안이라 재설치 시 함께 사라진다)

## 범위 제한

**Phase 4(적용)는 eval 대상이 아니다.** 실환경을 바꾸는 단계이고 그 안전장치는 사람의 승인 게이트인데, 승인 게이트는 자동 채점 대상이 아니다. 모든 eval 프롬프트는 "Phase 3 보고서까지만"으로 끝난다.

## HTML 보고서 결정적 검증

보고서 UI는 `evals/report-fixtures/`의 한국어 Phase 3·영어 Phase 5 픽스처로 검증한다.

```text
python scripts/render_report.py evals/report-fixtures/ko-phase3.json --output <TEMP>/ko-phase3.html
python scripts/render_report.py evals/report-fixtures/en-phase5.json --output <TEMP>/en-phase5.html
```

확인 항목:

- 요청 언어의 HTML 하나만 생성되는가
- 중요 발견 수만큼 Top findings 카드가 생기는가
- Phase 5가 없으면 최종 탭이 비활성화되는가
- 다섯 점수 축과 문자 등급이 계산되는가
- diff·승인 UI·결정 JSON·개인정보 보호 PNG 코드가 포함되는가
- Phase 5가 있으면 적용 전→후 상태가 같은 HTML에 공존하는가

브라우저 정책이 로컬 `file://` 자동 클릭을 막는 환경에서는 클릭 우회를 하지 않는다. 렌더·정적 DOM 계약·결정 JSON 검증기로 확인하고, 실제 다운로드 동작은 사용자가 보고서를 여는 환경에서 수행한다.
