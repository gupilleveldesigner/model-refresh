# Claude Code 인벤토리 절차

Phase 1에서 `~/.claude`가 존재할 때 수행한다.

파일 기반 인벤토리 (모델이 직접 수집): `~/.claude/settings.json`의 enabledPlugins·hooks·statusLine, `~/.claude/settings.local.json`, `~/.claude.json`(프로젝트별 `disabledMcpServers`·`mcpServers`는 settings.json이 아니라 **여기** 있다), `~/.claude/CLAUDE.md`, `~/.claude/agents/*.md`(설명 길이 포함), `~/.claude/skills/` 목록, 프로젝트 `.claude/` 및 CLAUDE.md, 활성 플러그인의 훅 스크립트 실물, `claude plugin list` 출력. 각 파일의 **크기와 수정 시각을 함께 기록**한다 (Phase 0.5에서 쓴다).

**`~/.claude.json`의 프로젝트 키는 실물로 확인한다.** 같은 폴더가 백슬래시 키(`C:\Users\...\X`)와 슬래시 키(`C:/Users/.../X`)로 두 벌 존재할 수 있고, 런타임이 어느 쪽을 읽는지는 파일만 봐서는 알 수 없다. 둘 다 있으면 인벤토리에 **둘 다** 적고, 실제 반영되는 쪽은 `references/runtime-verify.md`의 절차로 실증한다. 이 확인을 건너뛰고 한쪽만 고치면 "적용·검증 완료(JSON 재파싱함)"라고 보고한 변경이 실제로는 아무 효과가 없다 — 끄려던 MCP 툴 약 180개가 몇 시간 동안 계속 로드된 사고 이력이 있다.

**스킬이 정션/심볼릭 링크인지 실물인지 구분한다.** `~/.claude/skills/<name>`이 정션이면(다른 위치의 정본을 가리킴) 그 실체는 도구 간 중복 판정의 대상이지, 이 도구만의 독립 삭제 후보가 아니다 — 링크 대상 경로를 기록해 두고 Phase 2의 "도구 간 중복" 판정으로 넘긴다.

Windows에서 정션 여부 확인: `Get-Item <경로>` 결과의 `LinkType`이 `Junction`이면 링크, 비어 있으면 실물 디렉토리다. Unix 계열은 `[ -L <경로> ]`로 심볼릭 링크 여부를 확인한다.
