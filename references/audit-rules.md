# Judgment rules

## Base standard

Ask each item, in order:

1. **Can the model figure this out on its own?** — Things visible from project files (build commands, folder structure), general best practices, "do it this way" procedural mandates are deletion candidates. Things the model can't know (project-specific constraints, team decisions, a tool choice that differs from the default) are kept.
2. **Is there evidence of actual use?** — Look for real usage traces in: the memory directory (`~/.claude/projects/<project-slug>/memory/`), the project's own session records if any (e.g. a vault's `.session-memory/index.jsonl`), `~/.claude/projects/` transcripts, and the current conversation. It's a deletion candidate only when there's no evidence **and** the model could do it unaided (both conditions must hold). Distinguish "couldn't find evidence" from "no evidence exists" — a seasonal item (e.g., a cover-letter skill only used during hiring season) is expected to show no recent trace, so if its purpose implies periodic use, classify it as "needs user judgment," not a deletion candidate.
3. **Does it distort behavior?** — Even at low token cost, a hard rule enforced on every turn ("always do X before responding," including via hook injection) carries a high distortion cost. This matters more than token count as a judgment basis.

   Because this is the most important criterion, **it also needs the strictest evidence bar.** You wouldn't claim a token number without asking for `/context` — don't claim an injection frequency by impression either. Only write frequency claims like "it fires every time" or "it shows up on every Bash call" in the report when you can point to one of:
   - An unconditional code path confirmed by reading the hook script body (confirmed by the *absence* of branching, cooldowns, or dedup)
   - An actual throttle/state file — frameworks often leave dedup records in a state directory (real example: `<framework-state-dir>/sessions/<session-id>/*-throttle.json` held the last-emitted time per message). If this file exists, it's direct evidence *against* "every time"
   - An injection count you can actually count in the current transcript

   Without evidence, write "injection confirmed, **frequency unmeasured**." Real incident: a report claimed "it fires on every Bash call," but the plugin actually had a 5-minute per-message cooldown, and the report had to be publicly corrected. An overstated frequency claim can lead a user to disable a hook's guardrail output along with the noise.

## Category-specific things to look for

- **Hooks (SessionStart · UserPromptSubmit · PreToolUse)**: the unit of judgment isn't "the hook script" — it's **each distinct kind of output that hook produces**. It's common for one script to emit both (a) a notice injected every time and (b) an actual guardrail like `permissionDecision: "deny"`. If a notice is annoying and you disable the whole hook, the guardrail dies with it, and the user has no way to notice (real case: a delegation block and a model-routing check lived in the same script as the notice). So always **open the script body**, enumerate the kinds of output, and judge from there. A rule table planted by a framework is still a typical deletion candidate.

  Before disabling, always consider **narrowing** first. Narrowing techniques that have actually worked:
  - **The trigger condition is wrong** → fix the condition list. Example: a documentation vault where the hook's file-extension list includes `.md`/`.txt`/`.rst`/`.mdx`, so a code-workflow notice fires every time a markdown file is read → remove the document extensions from the list.
  - **A partial-disable token the framework already provides** → check the hook script body and the plugin docs for environment variables first. Many frameworks already have variables for "turn off just this hook" and "just lower the frequency" (real example: a targeted token shaped like `<PREFIX>_SKIP_HOOKS=<hook-name>` and a frequency-control variable shaped like `<PREFIX>_..._COOLDOWN_MS` — variable names differ per framework, so search the script directly for `process.env`/`os.environ` references). Putting it in the project-local `.claude/settings.local.json`'s `env` scopes it to that project only.

    Verification caveat: settings' `env` **is passed to hook subprocesses but not to Bash tool subprocesses.** Printing it with `printenv` from Bash and getting nothing back is inconclusive, not proof it isn't applied — to actually check, add a temporary hook that echoes the value, then remove it right away.
  - **A path/name-based false positive** → narrow the condition, or turn it off only for that project. Example: a notice like "start the wiki workflow immediately" injected on every prompt just because the path contains the word "Wiki."

  Disabling a hook entirely is the last resort, only **after confirming** there's no narrowing option. The report should always state "of what this hook outputs, what dies and what survives."

  Note: partial-disable tokens belong to that plugin. If the plugin is later disabled entirely, that config becomes **dead config** — when approving a plugin disable, add its plugin-specific env config to the cleanup list too.
- **Plugins**: an orchestration framework that injects dozens of skills plus MCP tools plus agents all at once (the rigid, step-enforcing kind) should be re-evaluated as a whole. A single-purpose plugin that provides a genuinely used feature leans toward keeping.
- **Agent descriptions**: the `<example>` conversation blocks in a description are always-loaded pure cost — a trimming candidate. Routing language like "use the skill directly for a simple request" is kept. Never delete the agent file itself.
- **Skill list**: skill bodies are on-demand and cheap. The cost is the always-resident description list. If the same role has two copies (a plugin version and a user/project version), keep only the canonical one.
- **Deferred MCP tools**: the schema is free until loaded, but the name list plus each server's per-server usage notes are injected every session. Judge connectors this project has no use for.
- **CLAUDE.md (structure)**: the ideal is a short router plus detail delegated to on-demand files. A block planted by a framework (wrapped in marker comments) shares that framework's fate. **Hand-editing inside the markers (`<!-- X:START -->` … `<!-- X:END -->`) gets reverted the next time that framework's install/update script runs.** So there are only two stable ways to handle this block: (1) disable the framework itself and remove the block entirely, or (2) shrink the block's content through config the framework provides. Never report a hand-edit inside the markers as "applied" — if you did edit it, note in the audit record that "it reverts on the next install-script run." If long, rarely-used content is sitting resident, suggest moving it to a skill or on-demand file (placement priority: prompt → CLAUDE.md → skill → MCP).
- **CLAUDE.md (content, line by line)**: apply the base standard to each line. Deletion candidates — anything visible from project files (build commands, folder-structure descriptions), general best practices, procedural mandates that exist to correct old-model mistakes. Keep — user policy/preference the model can't derive (language rules, publishing restrictions, security rules), a tool/path choice that differs from the default, project-specific constraints. Keep policy/preference lines regardless of length — the standard isn't "short, so harmless," it's "can't be derived, so keep." Present deletion proposals in the report line by line, with the original text quoted.
- **Status line / HUD**: zero context tokens. Not a performance judgment — a taste matter → classify as "needs user judgment."
- **Consumption habits (/usage)**: separately from resident context, audit habits that burn through the usage window — excessive subagent spawning, long sessions left uncompacted, high-fanout spawn workflows. Report this as a habit-correction recommendation, not a file deletion.
- **Applied scope (global vs. project)**: **where** to turn off a deletion candidate is a separate decision from the judgment itself. Skills, agents, hooks, and MCP are assets shared across projects, so "not used in this project" doesn't mean "safe to turn off globally." Real incident: in one audit, eight skills specific to a different project were nearly proposed as global-disable candidates just because "not used in the current project." Disabling them globally would have silently broken that other project, and the user wouldn't have known until reopening it.

  Judgment order:
  1. Is this item used by exactly one project, or several — grep the skill/agent name across other projects' CLAUDE.md, config, and session records too.
  2. If several, **narrow it to project-local.** Project-scoped mechanisms: `skillOverrides` in the project's `.claude/settings.local.json` (skills), `env` in the same file (hook tokens), `disabledMcpServers` under that project's key in `~/.claude.json` (MCP).
  3. Only disable globally once you've confirmed "not used by any project."

  Every deletion-candidate line in the report must state its **scope** — a deletion proposal without a scope can't be approved.

- **Not just subtraction — addition too**: the other half of the audit — if something the model can't derive (a team-specific constraint, a non-default tool choice, a service that must stay running) isn't documented, propose filling that gap with a CLAUDE.md line or a new skill. The goal of a setup isn't minimalism for its own sake — it's "the minimum the agent needs to work without further explanation."

## Traps (drawn from real incidents)

- **Apparent duplication ≠ real duplication**: a Discord user-skill and a Discord plugin looked like duplicates, but the skill actually depended on the plugin's MCP gateway — a complementary relationship. Verification procedure: grep the deletion candidate's name, MCP tool name, and executable path across every other skill body (the full SKILL.md), agent definitions, and hook/status-line commands in settings. If even one reference turns up, treat it as a dependency and judge them together (delete both or keep both). Even zero grep hits doesn't rule out a runtime dependency (a script calling another skill's batch file, etc.) — for items with a batch/shell script, read that script's contents too.
- **Mistaking a non-plugin for a plugin**: something installed directly into the skills directory won't appear in the `claude plugin` registry. The disable method is different.
- **A framework's own doctor has a blind spot**: a diagnostic tool a framework provides **about itself** cannot judge whether the framework should exist at all. Don't use its output as grounds for keeping that framework. This does not apply to Claude Code's built-in `/doctor` or an audit record left by another session — those often surface a layer this skill can't see (actual hook contents, project scope, runtime state), so actively look for and read them in Phase 0.
- **Quantitative claims from a video/blog**: cite secondhand-commentary numbers (cost, reduction percentage, etc.) as a reference, but don't treat them as established fact.

## Classification output

| Class | Condition | Handling |
|---|---|---|
| Deletion candidate | (criterion 1 applies) OR (criterion 2: no evidence **and** model can do it alone) OR (criterion 3 applies) — AND passes the dependency-check procedure | Phase 3 report → Phase 4 on approval |
| Keep | Unique information, confirmed real-use dependency, well-structured | State the reason for keeping in the report |
| Needs user judgment | Not controllable from a file (app-UI connectors, etc.), a matter of taste | Provide where to turn it off + decision-relevant material (connectors get the alive/needs-auth/dead three-way split from `references/runtime-verify.md`) |
| User-rejected | Proposed in a prior audit or recent session, but the user explicitly declined | Do not re-propose. Record in the audit record's "rejected items" with date and the rejection wording. Re-raise only with new grounds when circumstances have changed |
