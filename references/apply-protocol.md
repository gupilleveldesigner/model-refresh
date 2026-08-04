# Apply protocol (Phase 4)

Delegate only approved items to a background agent (general-purpose). The main session keeps the conversation going.

## Agent prompt template

Fill approved items into the skeleton below and hand it off. Brackets mark substitution points.

```
Clean up a Claude Code setup. Environment: [OS], home directory: [absolute path to ~/.claude]

Work (approved items only):
[For each approved group of deletion candidates: what, and by what method]

CLAUDE.md approved-line block:
[Verbatim quote of the deletion lines approved in Phase 3. If CLAUDE.md trimming wasn't approved, write "none"]

Do not touch:
[Everything classified as "keep" + any group not approved by the user + project files + memory directories]

Safety rules:
1. Before modifying anything, create a backup directory [~/.claude/backup-refresh-YYYYMMDD]
   and copy every file you're about to modify (~/.claude/CLAUDE.md, the agents folder,
   settings.json, settings.local.json, ~/.claude.json, project .claude/settings.json and
   settings.local.json, any hook scripts you'll edit, the plugin registry). Because the
   runtime constantly rewrites ~/.claude.json, record the backup timestamp alongside it.
   Create the backup directory **outside** any skill/plugin directory — placing it inside
   ~/.claude/skills/ registers the backup as a duplicate skill and pollutes the listing.
2. Prefer the official CLI for plugins: use `claude plugin list` to confirm the exact
   name@marketplace, then `claude plugin disable <name@marketplace>`. Only edit the config
   file (enabled:false) when the CLI isn't available. Never delete a plugin folder directly.
3. For files containing non-ASCII text, never use shell append (>>) or a heredoc (there is
   a history of file corruption from this). Read → write the full content → re-read.
   **Note that re-reading only proves "it got written to the file."** Whether the runtime
   picks it up is a separate question — always do step 8 below for that.
4. Trimming agent descriptions means removing example blocks only — never delete the file,
   and preserve any routing language ("for a simple request, just use the skill directly").
5. If a disabled plugin's hook entry is still present in settings.json, read what that hook
   script actually outputs before removing it. If it only emits a notice, remove it (after
   backup). If it also emits `permissionDecision`/`deny`/blocking logic, do not remove it —
   report it as "hook contains a guardrail — not removed." If you can't read the script,
   leave it and report it as unjudged. If plugin-specific env config remains (variables
   prefixed for that framework), just list it as "dead config" — removing it is a separate
   approval item.
6. For CLAUDE.md content trimming, remove only the lines quoted in the "CLAUDE.md
   approved-line block." If that block is "none" or empty, don't touch CLAUDE.md content at
   all, and report that fact. Lines not in the block — especially user policy/preferences
   (language rules, publishing restrictions, security rules) — must not be judged; leave
   them as-is.
7. Right before starting the apply, re-read the modification times of
   ~/.claude/CLAUDE.md, settings.json, settings.local.json, and ~/.claude.json, and compare
   against the "inventory-time snapshot" below. If even one differs, don't change anything —
   just report that fact and stop. It means another session is touching the same files.

   Inventory-time snapshot:
   [file | size | modification time table]
8. For changes that affect runtime loading — MCP servers, plugins, hooks — don't stop at
   re-reading the file. Confirm with a new headless session's init event
   (references/runtime-verify.md). Put the confirmation result directly in the report. If you
   couldn't confirm it, write "unverified" — never write "applied."

Final report (write it in the language the user has been using):
- Per-item handling and the mechanism used (CLI vs. config edit), and how to roll each one back
- Before/after size per file and verification result
- Runtime verification result (from the init event): mcp_servers status and loaded-tool count
  before/after. Mark unverified items explicitly as "unverified"
- What couldn't be done (app-UI-managed items, etc.) and anything else you discovered
```

## What the main session does

1. Once the agent's completion report comes back, summarize the essentials for the user: what was done, backup location, how to roll back, and anything that needs manual handling.
2. Proceed to Phase 5 recording.
3. If the report contains a failure or partial failure, surface it as-is — don't hide it — and suggest how to respond.

## Rollback procedure (if the user wants to undo it)

- Plugins: `claude plugin enable <name@marketplace>`
- Files: copy the original back from the backup directory
- The audit record (`~/.claude/audits/model-refresh/`) should have a per-item rollback method for that run.
