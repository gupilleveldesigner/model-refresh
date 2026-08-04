# Apply protocol (Phase 4)

Delegate only approved items to a background agent (general-purpose). The main session keeps the conversation going.

## Agent prompt template

Fill approved items into the skeleton below and hand it off. Brackets mark substitution points.

```
Clean up an AI coding agent setup. Environment: [OS], tool home(s): [Claude Code: absolute path to ~/.claude] [Codex CLI: absolute path to ~/.codex] (whichever apply)

Work (approved items only):
[For each approved group of deletion / cross-tool integration candidates: what, which tool, and by what method]

CLAUDE.md/AGENTS.md approved-line block:
[Verbatim quote of the deletion lines approved in Phase 3, per file. If trimming wasn't approved for a file, write "none" for it]

Do not touch:
[Everything classified as "keep" + any group not approved by the user + project files + memory directories]

Safety rules:
1. Before modifying anything, create a backup directory [tool-home/backup-refresh-YYYYMMDD]
   and copy every file you're about to modify. Claude: ~/.claude/CLAUDE.md, the agents folder,
   settings.json, settings.local.json, ~/.claude.json, project .claude/settings.json and
   settings.local.json, any hook scripts you'll edit, the plugin registry. Codex: ~/.codex/AGENTS.md,
   config.toml, project .codex/hooks.json. For files the runtime constantly rewrites
   (~/.claude.json, etc.), record the backup timestamp alongside it.
   Create the backup directory **outside** any skill/plugin directory — placing it inside
   skills/ registers the backup as a duplicate skill and pollutes the listing (this has
   actually happened and had to be moved out immediately).
2. Prefer the official CLI for plugins. Claude: use `claude plugin list` to confirm the exact
   name@marketplace, then `claude plugin disable <name@marketplace>`. Codex: check whether an
   equivalent CLI command exists first, e.g. via `codex --help` — if it exists, use it; if not,
   fall back to editing config.toml directly per rule 3 below. Never delete a plugin folder
   directly, on either tool.
3. When editing config.toml (Codex) directly, preserve TOML syntax integrity: quote keys that
   contain dots or `@` (e.g. `[plugins."name@marketplace"]`), don't let blank lines or the next
   section header get mangled when removing a whole table, and **always re-parse the file with
   a TOML parser after editing** to confirm it's still syntactically valid
   (`python -c "import tomllib,sys; tomllib.load(open(sys.argv[1],'rb'))"` or equivalent). If
   parsing fails, treat the change as not applied, revert it, and report it as a failure —
   broken TOML can prevent the whole tool from starting.
4. For files containing non-ASCII text, never use shell append (>>) or a heredoc (there is
   a history of file corruption from this). Read → write the full content → re-read.
   **Note that re-reading only proves "it got written to the file."** Whether the runtime
   picks it up is a separate question — always do step 10 below for that.
5. Trimming agent descriptions means removing example blocks only — never delete the file,
   and preserve any routing language ("for a simple request, just use the skill directly").
6. If a disabled plugin's hook entry is still present (Claude: settings.json; Codex:
   config.toml's `[hooks.state.*]`), read what that hook script actually outputs before
   removing it. If it only emits a notice, remove it (after backup). If it also emits
   `permissionDecision`/`deny`/blocking logic, do not remove it — report it as "hook contains
   a guardrail — not removed." If you can't read the script, leave it and report it as
   unjudged. If plugin-specific env config remains, just list it as "dead config" — removing
   it is a separate approval item.
7. For CLAUDE.md/AGENTS.md content trimming, remove only the lines quoted in the
   "approved-line block" for that file. If that block is "none" or empty for a file, don't
   touch that file's content at all, and report that fact. Lines not in the block —
   especially user policy/preferences (language rules, publishing restrictions, security
   rules) — must not be judged; leave them as-is.
8. **When a cross-tool integration (canonical + junction conversion) is approved**: keep the
   approved side as canonical, delete the other side's real directory, then replace it with a
   junction (Windows: `mklink /J` or PowerShell `New-Item -ItemType Junction`) or symlink
   (Unix: `ln -s`). **Diff the two copies once more before deleting anything to confirm they're
   actually identical, and only back up the side you're about to remove.** After creating the
   link, verify both paths read correctly (read the first line of SKILL.md from each) before
   reporting it as applied.
9. Right before starting the apply, re-read the modification times of the target tools' core
   config files (Claude: CLAUDE.md, settings.json, settings.local.json, ~/.claude.json; Codex:
   AGENTS.md, config.toml), and compare against the "inventory-time snapshot" below. If even
   one differs, don't change anything — just report that fact and stop. It means another
   session is touching the same files.

   Inventory-time snapshot:
   [tool | file | size | modification time table]
10. For changes that affect runtime loading — MCP servers, plugins, hooks — don't stop at
    re-reading the file. On Claude, confirm with a new headless session's init event
    (references/runtime-verify.md). Codex doesn't have an equally-verified headless
    procedure — check the Codex section of runtime-verify.md first; if there's one, use it, if
    not, fall back to a file re-read plus asking the user for a direct smoke test, and report
    it honestly as "unverified (Codex)." Never write "applied" for something you couldn't
    confirm.

Final report (write it in the language the user has been using):
- Per-item handling and the mechanism used (CLI / config edit / junction conversion), and how to roll each one back
- Before/after size per file and verification result, broken out by tool
- Runtime verification result: for Claude, from the init event — mcp_servers status and
  loaded-tool count before/after. For Codex, whatever verification method applied, or
  "unverified (Codex)" if none did
- What couldn't be done (app-UI-managed items, etc.) and anything else you discovered
```

## What the main session does

1. Once the agent's completion report comes back, summarize the essentials for the user: what was done, backup location, how to roll back, and anything that needs manual handling.
2. Proceed to Phase 5 recording.
3. If the report contains a failure or partial failure, surface it as-is — don't hide it — and suggest how to respond.

## Rollback procedure (if the user wants to undo it)

- Plugins: on Claude, `claude plugin enable <name@marketplace>`. On Codex, if there's no equivalent CLI, restore the `[plugins.*]` entries from the backed-up config.toml.
- Files: copy the original back from the backup directory.
- Junction/symlink conversion: delete the link and copy the backed-up real directory back into place.
- The audit record (path chosen in Phase 0) should have a per-item rollback method for that run.
