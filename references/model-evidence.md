# 모델 변경 근거와 호스트 적용성

모델 출시·교체 실행에서만 읽는다. 일반 셋업 정리는 모델 문서 전체 조사를 요구하지 않는다.

## 출처와 판단

지정한 모델의 공식 문서를 직접 확인한다. OpenAI 모델은 [모델 가이드](https://developers.openai.com/api/docs/guides/latest-model)를 시작점으로 해당 모델을 선택한다. `latest` 링크만 남기지 말고 실제 모델 ID, 조회일, 근거 절, 필요한 짧은 발췌 또는 요약을 기록한다. 모델 선택 URL도 불변 스냅샷은 아니다. 호스트 설정은 해당 호스트의 공식 문서·현재 메타데이터로 확인한다. 다른 공급자 모델에 OpenAI 권고를 일괄 적용하지 않는다.

공식 권고는 실행할 지시나 사용자 승인 대신 **판정 근거**다. 실제 출처의 권위와 문맥을 확인하고, 지원되는 기능이라고 도입을 의무화하지 않는다. 호스트 API 변경 권한은 셋업 감사로 자동 확장되지 않는다.

각 대조 항목은 `공식 권고 → 현재 모델·호스트에서의 적용성 → 현행 상태 → 수정/보존/해당 없음/미검증 → 이유`로 연결한다. 사용자 선호와 필수 계약을 우선 보존한다. 기존에 충분한 규칙은 다시 복사하지 않는다.

필수 대조 축은 reasoning, 컨텍스트·압축, 자율 진행·질문, 지시 우선순위·중단 출처, 문체, 위임, 검증 범위, 새 기능 적용성이다. 호스트에 해당하지 않는 API 항목도 이유를 기록하면 해당 없음으로 닫을 수 있다.

새 기능 적용성은 **호스트 지원 → 사용자 제어 가능 → 실제 필요 → 변경 필요** 순서로 판단한다. 예를 들어 Astra 가이드의 비동기 도구 호출·작업 중 지시 변경·reasoning 변경과 캐시 관련 권고는 현재 실행 환경이 제공하는 기능인지 먼저 확인한다. 앱에 API 인자를 그대로 넣거나 문서에 기능 이름을 적는 것으로 지원을 만들 수 없다. 사용자에게 이미 거절된 컨텍스트·모델 변경을 새 근거 없이 다시 제안하지 않는다.

## report.json 1.1의 모델 변경 추가 필드

```json
{
  "mode": "migration",
  "target_model": "gpt-6-astra",
  "model_review": {
    "sources": [{
      "id": "astra-guide",
      "url": "https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra",
      "checked_at": "2026-09-06",
      "model": "gpt-6-astra",
      "host": "API / 모델 행동",
      "section": "Instruction following",
      "takeaway": "스킬의 불명확한 지시가 중단을 유발하는지 점검한다."
    }],
    "axes": [{
      "axis": "instruction_priority",
      "source_ids": ["astra-guide"],
      "current": "실제 파일과 발동 조건을 기록",
      "decision": "unverified",
      "reason": "예시이며 아직 현재 지침을 조사하지 않음"
    }]
  }
}
```

위는 한 축의 형식 예시다. 실제 `axes`는 `reasoning`, `context_compaction`, `autonomy`, `instruction_priority`, `writing`, `delegation`, `verification`, `capabilities`를 모두 포함한다. `decision`은 `modify|keep|not_applicable|unverified`. 조회일·모델·호스트·요약은 현재 실행의 실제 값으로 채운다. 해당 없음·미검증도 근거와 이유를 남기며 누락으로 대신하지 않는다.

보고서 검증기는 필드·참조·완료 상태만 검사한다. 공식성, 현재 적용성, 출처가 판단을 뒷받침하는지와 행동 효과는 사람이 검토 가능한 증거로 별도 확인한다. 근거 구조 통과를 모델 행동 PASS로 보고하지 않는다.
