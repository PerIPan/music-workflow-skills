---
name: song-analysis
description: Use when a song recording has to become tempo, time signature, key, stems, a bass line, chords per bar, lyric timing, a drum-pattern read, or a chord+lyric chart for a band — including songs in odd or unknown meters.
---

# Song Analysis — recording → bars, chords, lyrics, chart

Song-agnostic pipeline, validated over many real projects (dream pop, Greek laiko, punk
reinterpretations, drone/devotional). Works for any song, genre, key or meter.

**References (read on demand):**
- `references/meter-detection.md` — how the meter sweep works, reading its output, calibration
- `references/chord-proposal.md` — the chord method, the major-bias trap, where it fails
- `references/chart-and-lyrics.md` — chart structure, the lyric-placement rules, HTML output
- `references/drum-pattern-analysis.md` — kick/snare pattern reading; optional ADTOF
- `references/modal-theory.md` — the 7 modes and the mode test, power chords, Byzantine ≠ Phrygian
- `references/lead-and-keys-extraction.md` — isolated guitar/piano lines via `htdemucs_6s`
- `references/environment-setup.md` — venvs, pinned versions, per-song folder layout

## Inputs

1. **Audio file** — mp3/wav of the song (full mix).
2. **Lyrics** — canonical text from an official source. Section labels (Verse, Chorus,
   Bridge…) come from this, not from the analyzer.

## Tool per step

| Step | Tool | Notes |
|---|---|---|
| Pulse (beats only) | **madmom** `DBNBeatTrackingProcessor` | No meter assumed |
| Meter, grouping, downbeat | **`scripts/detect_meter.py`** | Sweeps every cycle 2–25; odd meters |
| Key (melody's mode) | **madmom** `CNNKeyRecognitionProcessor` + bass-pedal check | Top-2 with probabilities — Trap 2 |
| Stems | **demucs `htdemucs_ft`** `-d mps` | `htdemucs_6s` only to isolate guitar/piano — never for bass |
| Bass → MIDI | **pyin** (`bass-transcribe` skill) | Root line, not chord quality. Not CREPE |
| Polyphonic parts → MIDI | **basic-pitch** | Floor at the instrument's range |
| Chords | **`scripts/chord_proposal.py`** | Chroma + bass root + slash relaxation |
| Lyrics + word timing | **`scripts/whisper_gated.py`** | mlx-whisper turbo, gated on the sung parts |
| Drum-pattern read | librosa band onsets (ADTOF optional) | see reference |
| Chart | Python → self-contained **HTML** | see reference |

Scripts run with the analysis venv (`<venv>/bin/python`); Whisper has its own venv.

## Phase 1 — Foundation (pulse + key, then meter)

### 1a. Pulse and key, WITHOUT assuming a meter

```python
from madmom.features.beats import RNNBeatProcessor, DBNBeatTrackingProcessor
from madmom.features.key import CNNKeyRecognitionProcessor, KEY_LABELS
import numpy as np

beat_times = DBNBeatTrackingProcessor(fps=100)(RNNBeatProcessor()(audio_path))  # no bars
pulse_bpm = 60.0 / float(np.median(np.diff(beat_times)))
probs = CNNKeyRecognitionProcessor()(audio_path)[0]    # 24 key probabilities
key_top2 = [(KEY_LABELS[i], round(float(probs[i]), 2)) for i in np.argsort(probs)[::-1][:2]]
```

**Never pass `beats_per_bar=(3, 4)`** — a constrained candidate list can't say "neither",
so it returns the least-bad option with full confidence and every bar count inherits it.

**Key: report the top two, then check the bass pedal.** The CNN beats chroma + Krumhansl
by ~20 MIREX points and fixes relative-major/minor flips, but it knows only 24
major/minor keys, and its probability is not a confidence on modal or drone material (a
Lydian track came out as the wrong key at p = 0.59). Take the pitch class the bass
sustains longest (duration-weighted, after Phase 3): if it disagrees, trust the pedal as
the tonic and name the mode with the mode test (`references/modal-theory.md`).

### 1b. Meter by sweeping every cycle length (after Phase 2, on the stems)

```bash
<venv>/bin/python scripts/detect_meter.py <song.mp3> --drums stems/<song>/drums.wav \
    --bass stems/<song>/bass.wav --other stems/<song>/other.wav \
    --foundation analysis/foundation.json --json analysis/meter.json
```

Folds band-limited onsets onto every period 2–25 and ranks by accent contrast. Always
pass `--bass` and `--other`: songs without a kit still carry the cycle in the bass and
harmony. It prints a consensus cycle with HIGH/LOW confidence and the downbeat, or
**INCONCLUSIVE** — then report the ambiguity and ask the user to count; never pick one.
A cycle of 8/16/24 is usually 4/4 with a phrase; a prime (7, 11, 13) is the meter; check
the tempo octave first. Details, output table and calibration:
`references/meter-detection.md`.

### Save `analysis/foundation.json`

`pulse_bpm`, `beat_times`, `beats_per_bar` (from 1b, **not** madmom), `pulse_unit` (4 if
the pulse is a quarter note, 8 if an eighth), `grouping` (the split from the two strongest
positions, e.g. `[6, 5]`; `[2, 2]` for 4/4), `downbeat_times`
(`beat_times[downbeat_pulse::cycle]` from `meter.json`), `num_bars`, `key` (top two),
`bar_bpm` (per bar: 60 / median inter-beat interval, pulse units) and `tempo_drift_pct`
((max − min) / median of `bar_bpm`).

**Cells.** Everything downstream (bass, chords, lyrics, chart) is keyed by `(bar, cell)`,
one cell per group in `grouping`: 4/4 → 2+2 (the familiar half-bars), 3/4 → one cell,
6/8 → 3+3, 11/8 as 6+5 → two unequal cells. Never split an odd bar at its midpoint.

**Sanity checks:** read `bar_bpm`, not one BPM — played music drifts, and above ~±3% a
single tempo misplaces notes by the end (`ableton-mcp` → "Timing"). Watch half/double time
on slow songs (60–90 BPM) — count along. `num_bars` should match
`duration ÷ (beats_per_bar × beat)`; a large mismatch means rubato, a wrong tempo octave,
or a wrong meter.

## Phase 2 — Stems

```bash
demucs -n htdemucs_ft -d mps -o stems <song.mp3>
# → stems/htdemucs_ft/<song>/{bass,drums,vocals,other}.wav
```

- **`-d mps` on Apple Silicon** — demucs 4.0.1 otherwise runs on the CPU (M3, 30 s clip:
  CPU 64.5 s, MPS 23.0 s). Meter-only runs need just `--two-stems=drums`.
- **Check the cache first** (`du -sh ~/.cache/torch/hub/checkpoints` for 4.0.1; 4.1.x uses
  the Hugging Face cache). `htdemucs_ft` is 4 × 84 MB; uncached, it downloads silently —
  ~100 min at 3 MB/min once — and piping through `tail` hides all progress.
- **Fast offline fallback:** `mlx-demucs` (plain htdemucs, not `_ft`; 28 s for a 4-minute
  track). Call its venv binary directly — `uv run mlx-demucs` re-resolves dependencies and
  hangs for 10+ minutes.
- **Quality check:** listen to `bass.wav` alone — piano/guitar bleed means separation
  struggled.

## Phase 3 — Bass → MIDI

**pyin** on `bass.wav` (code, cleanup rules and the octave cross-check are in the
`bass-transcribe` skill); basic-pitch only if the part is polyphonic. Then total each
pitch class's sounding time per `(bar, cell)` → `analysis/bass_per_cell.json`.

**Spell pitch classes from the key signature.** Flats for flat and neutral keys; sharps
for sharp keys — in F♯ minor a flat table writes the tonic `G♭m` and the dominant `D♭7`.

- Sub-0.5 s detections are noisy; ≥ 0.7 s sustained notes are usually right.
- Bass pedals, walks, sits on 3rds/5ths — it's a *clue* to the root, not the chord.
- **Bass enters late** in most songs: find the entry bar and ignore everything before it
  (stem bleed).

## Phase 4 — Lyric timing (Whisper on the vocals stem)

```bash
<whisper-venv>/bin/python scripts/whisper_gated.py stems/<song>/vocals.wav \
    [--language en] --out analysis/lyrics.json
```

It gates Whisper on where the stem is actually sung (RMS → `clip_timestamps`: long-form
lyric WER 22.9% → 20.7% and far fewer filler hallucinations, arXiv 2506.15514), sets
large-v3-turbo's word-alignment heads, and drops words whose *whole* span is silent —
Whisper often starts a sung word before the voice is audible, so filtering on start time
cuts real words. Force `--language` when detection wobbles (chant, non-English). Then drop
known hallucinations ("Thank you.", "Blah Blah", ".") and 3+ identical repeats. Skipping
the gate and leaning on `no_speech_threshold=0.8` instead can return nothing for a track
that has singing.

Map each word to a bar:

```python
def locate(t, downbeats, beats_per_bar):     # from foundation.json — never assume 4
    for i in range(len(downbeats)-1):
        if downbeats[i] <= t < downbeats[i+1]:
            return (i+1, (t - downbeats[i]) / (downbeats[i+1] - downbeats[i]) * beats_per_bar)
    return None
```

## Phase 5 — Sections (from lyrics + audio)

For each canonical lyric line, find its first bar via the word timings + `locate()`.
Section boundaries = where each labelled section's first line lands. Don't trust automatic
section detection (±1 bar off around bridges and outros); lyrics + word timing are far
more reliable.

## Phase 5b — Chord proposal

```bash
<venv>/bin/python scripts/chord_proposal.py --other stems/<song>/other.wav \
    --bass stems/<song>/bass.wav --foundation analysis/foundation.json \
    --bass-entry-bar <N> --out analysis/chord_proposal.json
```

Per cell: 24 triad templates scored on the harmonic stem's chroma, preferring the bass
note as root **unless that costs more than 15%** (then the bass is the 3rd or 5th — a
slash chord; this step alone took one track from 73.8% to 91.5%). Major bias is **0** and
never gated on the key; the script reports how many cells a 0.05 bias would flip, plus
each cell's margin over the runner-up. Many flips or near-ties = the quality call is
uncertain: say so. Method, measurements, failure modes: `references/chord-proposal.md`.

## Phases 6–9 — Chart

Read `references/chart-and-lyrics.md` before building the chart. Core invariants:
- One row per section; parallel sections get identical row splits.
- Chart bar = audio bar. A virtual bar only where the audio has none (e.g. a rubato hold
  the beat tracker skipped) — and mark it.
- Chord dict keyed by `(bar, cell)`.
- **Lyric phrases anchor at the chord they resolve INTO** (Rule 1 — the big one).
- Output: single self-contained HTML, print-friendly, harmonic-notes block at the bottom.

## Hard rules — the cardinal traps

### Trap 1 — A bass walk is one chord or two; the upper voicing decides

Bass moving within a bar (`C → A♭`) has two readings, and both are common: one held chord
over a moving bass (`Cm/A♭`, or a drone with a walking bass), or **two chords**
(`Cm → A♭`). The bass alone can't tell them apart, and a bass-constrained matcher follows
the bass, so it reports two chords either way. Look above the bass:
- **Re-attack** — a new voicing struck where the bass moves = two chords.
- **Register-pooled chroma** — pool chroma per cell in the chord instrument's register
  (high-pass above ~165 Hz). The pitch-class set changes with the bass = two chords; it
  stays put = one chord over a moving bass.

### Trap 2 — "Minor key" ≠ minor chords

Key estimators report the **melody's mode**, not chord quality. Many songs put major
triads under a minor melody — the bittersweet sound. Never propagate the key label to
chord quality; test each chord (major vs minor third, `chord-proposal.md`). Modal songs
often pivot between relative major and minor — label the key as a pair (`E♭ / Cm`).

### Trap 3 — The meter you never tested for looks like no meter at all

An odd cycle folded onto the wrong period gives a **flat** profile, not a low one — 11
folded onto 2, 3, 4 or 6 smears to near-uniform. Uniform contrast everywhere means the
right period hasn't been tested yet, never "no time signature". Assume odd meters are
live (`references/meter-detection.md`).

**Verify with a player.** Automated signals are wrong ~30% of the time on modal-mixture
songs. A musician who knows the song is ground truth — plan a verification pass before
declaring the chart done.

## Lessons learned

1. Trust the user's ear over any analyzer. Ask them to count — a player's count settles
   in seconds what a sweep can only rank.
2. Never hand an analyzer a candidate list it can't say "none of these" to — a constrained
   `beats_per_bar` and a key-gated major bias both produced confident wrong answers that
   survived every downstream check.
3. Chord-recognition tools are starting points, never ground truth.
4. Whisper timing is precise; musical placement is not strict timing (Rule 1).
5. `basic-pitch` duplicates notes at exact octaves and invents low-register content the
   stem doesn't contain. Floor it at the instrument's range (C3 for a piano out of
   `other.wav`) before pushing anything to Ableton.
6. Each chart correction touches ~3 places (chord dict, row layout, cascading lyrics).
7. Mirror parallel sections visually; overlay section-boundary pickups in the same cell.

## Local environment (this machine)

- Tooling root: `~/dev/abletonAI/audio-analysis/` — `.venv-bp/bin/python` (madmom,
  librosa, basic-pitch, crepe, pretty_midi; runs this skill's scripts);
  `.venv-demucs/bin/python` (demucs); `.venv-adtof` (ADTOF);
  `mlx-demucs/.venv/bin/mlx-demucs` (batches).
- **Whisper is not in any of those venvs:** `~/mlx-openai-whisper/bin/python`. Only
  `mlx-community/whisper-large-v3-turbo` is cached.
- Older helpers in the tooling root (`analyze_chords.py` etc.) predate this skill's
  scripts — `analyze_chords.py` still has a 0.05 major bias. Prefer `scripts/`.
