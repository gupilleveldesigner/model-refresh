# evals — model-refresh quality measurement

This directory is listed in `package_skill.py`'s `ROOT_EXCLUDE_DIRS` and is **excluded from packaging.** It doesn't ship in the distributed skill, so it costs recipients nothing. It exists for the maintainer to actually measure skill quality.

## Why fixtures

This skill audits and modifies real setup files. Running evals against a real home directory (`~/.claude`) would mean the test changes the user's actual configuration. So evals run against a synthetic home with deliberately planted defects instead.

`fixture-home/` is entirely made up — it is not any real person's setup. Keep it that way: no personal paths or project names.

## Planted defects (all binary pass/fail)

| # | Location | What was planted | Pass condition |
|---|---|---|---|
| 1 | `fixture-home/.claude.json` | The same folder exists under two keys, `D:\work\alpha-app` and `D:/work/alpha-app` | The report flags the duplicate key |
| 2 | `fixture-home/.claude/hooks/guard.js` | A notice and a `permissionDecision: "deny"` guardrail live in the same script | Proposes narrowing, not a full disable |
| 3 | `fixture-home/.claude/skills/puzzle-*` | Three skills specific to the `beta-puzzle` project | If listed as a deletion candidate, the line states project scope |
| 4 | `fixture-home/.claude/hooks/reader-nudge.js` | A 5-minute cooldown, plus `.md`/`.txt`/`.rst` in the extension list | Doesn't assert "every time" as the frequency + flags the extension false-positive |
| 5 | `fixture-audits/2026-05-01-model-4.md` | A rejection history for `permissions.defaultMode` | Not re-proposed |

The negative cases (ids 3–5) are near-miss triggers — they check that this skill does *not* misfire on an `update-config` request, codebase exploration, or a compact request.

**Known coverage gap (added 2026-08-04, when cross-tool support landed):** `fixture-home/` only mimics Claude's structure (`.claude.json`, `.claude/hooks/`, `.claude/skills/`). The Codex-side inventory procedure (`references/codex-inventory.md`) and the "cross-tool duplication" judgment (`references/audit-rules.md`) only got trigger phrases added to `trigger-evals.json` — they have **not** been exercised by this eval harness yet. Not hiding that here — a `fixture-codex-home/` (a fake `config.toml`/`AGENTS.md`/`skills/`) plus a cross-tool duplication case (a fixture where the same skill exists as a real copy on both sides) is the next priority.

## Running the evals

### Measuring trigger accuracy — direct measurement beats the harness here

`skill-creator`'s `run_eval`/`run_loop` **silently returns all-zero depending on the environment.** Three actual failure modes observed on Windows as of 2026-08-01:

1. `run_eval.py` calls `select.select()` on a pipe — Windows only accepts sockets there, so it raises `OSError [WinError 10093]`. Every query fails instantly as `False`.
2. `run_loop.py` and `utils.py` call `read_text()` with no encoding specified — on a non-English locale it tries to read a UTF-8 file as cp949 and crashes. Work around it with `PYTHONUTF8=1`.
3. `find_project_root()` walks up from cwd looking for the first `.claude/` — if it lands on the home directory, the session becomes extremely slow (measured: over 180 seconds vs. 6 seconds for a lightweight directory). Every query times out → also reads as all-`False`.

4. (Added the evening of 2026-08-01, more decisive than the three above) Even after working around all three, everything still came back 0. The cause isn't a stub-registration failure — the stub registers fine (`stub_in_slash_commands=True`). **The model calls the real, already-installed skill instead of the stub.** The harness only counts success when its own hashed stub name gets called, so a skill that fires correctly every time gets tallied as a failure every time. All three diagnostic runs matched `stub_hit=False` / `real_hit=True`. Any skill installed at user scope under `~/.claude/skills` — like `model-refresh` — loads in every project, so it always hits this condition.

**Fix**: in the measurement temp directory's `.claude/settings.local.json`, use `skillOverrides` to disable the target skill *for the measurement only*. The moment this was applied, a score that had been 0 all day long jumped to `rate=1/1`. This is safer than renaming the skill folder — if the process dies mid-run, the original state stays intact.

> Leaving `skillOverrides` in a real project's settings silently turns the skill off. Use it **only in a throwaway measurement directory.**

**Important**: the failure mode is "all zero," not an exception. Negative cases pass automatically at zero, producing a plausible-looking score, and it's easy to misread that as a real description-quality result. This misreading actually happened once.

### Recommended — direct measurement

Skip the stub and watch, via streaming, whether the actually-registered skill fires:

```
claude -p "<query>" --output-format stream-json --verbose --include-partial-messages
```

When `content_block_start` shows a `tool_use` block named `"Skill"`, start concatenating `input_json_delta`'s `partial_json` to read the skill name, and kill the process as soon as you can confirm it. A trigger takes 6–13 seconds; a non-trigger runs to the timeout — that time difference is itself a signal.

Caveat: run this from a **lightweight temp folder** as the working directory. Launching from the home directory turns measurement into a patience test.

### Reference (if you use the harness anyway)

```
cd <lightweight working folder>
PYTHONPATH=<skill-creator path> PYTHONUTF8=1 python -m scripts.run_eval \
  --eval-set <this folder>/trigger-evals.json --skill-path <this skill's path> --timeout 180
```

### Before running — confirm the patch is still applied

The local `run_eval.py` is a **patched build** that fixes failure mode 1 above (a thread+queue reader). As of 2026-08-01, upstream `anthropics/skills` main still has `select.select`, and more than 10 related PRs are unmerged — meaning **reinstalling or updating skill-creator wipes the patch out.** Because the failure mode is "all zero" rather than an exception, this becomes a silent regression.

There's no built-in warning for this — deliberately left out, to avoid changing the upstream spec. Instead, confirm manually before running:

```
grep -n "PATCH (local)" <skill-creator path>/scripts/run_eval.py
```

- One line of output → it's the patched build. Proceed.
- **No output → the patch was lost on reinstall.** Don't trust the score; restore the patch first.

Where the patched copy and the original are kept:

- Patched copy: `~/.claude/audits/model-refresh/run_eval.py.patched-20260801` (outside the skill folder, so it survives a reinstall)
- Upstream original: `<skill-creator path>/scripts/run_eval.py.orig` (inside the skill folder, so it disappears on reinstall)

## Scope limits

**Phase 4 (apply) is not in scope for evals.** It's the phase that changes the real environment, and its safety mechanism is a human approval gate — an approval gate isn't something you auto-grade. Every eval prompt is scoped to stop at "through the Phase 3 report."
