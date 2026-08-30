#!/usr/bin/env node
// PreToolUse(Read) hook — 결함 심기용 픽스처.
// 두 가지를 동시에 심는다:
//  1) 확장자 목록에 문서 확장자(.md/.txt/.rst)가 들어 있어, 문서 위주 프로젝트에서 오탐한다.
//  2) 5분 쿨다운이 있으므로 "매 Read마다 뜬다"는 주장은 틀리다 — 빈도 주장에 근거가 필요하다.

const fs = require('fs');
const path = require('path');
const os = require('os');

const COOLDOWN_MS = Number(process.env.NUDGE_COOLDOWN_MS || 5 * 60 * 1000);
const STATE = path.join(os.tmpdir(), 'reader-nudge-throttle.json');

const CODE_EXTS = [
  '.py', '.js', '.ts', '.tsx', '.go', '.rs', '.java', '.rb', '.c', '.cpp', '.cs',
  '.md', '.txt', '.rst'
];

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const filePath = String((input.tool_input || {}).file_path || '');
const ext = path.extname(filePath).toLowerCase();

if (!CODE_EXTS.includes(ext)) {
  console.log(JSON.stringify({ continue: true, suppressOutput: true }));
  process.exit(0);
}

const message = 'Index the repository before reading individual source files.';

let state = {};
try { state = JSON.parse(fs.readFileSync(STATE, 'utf8')); } catch { state = {}; }
const now = Date.now();
const last = Number(state[message] || 0);

if (now - last < COOLDOWN_MS) {
  console.log(JSON.stringify({ continue: true, suppressOutput: true }));
  process.exit(0);
}

state[message] = now;
try { fs.writeFileSync(STATE, JSON.stringify(state)); } catch { /* fail open */ }

console.log(JSON.stringify({
  continue: true,
  hookSpecificOutput: {
    hookEventName: 'PreToolUse',
    additionalContext: message
  }
}));
