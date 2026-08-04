# Claude Code inventory procedure

Run this during Phase 1 when `~/.claude` exists.

File-based inventory (collected directly by the model): `enabledPlugins`/`hooks`/`statusLine` from `~/.claude/settings.json`, `~/.claude/settings.local.json`, `~/.claude.json` (per-project `disabledMcpServers`/`mcpServers` live **here**, not in settings.json), `~/.claude/CLAUDE.md`, `~/.claude/agents/*.md` (including description length), the `~/.claude/skills/` listing, project `.claude/` and CLAUDE.md, the actual hook scripts of active plugins, and `claude plugin list` output. **Record size and modification time for every file** (used in Phase 0.5).

**Verify project keys in `~/.claude.json` against the actual file.** The same folder can exist as both a backslash key (`C:\Users\...\X`) and a forward-slash key (`C:/Users/.../X`), and you cannot tell which one the runtime reads just by looking at the file. If both exist, list **both** in the inventory, and prove which one is actually live using the procedure in `references/runtime-verify.md`. Skipping this check and fixing only one key means a change reported as "applied and verified (re-parsed the JSON)" actually had zero effect — there's a real incident where roughly 180 MCP tools the user meant to turn off stayed loaded for hours because of exactly this.

**Check whether a skill is a junction/symlink or the real thing.** If `~/.claude/skills/<name>` is a junction (pointing to a canonical copy elsewhere), that's a cross-tool duplication judgment target, not an independent deletion candidate for this tool alone — record the link target and hand it off to Phase 2's "cross-tool duplication" judgment.

Checking link status on Windows: if `Get-Item <path>`'s `LinkType` is `Junction`, it's a link; empty means it's a real directory. On Unix-like systems, use `[ -L <path> ]`.
