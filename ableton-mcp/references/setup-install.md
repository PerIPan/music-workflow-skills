# AbletonMCP — one-time setup

Read this only when installing or re-installing the AbletonMCP connection.

## What you're installing (two halves)

Both halves must run and **must come from the same source/version** (a mismatched Remote
Script and server can fail to talk):

1. **A Remote Script inside Ableton** ("AbletonMCP" control surface) — opens a **TCP
   socket on port 9877** that Live listens on. *Most setup failures are a forgotten,
   mis-named, or unselected Remote Script.*
2. **The MCP server** (`ableton-mcp`, Python) — your MCP client (Claude Code, Claude
   Desktop, Cursor) launches it; it relays commands to the Remote Script.

```
Claude  <->  MCP server (Python)  <->  Ableton Remote Script  <->  Live (LOM)
                            port 9877 TCP
```

Repo: <https://github.com/ahujasid/ableton-mcp> (150+ tools; count varies by build).

## Prerequisites

- Ableton Live 10+ (any edition; Pedal/Amp devices are Suite-only)
- A working MCP client (Claude Desktop / Claude Code / Cursor)
- Python 3.8+, git (or download repo ZIP)
- [uv](https://astral.sh/uv): macOS `brew install uv`; Windows `pip install uv`

## 1. Install the Remote Script (the step people miss)

0. `git clone https://github.com/ahujasid/ableton-mcp.git` — the script is
   `AbletonMCP_Remote_Script/__init__.py`.
1. Locate Live's MIDI Remote Scripts folder:
   - **macOS:** right-click Ableton Live → Show Package Contents →
     `Contents/App-Resources/MIDI Remote Scripts/` — or
     `~/Library/Preferences/Ableton/Live XX/User Remote Scripts`
     (Live 11+ also accepts `~/Music/Ableton/User Library/Remote Scripts/`)
   - **Windows:** `C:\Users\[You]\AppData\Roaming\Ableton\Live x.x.x\Preferences\User Remote Scripts`
     — or `C:\ProgramData\Ableton\Live XX\Resources\MIDI Remote Scripts\`
2. Create a folder named **exactly `AbletonMCP`** (case-sensitive) and put `__init__.py`
   inside.
3. **Restart Ableton Live** — it scans Remote Scripts only at launch.
4. Settings → Link, Tempo & MIDI → free Control Surface dropdown → **"AbletonMCP"**;
   set that row's Input and Output to **None**.

## 2. Configure the MCP client

**Claude Code** — `.mcp.json` at project root (merge into existing `mcpServers`):
```json
{ "mcpServers": {
    "ableton": { "type": "stdio", "command": "uvx", "args": ["ableton-mcp"], "env": {} }
} }
```

**Claude Desktop / Cursor** — merge into the MCP config
(`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):
```json
{ "mcpServers": { "AbletonMCP": { "command": "uvx", "args": ["ableton-mcp"] } } }
```

Restart the client. Notes:
- `uvx` not on PATH → use its absolute path (e.g. `~/.local/bin/uvx`).
- To run a local checkout (guarantees both halves match):
  `"args": ["--from", "/path/to/ableton-mcp", "ableton-mcp"]`.
- Server fails with an `mcp` import error → pin: add `"--with", "mcp[cli]==1.4.1"`
  before `"ableton-mcp"` in args.

## 3. Verify

A **Set** is a Live project (`.als`); the start screen is not a Set.

1. File → New Live Set; bring Live to the foreground.
2. Run `health_check` (Claude Code: `ToolSearch select:mcp__ableton__health_check` first).
3. Success = a real response, e.g. `get_session_info` → `{"tempo": 120.0, "track_count": 2, …}`.
4. Smoke-test write access: `create_midi_track` → `get_session_info` shows track count +1.

To avoid a permission prompt on every call in Claude Code, add to `.claude/settings.json`:
```json
{ "permissions": { "allow": ["mcp__ableton__*"] } }
```
