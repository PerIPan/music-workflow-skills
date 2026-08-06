---
name: song-analysis
description: Use when analyzing a song recording — extracting tempo/downbeats/key, separating stems, transcribing bass to MIDI, identifying chords per bar, timing lyrics, reading drum patterns, or producing a chord+lyric chart for a band. Covers madmom, demucs (htdemucs_ft), CREPE, basic-pitch, chroma chord proposal, and Whisper word timing.
---

# Song Analysis — recording → bars, chords, lyrics, chart

Song-agnostic pipeline, validated over many real projects (Mitski "A Pearl", Greek
laiko, punk reinterpretations). Works for any song, genre, or key.

**References (read on demand):**
- `references/environment-setup.md` — first-time venv install + per-song folder layout
- `references/chart-and-lyrics.md` — chart structure, the 6 lyric-placement rules, HTML output
- `references/drum-pattern-analysis.md` — kick/snare pattern reading from the drums stem
- `references/modal-theory.md` — power-chord shorthand, mode tables, Byzantine ≠ Phrygian

## Inputs

1. **Audio file** — mp3/wav of the song (full mix).
2. **Lyrics** — canonical text from an official source. Section labels (Verse, Chorus,
   Bridge…) come from this, not from the analyzer.

## Tool per step

| Step | Tool | Why |
|---|---|---|
| Tempo / downbeats / bars | **madmom** downbeat tracker | Most accurate at slow & mid tempos |
| Key (melodic mode) | **librosa** chroma + Krumhansl | Signal only — see Trap 2 |
| Stem separation | **demucs `htdemucs_ft`** (4-stem) | Cleanest bass; NEVER `htdemucs_6s` (bleeds piano/guitar into bass) |
| Bass → MIDI | **CREPE** (`full` + viterbi) | Monophonic tracker; gives the ROOT, not quality |
| Polyphonic parts → MIDI | **basic-pitch** | Piano/guitar/pads, double-stops |
| Chords | **chroma + bass-root + major-bias** | 99% top-1 validated (see Phase 5b) |
| Lyrics + word timing | **mlx-whisper `large-v3`** (Apple Silicon) or openai-whisper | Word timestamps, hallucination-filterable |
| Drum-pattern read | **librosa** band-limited onsets | see reference |
| Chart output | Python → self-contained **HTML** | see reference |

## Phase 1 — Foundation (downbeats + key)

```python
from madmom.features.downbeats import RNNDownBeatProcessor, DBNDownBeatTrackingProcessor
import librosa, numpy as np
from collections import Counter

act = RNNDownBeatProcessor()(audio_path)
beats = DBNDownBeatTrackingProcessor(beats_per_bar=(3,4), fps=100)(act)  # (time, pos-in-bar)
beat_times = beats[:,0].tolist()
beat_positions = beats[:,1].astype(int).tolist()
downbeat_times = [t for t,p in zip(beat_times, beat_positions) if p == 1]
bpm = float(60.0 / np.median(np.diff(beat_times)))
# Key via librosa chroma_cqt mean + Krumhansl correlation → melodic mode ONLY (Trap 2)
```

Save as `analysis/foundation.json`: `bpm`, `beats_per_bar`, `beat_times`,
`downbeat_times`, `num_bars` (= downbeat count), `key`.

**Sanity checks:** BPM stable (no jumps); watch half/double-time on slow songs (60–90
BPM) — count along the audio; downbeat spacing roughly constant.

## Phase 2 — Stems

```bash
demucs -n htdemucs_ft -o stems <song.mp3>
# → stems/htdemucs_ft/<song>/{bass,drums,vocals,other}.wav   (~50s for 2:30 on M3 Pro)
```

**CHECK THE CACHE FIRST — `du -sh ~/.cache/torch/hub/checkpoints`.** `htdemucs_ft` is a
bag of 4 models (~320 MB). If it isn't cached, that command silently downloads for as long
as your connection takes — measured at ~3 MB/min (≈100 min) on 2026-08-06 — and shows no
progress at all if you pipe it through `tail`. Don't assume it's cached because you used it
on a previous song.

**Fast offline fallback (Apple Silicon):** plain htdemucs via MLX, weights already local —
28 s for a 4-minute track (8.7× realtime):

```bash
<audio-analysis>/mlx-demucs/.venv/bin/mlx-demucs <song.mp3> -o stems_mlx -v
```

Call the venv binary **directly**. `uv run mlx-demucs` re-resolves dependencies over the
network and hangs 10+ min even though the venv is already complete. The MLX port is within
0.03% of the PyTorch htdemucs reference, so it's a sound basis for chords and bass; re-run
on `_ft` later only if quality looks marginal. Note its README lists `htdemucs_ft` as a
supported model, but only plain htdemucs weights ship in `weights/`.

**Quality check:** listen to `bass.wav` alone — piano/guitar bleed means separation
struggled; try plain `htdemucs` as fallback.

## Phase 3 — Bass → MIDI

Default: **CREPE** on `bass.wav` (monophonic → root line). For the CREPE→MIDI code and
cleanup rules, use the `bass-transcribe` skill — same pipeline. Use **basic-pitch** only
if the part is polyphonic.

Then aggregate per (bar, half): for each half-bar, total each pitch class's overlapping
note duration and rank → `analysis/bass_per_bh.json`.

**Spell pitch classes from the key signature, not from a fixed table.** Flat spelling
(C, D♭, D, E♭ … B♭, B) is the right default for flat and neutral keys — it matches how
guitarists read pop/indie charts. But applying it blindly in a **sharp key produces
nonsense**: Black Pumas' "Colors" is in three sharps, where the flat table renders the
tonic as `G♭m` instead of `F♯m`, and the dominant as `D♭7` instead of `C♯7`. Rule: if the
key signature has sharps, use sharp spelling (C♯, D♯, F♯, G♯, A♯); if flats or none, use
flats.

**Pitfalls:**
- Sub-0.5 s detections are noisy; ≥0.7 s sustained notes are usually right.
- Bass doesn't always play roots — it pedals, walks, sits on 3rds/5ths. Bass note is a
  *clue*; annotate in chart only when bass ≠ chord root.
- **Bass enters late** in most songs. Find the bass-entry bar (first clearly audible bar)
  and suppress all bass-derived annotations before it — pre-entry content is stem bleed.

## Phase 4 — Lyric timing (Whisper on the VOCALS STEM)

Whisper is far more accurate on isolated vocals than the full mix.

Settings that work: model `large-v3` (`mlx-community/whisper-large-v3-mlx` on Apple
Silicon); `word_timestamps=True`; `no_speech_threshold=0.8`;
`condition_on_previous_text=False` (avoids hallucination drift); post-filter known
hallucinations ("Thank you.", "Blah Blah", ".") and 3+ identical repeats.

Map each word's start time to (bar, beat):

```python
def locate(t, downbeats, bpb=4):
    for i in range(len(downbeats)-1):
        if downbeats[i] <= t < downbeats[i+1]:
            return (i+1, (t - downbeats[i]) / (downbeats[i+1] - downbeats[i]) * bpb)
    return None
```

## Phase 5 — Sections (manual, from lyrics + audio)

For each canonical lyric line, find its first bar via Whisper + `locate()`. Section
boundaries = where each labeled section's first line lands. **Don't trust automatic
section detection** (librosa recurrence segmentation is ±1 bar off around bridges/outros);
the lyrics + word timing are far more reliable.

## Phase 5b — Chord proposal (chroma + bass-root + major-bias)

Per half-bar, on the `other.wav` stem (everything harmonic except bass/drums/vocals).
Validated: **99% top-1, 100% top-3** on modal-major dream pop.

1. **Chroma**: average `librosa.feature.chroma_cqt(other.wav)` over the cell's frames.
2. **Score all 24 triad templates** (12 maj + 12 min, binary root/3rd/5th, sum-normalized)
   by dot product with the cell chroma.
3. **Bass-root constraint** (only when `bar >= BASS_ENTRY_BAR`): if one bass pitch class
   has ≥0.5 s sustain in the cell, restrict candidates to the maj+min triads on that root —
   **but relax it on slash chords** (see below).
4. **Major-bias**: if top template is minor and same-root major is within margin
   `MAJOR_BIAS_MARGIN`, swap. ("Default major; fall back to minor only if it clearly
   clashes.") **The 0.05 default is genre-specific — see the warning below.**

### 3b. Slash-chord relaxation (REQUIRED — validated +17.7 points)

The bass-root constraint assumes the bass note *is* the root. On a slash chord the bass
plays the 3rd or 5th, and constraining to it forces a guaranteed-wrong answer. Fix:

```python
allc = sorted(all 24 templates by score, desc)
con  = [c for c in allc if root_of(c) == bass_pc]
use_constrained = con and con[0].score >= RELAX_FACTOR * allc[0].score   # 0.85
```

If the best chord rooted on the bass note scores materially worse than the unconstrained
best, the bass is a non-root chord tone — drop the constraint and let chroma decide.
`RELAX_FACTOR = 0.85`; anything ≥0.85 behaves identically, 0.0 = old behaviour.

Measured on Black Pumas "Colors" (C♯7/F, bass on E♯): the old rule mislabelled every
C♯7 cell as `Fm` (14 misses, a third of all errors). With relaxation the pipeline
recovers `C♯` with F in the bass unaided — **73.8% → 91.5%** root+quality.

### ⚠️ `MAJOR_BIAS_MARGIN` is the single highest-leverage parameter

The shipped default `0.05` is tuned for **modal-major dream pop**. On an honest-minor
song it flips the tonic minor to major on nearly every cell. Measured on "Colors"
(F♯m tonic), same audio, only this parameter changed:

| `MAJOR_BIAS_MARGIN` | root+quality |
|---|---|
| 0.05 (shipped default) | **27.4%** |
| 0.02 | 54.9% |
| 0.0 | **73.8%** |

A 46-point swing. **Set it to 0 for any song whose tonic is minor**, and only raise it
for modal-major material. The "99% top-1" figure quoted below was measured on
modal-major dream pop and does not transfer across genres — re-tune per song.
5. **Emit top-3** per cell + `beat3_re_attack` flag from onset detection on the same stem
   (corroborating evidence only — noisy).

Why it works: bass-MIDI gives root but not quality; chroma gives quality but confuses
4th/5th-related roots; major-bias cancels the minor-key bias. Any one signal alone ≈
70–90%; the combination hits 99%. Errors concentrate in pre-bass-entry bars,
sustained-organ smear, and extended chords (expand templates with 7th/sus for jazz/R&B).

Per-song tuning: `MAJOR_BIAS_MARGIN` (raise for modal-major genres, lower/zero for
honest-minor folk), `BASS_ENTRY_BAR`, template set.

## Phases 6–9 — Chart

Read `references/chart-and-lyrics.md` before building the chart. Core invariants:
- One row per section; parallel sections get identical row splits.
- Chart bar = audio bar (no virtual bars).
- Chord dict keyed by `(bar, half)`.
- **Lyric phrases anchor at the chord they resolve INTO** (Rule 1 — the big one).
- Output: single self-contained HTML, print-friendly, harmonic-notes block at bottom.

## Hard rules — the two cardinal traps

Both appeared in production and required a working musician to correct.

### Trap 1 — Bass walk ≠ slash chord

Bass moving across a bar's halves (`C → A♭`) has two readings: (1) one held chord with
moving bass (`Cm/A♭`) or (2) **two chords** (`Cm → A♭`). Automated tools bias to (1);
many indie/folk/dreampop songs are doing (2).

**Discriminating test:** listen for a **re-attack on beat 3** in `other.wav`. New
voicing struck on beat 3 = two chords. Bass-only move under sustained voicing = slash.
Bass movement alone is a suspicion signal, never the decision.

### Trap 2 — "Minor key" ≠ minor chords

Key estimators report the **melody's mode** (the PCP is melody-dominant), not chord
quality. Many songs put **major triads under a minor melody** — that's the bittersweet
sound. Default each chord to major, then verify: play root+maj3+5 against the melody; if
the maj-3rd fights the melody's ♭3, go minor. Never propagate the key label to chord
quality. Also: many modal songs pivot between relative major and minor — label the key as
a pair (`E♭ / Cm`) when both centers appear.

**Verify with a player.** All automated signals are wrong ~30% of the time on
modal-mixture songs. A musician who knows the song is ground truth — plan a verification
pass before declaring the chart done.

## Lessons learned

1. `htdemucs_ft`, never `htdemucs_6s` — 6-stem bleeds piano/guitar into bass MIDI.
2. Trust the user's ear over any analyzer disagreement.
3. Chart bar = audio bar.
4. Whisper timing is precise; musical placement is not strict timing (Rule 1).
5. Bass walks mid-bar = chord changes → key by `(bar, half)`.
6. Chord-recognition tools are starting points, never ground truth.
7. Each chart correction touches ~3 places (chord dict, row layout, cascading lyrics).
8. Mirror parallel sections visually.
9. Section-boundary pickups: overlay in the same cell, don't displace.

## Local environment (this machine)

- Tooling root: `/Users/peripan/dev/abletonAI/audio-analysis/`
- `.venv-bp/bin/python` — madmom, librosa, basic-pitch, crepe, pretty_midi, mlx-whisper
  (verified 2026-07-16). `.venv-demucs/bin/python` — demucs.
- Existing helpers: `analyze_chords.py` (Phase 5b), `analyze_chord_onsets.py`,
  `scripts/whisper_vocals.py` (Phase 4), chart generators `gen_*.py` per song folder.
- Source docs (read-only): `WORKFLOW-song-analysis.md` in the tooling root.
