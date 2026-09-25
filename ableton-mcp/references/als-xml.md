# Reading Arrangement content from the `.als`

Read this when you need Arrangement-view clips, names or notes — the MCP exposes Session
clips only.

A `.als` Set is **gzipped XML**. `get_session_path` gives the file.

```bash
gunzip -c "/path/to/Set.als" > /tmp/set.xml     # 5–10 MB of XML: grep, never cat
grep -nE "<MidiClip Id|<CurrentStart|<CurrentEnd|<UserName|<EffectiveName|<MidiKey" /tmp/set.xml
```

Key elements:
- `<MidiTrack>` — one per MIDI track; its `<EffectiveName Value=…>` near the top is the
  track name.
- `<MidiClip Time="<beat>">` — one Arrangement clip; `<CurrentStart>`/`<CurrentEnd>` give
  its span in beats; `<UserName>`/`<EffectiveName>` its name (often the chords — see hard
  rule 13 in the skill).
- `<KeyTracks>` → `<KeyTrack>` per pitch: `<MidiKey Value=…>` is the MIDI pitch, and
  `<MidiNoteEvent Time=… Duration=… Velocity=…>` the notes (times relative to the clip,
  in beats).

Bars per chord from a labelled clip: clip length in beats ÷ number of chords in the label
gives a first guess; where the lowest note changes breaks the tie.

**Caveat:** the file is the **last saved** state, not what's in Live now. Users often edit
without saving — treat the `.als` as a starting reference, and the MCP reads (Session) or
a screenshot as current truth.
