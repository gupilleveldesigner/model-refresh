# Runtime verification — did you ask the session, not just the file

Everything in this document is **Claude Code-specific**. For Codex CLI, check the "Codex-side runtime verification" section at the bottom first — there isn't an equally-verified procedure yet.

## Why re-reading the file isn't enough

If you consider a setup change verified once "I re-read the file and the content is correct," you've only confirmed bytes. Nothing guarantees the runtime actually reads that key from that file.

Real incident: `~/.claude.json` had the same folder present as both a backslash key and a forward-slash key, and a `disabledMcpServers` change was written to the backslash key while the session read the forward-slash key. A change reported as "applied and verified (re-parsed the JSON)" had zero effect for hours, and roughly 180 MCP tools kept loading the whole time. Re-parsing proved nothing.

File verification answers **did the intended bytes go in**; runtime verification answers **does the session actually reflect it**. Different questions.

## Procedure — headless init event

With the working directory set to the project you're verifying, start a session:

```
claude -p "ok" --output-format stream-json --verbose
```

The first line's `type: "system"`, `subtype: "init"` event is that session's actual state. Read from it:

- `mcp_servers` — per-server `status`. Distinguishes `connected` / `disabled` / `needs-auth` / `pending`. If a server you turned off shows `disabled`, it applied; if it's still alive, it didn't.
- `tools` — the actual list of loaded tool names. The count difference before/after is the only real measurement of a "name list" reduction.
- `slash_commands` — whether a plugin disable took effect.

Run this **once before and once after** the change, and record both results side by side. Without two snapshots, any claim like "N fewer tools" is just an estimate.

Caution: the verification session's working directory *is* the applied scope. An item turned off only for one project will still show up alive when you launch from a different directory — that's expected, and it's itself evidence the scope landed as intended.

## Resolving duplicate project keys

If the same folder appears under two spellings under `projects` in `~/.claude.json`:

1. List both keys in the inventory.
2. Put the change in only one of them, and use an init event to prove which one takes effect.
3. Treat the one that takes effect as canonical. **Do not delete the other key** — there may be an execution path that uses the other spelling, and the runtime rewrites this file constantly anyway. Note in the audit record: "this project has two keys, canonical spelling is <X>."

Writing the same value into both keys is also a valid fix. Whichever one gets read, the result is the same, so you can apply it safely without resolving which one is canonical.

## Judging whether a connector is alive or dead

**Disconnecting** a connector is still app-UI territory, so "needs user judgment" is the right class — but the decision-relevant material you hand the user should be measured, not assumed.

Don't use `claude mcp list`'s "Connected" label as your evidence — a server with expired auth or a dead endpoint can still show Connected. Real measurement: Drive/Calendar/n8n all showed Connected in `claude mcp list`, but the init event showed `needs-auth` for them, the only tools they exposed were `authenticate`/`complete_authentication`, and one of those endpoints returned HTTP 404.

Classify into three states based on the init event, and report them:

| State | Decision material |
|---|---|
| Alive | Real functional tools are loaded. Confirm actual-use evidence separately |
| Needs auth | `needs-auth`, or the only exposed tools are `authenticate`/`complete_authentication` — **connected but unusable.** Either re-authenticate or disconnect |
| Dead | Connection failed / endpoint error. Just taking up space in the name list — recommend disconnecting |

## Don't overstate name-list savings

A deferred MCP tool's schema isn't loaded until it's called. Turning off a connector actually reduces the **tool name list and each server's usage notes** — not the entire "MCP tools (deferred)" figure in `/context`. Don't carry that figure over as expected savings. The honest claims are "the name count dropped by N" (before/after init-event comparison) and "a layer nobody uses disappeared from the list, which simplifies routing."

## Codex-side runtime verification

**Honestly, as of this writing it hasn't been confirmed whether Codex CLI has a procedure equivalent to Claude's headless init event.** Don't invent a specific command name here — instead, approach it in this order:

1. Check `codex --help` and its subcommands' `--help` for a headless/non-interactive mode or an option that dumps session state as JSON. If one exists, look in that output for fields corresponding to loaded MCP servers, plugins, and active hooks, and use it the same way as Claude's init event (before/after comparison). If you find it, add the method to this document so the next audit can reuse it.
2. If no such mechanism turns up, drop verification to two fallback steps:
   - **Re-parse the file**: re-read config.toml, confirm it still parses as valid TOML, and confirm the intended section is actually gone/changed. This only proves "the intended bytes made it into the file" — it's not a guarantee the runtime reads it.
   - **Ask the user for a smoke test**: ask the user to open a fresh Codex session and directly confirm whether the given MCP server/plugin/hook is off (or on). Point out specifically what to look for (e.g. "does the `<server-name>` MCP tool still show up in a new session").
3. Either way, honestly record it in the report and audit record as **"unverified (Codex, no headless verification method)."** Don't upgrade it to "applied" — this is exactly to avoid repeating, on the Codex side, the same mistake that happened on the Claude side when trusting a file re-read alone led to reporting "verified" while roughly 180 MCP tools stayed loaded for hours.

If a reliable headless verification method for Codex is confirmed in the future, replace this section with that procedure and update the "unverified (Codex)" labeling rule in Phase 4/apply-protocol.md accordingly.
