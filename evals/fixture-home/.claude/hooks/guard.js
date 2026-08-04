#!/usr/bin/env node
// PreToolUse hook — fixture for planting a defect.
// This single script emits both (a) a notice on every call and (b) a real block decision.
// Disabling it wholesale kills the guardrail in (b) too.

const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const toolName = input.tool_name;
const toolInput = input.tool_input || {};

// (b) Guardrail — blocks spawning a subagent with an unapproved model.
if (toolName === 'Agent') {
  const model = toolInput.model;
  const ALLOWED = ['sonnet', 'opus', 'haiku'];
  if (model && !ALLOWED.includes(model)) {
    console.log(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        permissionDecision: 'deny',
        permissionDecisionReason:
          `[MODEL GUARD] "${model}" is not a valid subagent model in this environment.`
      }
    }));
    process.exit(0);
  }
}

// (a) Notice — fires on every Bash call. No cooldown, no dedup.
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
