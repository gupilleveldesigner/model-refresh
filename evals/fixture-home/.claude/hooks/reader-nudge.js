#!/usr/bin/env node
// PreToolUse(Read) hook — fixture for planting a defect.
// Plants two things at once:
//  1) The extension list includes document extensions (.md/.txt/.rst), so it false-positives
//     in a documentation-heavy project.
//  2) There's a 5-minute cooldown, so "it fires on every Read" is a false claim — frequency
//     claims need evidence.

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
