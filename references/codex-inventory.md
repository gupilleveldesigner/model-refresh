# Codex CLI 인벤토리 절차

Phase 1에서 `~/.codex`가 존재할 때 수행한다. Codex의 설정 스키마는 버전마다 달라질 수 있으므로, 아래 섹션 이름이 안 보이면 실물 파일을 먼저 확인하고 이 문서보다 실물을 우선한다.

## 파일 구조

- **`~/.codex/AGENTS.md`** — Claude의 CLAUDE.md에 대응하는 전역 라우터. 같은 판정 기준(모델이 스스로 알아낼 수 있는가)을 라인 단위로 적용한다.
- **`~/.codex/config.toml`** — Claude라면 `settings.json` + `settings.local.json` + `~/.claude.json`을 합쳐놓은 자리다. 아래 섹션들을 읽는다:
  - `[mcp_servers.<name>]` — MCP 서버 등록. Claude의 `mcpServers`에 대응.
  - `[projects.'<절대경로>']` — 프로젝트별 설정. 경로 표기가 대소문자·슬래시 방향으로 갈릴 수 있으니(`c:\users\...` vs `C:\Users\...`), Claude의 이중 프로젝트 키 문제와 같은 방식으로 실물을 확인한다 — 같은 프로젝트가 다른 표기로 두 벌 있으면 어느 쪽이 반영되는지 실증 없이 한쪽만 고치지 않는다.
  - `[marketplaces.<name>]` — 플러그인 마켓플레이스 등록.
  - `[plugins."<name>@<marketplace>"]` — 활성 플러그인. Claude의 `enabledPlugins`에 대응.
  - `[hooks.state.'<key>']` — 등록된 훅. 키 형태가 두 종류다: 프로젝트 로컬 훅은 `'<프로젝트 절대경로>\.codex\hooks.json:<이벤트>:0:0'`처럼 프로젝트 파일을 가리키고, 플러그인이 심은 훅은 `"<플러그인>@<마켓플레이스>:hooks/<파일>:<이벤트>:0:0"`처럼 플러그인 소유임을 명시한다. **훅 스크립트 실물은 이 키가 가리키는 파일(`hooks/<파일>`은 플러그인 설치 경로 기준, 프로젝트 훅은 `<프로젝트>\.codex\hooks.json`)에 있다** — Claude와 마찬가지로 스크립트를 열어 출력 종류를 나열한 뒤 판정한다.
  - `[agents.<name>]` — 커스텀 에이전트 정의.
  - `[features]`, `[desktop]`, `[tui.*]`, `[shell_environment_policy.*]`, `[windows]` 등 — 동작 설정. 대부분 사용자 취향 영역이라 "사용자 판단"으로 분류하되, 명백히 구모델 보정용인 항목(예: 특정 실수를 막기 위한 우회 설정)이 있으면 기준 1을 적용한다.
- **`~/.codex/skills/<name>/`** — Claude의 `~/.claude/skills/`에 대응하는 스킬 디렉토리. `SKILL.md`만 있는 경우도, `agents/openai.yaml`(Codex용 표시 이름·기본 프롬프트 매니페스트)이 같이 있는 경우도 있다.
- **`~/.codex/MEMORY.md`** — Codex의 영구 메모리 파일. Claude 쪽 메모리 디렉토리(`~/.claude/projects/<slug>/memory/`)와 같은 역할이지만 위치·형식이 다르다. 실사용 증거 확인 시 이쪽도 훑는다.
- **`~/.codex/skills-archived/`** (있는 경우) — 과거 비활성화 이력. Phase 0에서 참고 자료로 훑는다.

## 인벤토리 수집 시 주의

- **`auth.json`, `cap_sid`, 세션 상태 파일(`.codex-global-state.json` 등)은 감사 대상이 아니다.** 인증·런타임 상태이지 지침이 아니므로 건드리지 않고 읽지도 않는다.
- config.toml은 **TOML**이다. 섹션 삭제·수정 시 JSON과 다른 문법(따옴표 규칙, 배열, 중첩 테이블)을 지켜야 한다 — 자세한 안전 규칙은 `references/apply-protocol.md`.
- 공식 CLI로 플러그인을 켜고 끄는 대응 명령이 있는지 먼저 `codex --help` 계열로 확인한다. 이 문서 작성 시점에 확실히 검증된 대응 명령은 없다 — 있는지 없는지 먼저 확인하고, 없으면 config.toml 직접 편집이 유일한 경로임을 보고서에 명시한다.
- `[hooks.state.*]`에 플러그인 소유 훅이 있으면, 그 플러그인을 나중에 비활성화할 때 이 훅 항목도 죽은 설정으로 남을 수 있다 — Claude 쪽과 같은 함정이다.

## 스킬이 정션/심볼릭 링크인지 실물인지 구분

`~/.codex/skills/<name>`이 정션이면 그 실체는 도구 간 중복 판정의 대상이지, 이 도구만의 독립 삭제 후보가 아니다 — 링크 대상 경로를 기록해 두고 Phase 2의 "도구 간 중복" 판정으로 넘긴다. 확인 방법은 `references/claude-inventory.md`와 동일 (`LinkType`/`[ -L ]`).
