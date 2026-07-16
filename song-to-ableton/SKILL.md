---
name: song-to-ableton
description: Use when taking an existing song end-to-end — analyze a recording (bars, key, chords, lyrics, drum logic) and rebuild or reinterpret it in Ableton Live. Orchestrates the song-analysis, ableton-mcp, ableton-arrangement, and bass-transcribe skills. Ask first whether the user wants analysis, Ableton building, or both.
---

# Song → Ableton (end-to-end orchestrator)

```
  existing audio ──▶  A. ANALYSIS                      ──▶  C. HANDOFF      ──▶  B. ABLETON (MCP)
                      stems · bars/BPM/key · chords          bars + chords +      build/reinterpret:
                      · bass MIDI · lyrics · drum read        drum logic           tempo · clips · MIDI
                                                                                   · devices · scenes · mix
```

**ASK FIRST:** "Do you want song analysis, Ableton building, or both?" Then route only
to what's needed.

> **GOLDEN RULE: reason in BARS, never seconds.** Every length and position is a bar
> count (1, 2, 4, 8, 16, 32…). Convert any "first 16 seconds" to bars and stay in bars.

## Routing

| Need | Skill |
|---|---|
| Analyze the recording (tempo/bars, stems, chords, lyrics, drum read, chart) | `song-analysis` |
| Drive Live — tracks, clips, notes, devices, mixing; connection issues | `ableton-mcp` |
| Arrangement craft — sections, bass/drum patterns, FX chains, dynamics | `ableton-arrangement` |
| The user plays bass (or another mono instrument) and wants it as MIDI | `bass-transcribe` |

## The handoff (analysis output → Ableton input)

| Analysis output | Use in Ableton |
|---|---|
| BPM + `num_bars` | `set_tempo`; size clips in bars (32-bar song = 128 beats) |
| `chord_proposal` per bar/half | chord clips on a synth/keys track, or a chart for a live band |
| bass MIDI (root line) | reference clip — or **leave the bass slot empty** for a live bassist |
| drum-pattern read | match the original's kick/snare logic (or `generate_drum_pattern`); never impose a rock backbeat on a non-rock song |
| key/mode | scale + voicings (mind major-triads-under-minor-melody — Trap 2 in `song-analysis`) |
| section map | scenes (jam) or arrangement sections; mirror parallel sections |

**Reinterpreting in a new genre:** keep the **harmonic + rhythmic skeleton** (chords per
bar, original drum logic, section lengths) from analysis; change instrumentation and
energy in Ableton. Analysis says *what the song is*; the build decides *how it sounds*.

## Quickstart

1. Drop `<song>.mp3` + `lyrics.txt` in a song folder.
2. Run the `song-analysis` pipeline: stems (htdemucs_ft) → foundation (bars/BPM/key) →
   bass via CREPE → chords via chroma+bass-root → Whisper on the vocals stem.
3. Open Ableton; verify the MCP connection (`health_check` — see `ableton-mcp`).
4. Build, e.g.: "At <BPM> in <key>, build a Session scene with these chords per bar
   <chord_proposal>, a drum pattern matching <kick/snare logic>, and leave the bass slot
   empty for me to play."

## Troubleshooting (route, don't debug here)

- Noisy bass MIDI → CREPE not basic-pitch; bass bleed → `htdemucs_ft` + suppress
  pre-bass-entry bars; too few snares detected → `delta≈0.15`, un-normalized envelope
  (all in `song-analysis`).
- Can't connect / tools missing / device errors → `ableton-mcp`
  references/troubleshooting.md.

## Local environment (this machine)

- Analysis tooling + venvs: `/Users/peripan/dev/abletonAI/audio-analysis/`
  (`.venv-bp`, `.venv-demucs`); song folders live next to it in
  `/Users/peripan/dev/abletonAI/`.
- Ableton MCP configured via that project's `.mcp.json`.
