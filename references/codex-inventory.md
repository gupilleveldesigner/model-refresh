# Codex CLI inventory procedure

Run this during Phase 1 when `~/.codex` exists. Codex's config schema can change between versions — if a section name below isn't there, trust the actual file over this document.

## File layout

- **`~/.codex/AGENTS.md`** — the global router equivalent to Claude's CLAUDE.md. Apply the same line-by-line standard (can the model figure this out on its own).
- **`~/.codex/config.toml`** — for Claude this would be `settings.json` + `settings.local.json` + `~/.claude.json` combined into one file. Read these sections:
  - `[mcp_servers.<name>]` — MCP server registration. Equivalent to Claude's `mcpServers`.
  - `[projects.'<absolute-path>']` — per-project settings. Path spelling can diverge by case or slash direction (`c:\users\...` vs `C:\Users\...`), the same way Claude's duplicate-project-key problem works — if the same project shows up under two spellings, don't fix only one side without proving which one is actually live.
  - `[marketplaces.<name>]` — plugin marketplace registrations.
  - `[plugins."<name>@<marketplace>"]` — active plugins. Equivalent to Claude's `enabledPlugins`.
  - `[hooks.state.'<key>']` — registered hooks. Two key shapes exist: a project-local hook points at a project file, shaped like `'<project-absolute-path>\.codex\hooks.json:<event>:0:0'`; a plugin-provided hook declares its owning plugin, shaped like `"<plugin>@<marketplace>:hooks/<file>:<event>:0:0"`. **The actual hook script lives at the file this key points to** (`hooks/<file>` is relative to the plugin's install path; project hooks live at `<project>\.codex\hooks.json`) — same as Claude, open the script and enumerate its output kinds before judging.
  - `[agents.<name>]` — custom agent definitions.
  - `[features]`, `[desktop]`, `[tui.*]`, `[shell_environment_policy.*]`, `[windows]`, etc. — behavior settings. Mostly a matter of taste ("user judgment"), unless an item is clearly a corrective for an older model's mistake, in which case apply criterion 1.
- **`~/.codex/skills/<name>/`** — the skill directory equivalent to Claude's `~/.claude/skills/`. Some have only `SKILL.md`; others also have `agents/openai.yaml` (a Codex-facing manifest with display name and default prompt).
- **`~/.codex/MEMORY.md`** — Codex's persistent memory file. Plays the same role as Claude's memory directory (`~/.claude/projects/<slug>/memory/`) but at a different location and format. Check it too when looking for actual-use evidence.
- **`~/.codex/skills-archived/`** (if present) — history of past disables. Worth a look in Phase 0.

## Collection caveats

- **`auth.json`, `cap_sid`, session-state files (`.codex-global-state.json`, etc.) are out of scope.** They're auth/runtime state, not instructions — don't touch or read them.
- config.toml is **TOML**. Editing or removing a section requires respecting its syntax (quoting rules, arrays, nested tables) — see `references/apply-protocol.md` for the safety rules.
- Check whether there's an official CLI command for toggling plugins on/off, e.g. via `codex --help`. As of this writing there is no confirmed equivalent — verify whether one exists, and if not, state in the report that editing config.toml directly is the only available path.
- If `[hooks.state.*]` has a plugin-owned hook, disabling that plugin later can leave this hook entry as dead config — same trap as on the Claude side.

## Checking whether a skill is a junction/symlink or the real thing

If `~/.codex/skills/<name>` is a junction, that's a cross-tool duplication judgment target, not an independent deletion candidate for this tool alone — record the link target and hand it off to Phase 2's "cross-tool duplication" judgment. Checking method is the same as `references/claude-inventory.md` (`LinkType` / `[ -L ]`).
