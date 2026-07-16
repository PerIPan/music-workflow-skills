# AbletonMCP — troubleshooting

## Nothing happens / "could not connect" — work through in order

1. **Is a Set open and frontmost?** Live's start screen isn't a Set (File → New Live Set).
2. **Is "AbletonMCP" selected** as a Control Surface (Settings → Link, Tempo & MIDI)? If
   the script was added while Live was open, **restart Live** (scans only at launch).
3. **Remote Script installed correctly?** Folder named **exactly** `AbletonMCP` with
   `__init__.py` inside. Missing from the dropdown → check Ableton's **Log.txt** for load
   errors.
4. **Did the MCP server launch?** Check the client's MCP logs. Failed on an `mcp` import →
   add the `--with mcp[cli]==1.4.1` pin (see setup-install.md).
5. **Port conflict:** nothing else may use **TCP 9877**; restart both client and Live.

## Other failures

- **Tools "not found" in Claude Code** — they're deferred; load first with
  `ToolSearch select:mcp__ableton__<name>`.
- **A load/parameter call errors** — confirm `load_instrument_or_effect` with a
  `sounds`-category URI, and the right device index (instrument is usually device 0;
  added FX append after it).
- **Edits land on the wrong track** — indices are 0-based and an earlier insert may have
  shifted them. Re-run `get_session_info`.
- **Timeouts on big requests** — break into smaller steps; give Live time to process.
- **Set switched mid-session** — the server re-attaches to the new frontmost Set
  automatically; re-read session info before continuing.
