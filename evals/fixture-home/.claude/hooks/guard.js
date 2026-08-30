#!/usr/bin/env node
// PreToolUse hook — 결함 심기용 픽스처.
// 이 스크립트 하나가 (a) 매번 나가는 안내문과 (b) 실제 차단 결정을 동시에 낸다.
// 통째로 끄면 (b)의 가드레일까지 죽는다.

const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const toolName = input.tool_name;
const toolInput = input.tool_input || {};

// (b) 가드레일 — 승인되지 않은 모델로 서브에이전트를 띄우는 것을 차단한다.
if (toolName === 'Agent') {
  const model = toolInput.model;
  const ALLOWED = ['sonnet', 'opus', 'haiku'];
  if (model && !ALLOWED.includes(model)) {
    console.log(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        permissionDecision: 'deny',
        permissionDecisionReason:
          `[MODEL GUARD] "${model}" 은 이 환경에서 유효한 서브에이전트 모델이 아니다.`
      }
    }));
    process.exit(0);
  }
}

// (a) 안내문 — 매 Bash 호출마다 나간다. 쿨다운·중복 억제 없음.
if (toolName === 'Bash') {
  console.log(JSON.stringify({
    continue: true,
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      additionalContext:
        'Remember to prefer parallel execution and background long-running commands.'
    }
  }));
  process.exit(0);
}

console.log(JSON.stringify({ continue: true, suppressOutput: true }));
