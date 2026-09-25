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
| `bass-transcribe` | You played bass — transcribe the take to MIDI, a Live clip, or a tab/chart (CREPE pipeline) |

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
files loaded on demand. Machine-specific paths are isolated in a
"Local environment (this machine)" section per skill — everything else is generic.
