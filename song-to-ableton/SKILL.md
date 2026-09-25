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
| `pulse_bpm`, `pulse_unit`, `beats_per_bar`, `num_bars` | `set_tempo(pulse_bpm × 4 / pulse_unit)` — Live's tempo counts quarter notes. One bar = `beats_per_bar × 4 / pulse_unit` Live beats (4/4 → 4, 7/8 → 3.5, 11/8 → 5.5); size clips in whole bars |
| `chord_proposal` per `(bar, cell)` | chord clips on a synth/keys track, or a chart for a live band |
| `bar_bpm`, `tempo_drift_pct` | above ~±3% drift, place notes through the beat grid, not one BPM (`ableton-mcp` → "Timing") |
| bass MIDI (root line) | reference clip — or **leave the bass slot empty** for a live bassist |
| drum-pattern read | match the original's kick/snare logic (or `generate_drum_pattern`); never impose a rock backbeat on a non-rock song |
| key/mode | scale + voicings (mind major-triads-under-minor-melody — Trap 2 in `song-analysis`) |
| section map | scenes (jam) or arrangement sections; mirror parallel sections |

**Reinterpreting in a new genre:** keep the **harmonic + rhythmic skeleton** (chords per
bar, original drum logic, section lengths) from analysis; change instrumentation and
energy in Ableton. Analysis says *what the song is*; the build decides *how it sounds*.

## Quickstart

1. Drop `<song>.mp3` + `lyrics.txt` in a song folder.
2. Run the `song-analysis` pipeline: stems (htdemucs_ft) → pulse + key → **meter sweep
   (`detect_meter.py`; never assume 4/4)** → bass via pyin → chords via chroma+bass-root
   → Whisper on the vocals stem.
3. Open Ableton; verify the MCP connection (`health_check` — see `ableton-mcp`).
4. Build, e.g.: "At <BPM> in <key>, build a Session scene with these chords per bar
   <chord_proposal>, a drum pattern matching <kick/snare logic>, and leave the bass slot
   empty for me to play."

## Troubleshooting (route, don't debug here)

- Noisy bass MIDI → pyin, not basic-pitch or CREPE; bass bleed → `htdemucs_ft` + suppress
  pre-bass-entry bars; too few snares detected → `delta≈0.15`, un-normalized envelope
  (all in `song-analysis`).
- Can't connect / tools missing / device errors → `ableton-mcp`
  references/troubleshooting.md.

## Local environment (this machine)

- Analysis tooling + venvs: `/Users/peripan/dev/abletonAI/audio-analysis/`
  (`.venv-bp`, `.venv-demucs`); song folders live next to it in
  `/Users/peripan/dev/abletonAI/`.
- Ableton MCP configured via that project's `.mcp.json`.
