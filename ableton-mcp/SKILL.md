---
name: ableton-mcp
description: Use when controlling Ableton Live through the AbletonMCP server — creating tracks/clips/scenes, pushing MIDI notes, loading instruments or effects, setting device parameters, mixing, automation, or debugging the Live connection. Contains the hard limits and gotchas (note chunking, browser URIs, EQ Eight formulas, index shifts).
---

# Ableton Live via MCP

Claude drives a live Ableton Set through the AbletonMCP server (jpoindexter fork v2.0.0,
128 tools, all prefixed `mcp__ableton__`). Limits below are for this fork.

**References (read on demand):**
- `references/setup-install.md` — first-time install (Remote Script + server + verify)
- `references/troubleshooting.md` — connection failures, tool errors

For arrangement *craft* (section design, bass/drum patterns, FX chains) use the
`ableton-arrangement` skill; this skill is the mechanics and the gotchas.

## Mental model

- **Live and stateful.** Every call mutates the open Set immediately. No preview/dry-run.
  Undo is Live's own Cmd/Ctrl-Z.
- **Single session.** Controls one Ableton instance — the frontmost open Set. No diffing
  two Sets, no background operation. Two clients on one Live collide; work sequentially.
- **No autosave.** Claude can't save/open/new a Set — the USER Cmd-S's. After a Set
  switch, the server re-attaches to the new frontmost Set.
- **Deferred tools (Claude Code).** Load schemas before first use:
  `ToolSearch select:mcp__ableton__<name>`.
- **Reason in BARS, never seconds.** Sizes and positions are bar counts; convert
  everything to bars up front.

## Tool map

| Area | Representative tools |
|---|---|
| Transport | start/stop_playback, start/stop_recording, set_tempo, set_metronome, jump_to_time, capture_midi |
| Tracks | create_midi/audio/group_track, set_track_name/volume/pan/mute/solo/arm/color, set_track_input/output_routing, delete/duplicate_track, freeze/flatten |
| Clips | create/delete/duplicate/fire/stop_clip, set_clip_name/color/loop/gain/pitch, get_clip_notes |
| MIDI notes | add_notes_to_clip, remove_notes (range), remove_all_notes, transpose_notes, quantize_clip_notes, humanize_clip_timing/velocity |
| Devices / FX | search_browser, load_instrument_or_effect, get/set_device_parameter, toggle/delete_device, move_device_left/right, get_rack_chains |
| Scenes | create/delete/duplicate/fire_scene, set_scene_name/color, get_all_scenes |
| Mixing | set_send_level, get/set_return_volume/pan, set_master_volume/pan |
| Automation | get/set/clear_clip_automation, toggle_session_record, set_overdub |
| AI helpers | get_scale_notes, generate_drum_pattern, generate_bassline |

Most tools take `(track_index, clip_index)` — both **0-based** (Live's UI is 1-based:
"track 3" in the UI = index 2).

## Capabilities vs hard limits (all observed in testing)

**Reachable:** Session-view clip CRUD + MIDI editing, track/scene CRUD, device loading +
any device parameter on regular tracks, transport, mixing/sends, clip automation,
humanize, generative helpers.

**Not reachable — plan around:**
- ❌ Effects on the **Master track** — user adds limiter/EQ manually.
- ❌ **Stamping clips into Arrangement** — only real-time recording reaches Arrangement
  (and session-fire→arrangement-record produced an empty arrangement). Bounce loops via
  **Resample** into a session audio clip, or drag manually.
- ❌ **Firing an empty slot to record** — "click empty slot to record" is UI-only.
- ❌ **Render/export audio** — user does File → Export.
- ❌ **Return-track device parameters** — rejected ("Track index out of range"). Use
  set_return_volume/pan, or move the FX to a regular track.
- ⚠️ **Per-clip mute** — no clean toggle; `set_clip_gain` 0 (reversible) or UI Deactivate.
- ⚠️ **Follow Actions** unreachable — use launch quantization for count-ins/progressions.
- ⚠️ **`set_clip_automation` "Volume"** works on simple instrument tracks; rack-based
  tracks (drum racks, amp racks) often reject it → fall back to per-note velocity or a
  Utility device.
- ⚠️ **No visual feedback** — no screenshot tool. Workaround: macOS `screencapture` +
  Read the PNG.

## Hard rules (gotchas that bite)

1. **Load with `load_instrument_or_effect`**, not `load_item_to_track` (errors "Unknown
   command"). URIs are HTML-encoded: `query:AudioFx#EQ%20Eight`.
   ⚠️ **Its success message lies about the device list** — it returns
   `"Loaded instrument ... Devices on track:"` with the list *empty* even when the load
   worked. Don't retry on the strength of that; confirm with `get_track_info(track_index)`
   and read the `devices` array.
2. **Instruments/presets live under the `sounds` browser category**, not `instruments`
   (returns nothing). Pianos: `query:Sounds#Piano & Keys`; guitars:
   `query:Sounds#Guitar & Plucked`. Use `search_browser(query, category="sounds")`.
   Search matches **literal preset names**, so instrument nicknames miss: `"Rhodes"`
   returns nothing, `"Electric Piano"` finds *Electric Piano Daze*. Search the generic
   name, not the iconic one.
3. **Chunk note pushes ≤140 notes** per `add_notes_to_clip` (larger has failed silently).
   **Never two pushes to the same clip in one parallel batch** — they race. Sequential
   per clip; parallelize only across different clips.
4. **Reading a big clip can exceed the response token limit.** Generate notes in a
   script → save JSON → push from that. Don't round-trip 500 notes through a read.
5. **`remove_notes(from_time, time_span, from_pitch, pitch_span)` for surgical edits** —
   prefer over `remove_all_notes`. **Always assume the user hand-edited the clip** —
   read or remove-by-range rather than wiping.
6. **Effects load at the END of the chain.** Build in order or reorder with
   `move_device_left/right`.
7. **EQ Eight freq is normalized 0–1:** `value = log10(freq/20) / 3` (1 kHz ≈ 0.566,
   250 Hz ≈ 0.366, 130 Hz ≈ 0.271). Band N (A-set) param indices: On `4+(N-1)*10`, Type
   `5+…`, Freq `6+…`, Gain `7+…`, Q `8+…`. Filter types: 0=HP48 1=HP12 2=LowShelf 3=Bell
   4=Notch 5=HighShelf 6=LP12 7=LP48.
8. **Distortion:** `Overdrive` — Drive/Tone/Dry-Wet on 0–100. `Saturator` —
   Drive/Output/Dry-Wet on 0–1, Type 0–7 (hard curve = fuzz). `Pedal`/`Amp` are
   Suite-only — Saturator/Overdrive are the universal fallback.
9. **Creating a track/scene at a low index shifts everything after it.** Re-check indices
   (`get_session_info`) or append at the end (`index = -1`).
10. **Humanize in layers** — `humanize_clip_velocity(~0.08)` + `humanize_clip_timing(~0.04)`;
    apply twice if it still sounds programmed.

## Session-jam patterns (song-agnostic)

- **One scene per feel/groove**; launching a scene starts all its clips bar-quantized.
- **Shared click track** (Simpler + clave at one pitch), a click clip per scene; mute to
  toggle.
- **A REC audio track per live instrument** — armed, monitored, for takes.
- **A muted NOTES track** whose clip *names* carry tips/roadmaps.
- **Count-in without Follow Actions:** click-only clip + 1–2-bar launch quantization;
  fire the groove during the count bar, it drops on the next downbeat.
- **Odd meters via clip length, not global signature:** 5/4 = 5-beat clips, 7/8 =
  3.5-beat clips — same length for every clip in the scene **including the click**.
- **Whole song in one scene (through-composed):** full-song-length clips per track with
  an energy arc; **leave a track empty for a live player** (e.g. no bass clip for a
  bassist).
- **Label everything:** chords/patterns in `set_clip_name`, matching clip colors,
  paste-ready "Edit Info Text" blocks for the user.

### Working method that scales

Generate notes in a script → save JSON → push in ≤140-note chunks (deterministic,
reviewable, revertible). High-pass synths/keys so a live bass owns the lows. Test one
section, get direction, then propagate.

## Local environment (this machine)

- `.mcp.json` already configured in `/Users/peripan/dev/abletonAI/` (server `ableton` via
  `uvx --from <that dir>/ableton-mcp --with mcp[cli]==1.4.1 ableton-mcp`); Remote Script
  from the same checkout installed.
- Recording session output to audio: empty-slot record needs a UI click — use Resample
  workflow instead.
- Source doc (read-only): `/Users/peripan/dev/abletonAI/audio-analysis/WORKFLOW-ableton-mcp.md`.
