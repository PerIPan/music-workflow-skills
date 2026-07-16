---
name: bass-transcribe
description: Use when the user has played bass (or another monophonic instrument) and wants the take transcribed — to a MIDI file, an Ableton Live clip, or a tab/chart. Default pipeline is CREPE (full model + viterbi) on the recorded audio; basic-pitch for double-stops; includes note segmentation, cleanup rules, and real-time plugin alternatives.
---

# Bass Transcribe — played take → MIDI / Live clip / chart

Default is the offline **CREPE** pipeline (validated: CREPE `full`+viterbi beats pyin on
bass and vocals). For in-Live plugin options (NeuralNote, Jam Origin) read
`references/realtime-options.md`.

## 1. Get the audio

- **User points at a file** — wav/mp3/aiff of the take. Mono preferred; DI cleaner than mic.
- **Record in Live** — audio track, arm, record the take. MCP **cannot export audio**:
  the user does File → Export, or point at the raw recording under the Set's
  `Samples/Recorded/` folder.
- Ask for (or detect) the take's **BPM** if the output will go into a Live clip.

## 2. Default pipeline — CREPE → MIDI

```python
import crepe, librosa, numpy as np, pretty_midi

y, sr = librosa.load(AUDIO, sr=16000, mono=True)
time, freq, conf, _ = crepe.predict(y, sr, model_capacity='full', viterbi=True, step_size=10)

CONF, MIN_LEN, GAP = 0.55, 0.08, 0.05   # confidence gate, min note s, merge gap s
midi_f = 69 + 12*np.log2(freq/440.0)
notes, cur = [], None
for t, m, c in zip(time, midi_f, conf):
    p = int(round(m)) if c >= CONF and np.isfinite(m) else None
    if cur and p == cur['p'] and t - cur['end'] <= GAP:
        cur['end'] = t
    else:
        if cur and cur['end'] - cur['start'] >= MIN_LEN:
            notes.append(cur)
        cur = {'p': p, 'start': t, 'end': t} if p is not None else None
if cur and cur['end'] - cur['start'] >= MIN_LEN:
    notes.append(cur)

pm = pretty_midi.PrettyMIDI()
inst = pretty_midi.Instrument(program=33)     # Electric Bass (finger)
for n in notes:
    if 26 <= n['p'] <= 67:                    # octave sanity: drop-D D1 to 24th-fret G4
        inst.notes.append(pretty_midi.Note(velocity=96, pitch=n['p'],
                                           start=n['start'], end=n['end']))
pm.instruments.append(inst)
pm.write(OUT_MID)
```

Tuning knobs: `CONF` up to 0.6–0.7 for noisy takes; `MIN_LEN` down to 0.05 for fast
lines; `step_size=10` ms is fine for bass.

## 3. Cleanup rules

- **Drop blips** < 80 ms (tracker flicker, fret noise).
- **Octave sanity**: 4-string bass ≈ MIDI 26–67 (drop-D D1 … 24th-fret G4). CREPE
  octave errors land a 5th/octave out — flag and correct outliers to the nearest
  in-range octave.
- **Legato-join** same-pitch notes split by < 50 ms gaps.
- **Ghost notes / slides** show as short low-confidence fragments — either drop (chart
  use) or keep (feel/groove analysis). Ask which the user wants.
- **Double-stops or chords played?** CREPE is monophonic and will pick one note — rerun
  with **basic-pitch** (`basic-pitch <out_dir> <audio> --save-midi`) for those passages.

## 4. Outputs

1. **`.mid` file** — the pipeline's direct product; drag into any DAW.
2. **Live clip** via the `ableton-mcp` skill: convert seconds → beats
   (`beats = sec * BPM / 60`), size the clip in **BARS** (round up to 1/2/4/8…), push
   with `add_notes_to_clip` in ≤140-note chunks (never two pushes to the same clip in
   parallel).
3. **Tab / chart** — bass tab or bar chart generation: chart craft lives in the
   `song-analysis` skill (`references/chart-and-lyrics.md`); pitch-class per half-bar
   aggregation as in its Phase 3.

## 5. Verify before declaring done

Report note count, pitch range, and duration vs. take length. Sanity signals: a bass
take yields roughly 1–4 notes/second; a pitch histogram dominated by 2–5 pitch classes
(the song's roots). Wildly more notes → lower `CONF` gate is letting flicker through;
wildly fewer → gate too high or the take is quieter than expected.

## Local environment (this machine)

- Python with crepe 0.0.16 + basic-pitch 0.4.0 + pretty_midi (verified 2026-07-16):
  `/Users/peripan/dev/abletonAI/audio-analysis/.venv-bp/bin/python`
- Prior art: `scripts/transcribe_bass_pyin.py` in the tooling root (pyin —
  superseded by CREPE).
