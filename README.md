# music-workflow-skills

Claude Code skills for a full music-production workflow: analyze real recordings
(tempo, key, stems, chords, lyrics, drum logic), transcribe played bass takes, and
build or reinterpret songs in Ableton Live over MCP.

Derived from working `WORKFLOW-*.md` guides validated on real song projects
(dream-pop analysis, an 11/4 punk reinterpretation of a Byzantine hymn, Greek laiko analysis, and others).

## Skills

| Skill | Use when |
|---|---|
| `song-analysis` | Turn a recording into bars/BPM/key, stems, bass MIDI, per-bar chords, word-timed lyrics, a band-ready chord+lyric chart |
| `ableton-mcp` | Drive Ableton Live via the AbletonMCP server — tracks, clips, MIDI, devices, mixing; all the gotchas and hard limits |
| `ableton-arrangement` | Compose/arrange a full song in Live — section design, bass pattern palette, drum conventions, FX chains |
| `song-to-ableton` | End-to-end orchestrator: analyze a song, then rebuild/reinterpret it in Live (routes to the other skills) |
| `bass-transcribe` | You played bass — transcribe the take to MIDI, a Live clip, or a tab/chart (pyin; CREPE for vocals) |

## Install

```bash
git clone https://github.com/PerIPan/music-workflow-skills.git
cd music-workflow-skills
for s in song-analysis ableton-mcp ableton-arrangement song-to-ableton bass-transcribe; do
  ln -sfn "$PWD/$s" ~/.claude/skills/$s
done
```

Restart Claude Code; the five skills appear in the skill listing.

## Layout

Each skill: a lean `SKILL.md` (triggers + core rules) and, where needed, `references/`
files loaded on demand, `scripts/` the skill runs, and `tests/` for those scripts.
Machine-specific paths are isolated in a "Local environment (this machine)" section per
skill (written against `~`) — everything else is generic.

Scripts:
- `song-analysis/scripts/foundation.py` — pulse + key, then the meter fields; asks instead of guessing
- `song-analysis/scripts/bass_notes.py` / `mode_test.py` — bass line, tonic from the bass, mode by characteristic degrees
- `song-analysis/scripts/align_lyrics.py` — canonical lyrics aligned to Whisper's word times → sections
- `song-analysis/scripts/validate_artifacts.py` — checks the hand-offs between phases
- `song-analysis/bench/run_bench.py` — scores everything against local ground truth
- `song-analysis/scripts/detect_meter.py` — meter by sweeping every cycle 2–25 (odd meters)
- `song-analysis/scripts/lv_chords.py` — chords with 7ths/inversions (lv-chordia) on the bar/cell grid
- `song-analysis/scripts/chord_proposal.py` — triad cross-check: slash relaxation, flip count
- `song-analysis/scripts/whisper_gated.py` — lyric word timing gated on the sung parts
- `ableton-mcp/scripts/push_notes.py` — bulk note push over Live's TCP socket

Tests run offline on synthetic audio or a mock Live socket:

```bash
<analysis-venv>/bin/python song-analysis/tests/test_detect_meter.py
<analysis-venv>/bin/python song-analysis/tests/test_chord_proposal.py
<analysis-venv>/bin/python song-analysis/tests/test_mode_test.py
python3 song-analysis/tests/test_foundation.py
python3 song-analysis/tests/test_align_lyrics.py
python3 ableton-mcp/tests/test_push_notes.py
```

Third-party tools the skills point to (ADTOF, madmom's models, demucs weights) keep their
own licences — several are non-commercial — and are installed, never copied here.

## License

MIT — see `LICENSE`.
