# deep mode — safe-mode baseline comparison

If static analysis judges "this looks unnecessary in theory," deep mode proves "is it actually unnecessary." The principle: run your usual work against a baseline with the whole setup turned off, and if the result is the same, that setup element had no reason to exist.

## Procedure

1. **Pick representative tasks** — pull 3–5 tasks the user actually does often from recent session records/memory, and write them up as reproducible prompts. This only means something if they're real tasks, not artificial tests.
2. **Write the pass/fail criteria first** — **before** starting the comparison, write down a fixed, falsifiable criterion for each task (e.g., "the generated document has section X and doesn't violate rule Y," "exactly these 3 files got modified and tests pass"). "The results look similar" is not a criterion — that's the same "run it and see if it looks good" this skill criticizes elsewhere. If a criterion can't come out "no," rewrite it.
3. **Run the baseline** — have the user open a new session in safe mode (the whole setup disabled) and run those prompts. Known entry points as of writing: the `--safe-mode` flag, the `CLAUDE_CODE_SAFE_MODE=1` environment variable, or `--bare`. These can change between versions, so check with `claude --help` before guiding the user.
4. **Run current** — run the same prompts in a session with the current setup (an existing session record can substitute for this if you already have one).
5. **Compare and judge** — apply step 2's criteria to both, per task, and record: pass/fail, evidence the setup intervened (a skill fired, a hook took effect), and whether that intervention helped or got in the way. If the baseline passes the criteria exactly as the current setup does, that setup element is promoted from a static "deletion candidate" to a proven one.
6. **Merge the result into the Phase 3 report** — present it as two columns, "static judgment + empirical result," so the user's approval decision is easier.

## Caution

- Don't conclude from a single comparison. Model output varies run to run — if it's ambiguous, rerun just that task once more.
- Doing fine in safe mode is evidence the setup was unnecessary; failing in safe mode is not automatically evidence the setup is required — often, giving the prompt more context fixes it (instruction placement priority: prompt → CLAUDE.md → skill → MCP).
