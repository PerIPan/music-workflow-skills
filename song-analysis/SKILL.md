---
name: song-analysis
description: Use when a song recording has to become tempo, time signature, key, stems, a bass line, chords per bar, lyric timing, a drum-pattern read, or a chord+lyric chart for a band — including songs in odd or unknown meters.
---

# Song Analysis — recording → bars, chords, lyrics, chart

Song-agnostic pipeline, validated over many real projects (dream pop, Greek laiko, punk
reinterpretations, drone/devotional). Works for any song, genre, key or meter.

**References (read on demand):**
- `references/meter-detection.md` — how the meter sweep works, reading its output, calibration
- `references/stems.md` — separation options, speeds, cache, quality checks
- `references/chord-proposal.md` — chord benchmark, the triad cross-check, the major-bias trap
- `references/chart-and-lyrics.md` — chart structure, the lyric-placement rules, HTML output
- `references/drum-pattern-analysis.md` — kick/snare pattern reading; optional ADTOF
- `references/modal-theory.md` — the 7 modes and the mode test, power chords, Byzantine ≠ Phrygian
- `references/lead-and-keys-extraction.md` — isolated guitar/piano lines via `htdemucs_6s`
- `references/environment-setup.md` — venvs, pinned versions, folder layout, this machine

## Inputs

1. **Audio file** — mp3/wav of the song (full mix).
2. **Lyrics** — canonical text from an official source. Section labels (Verse, Chorus,
   Bridge…) come from this, not from the analyzer.

## Tool per step

| Phase | Tool | Output |
|---|---|---|
| 1 Pulse + key | **`scripts/foundation.py pulse`** (madmom beats + CNN key) | `foundation.json` (step 1) |
| 2 Stems | **demucs `htdemucs_ft -d mps`** | `stems/htdemucs_ft/<song>/` |
| 3 Meter | **`scripts/detect_meter.py`** → **`scripts/foundation.py meter`** | `meter.json`, `foundation.json` (step 2) |
| 4 Bass → MIDI | **pyin** (`bass-transcribe` skill) | `bass.mid`, `bass_per_cell.json` |
| 5 Lyrics | **`scripts/whisper_gated.py`** | `lyrics.json` |
| 6 Sections | lyrics + word timing (as_seg may suggest) | section map |
| 7 Chords | **`scripts/lv_chords.py`**, cross-checked by **`scripts/chord_proposal.py`** | `chords_lv.json`, `chord_proposal.json` |
| 8 Chart | Python → self-contained **HTML** | chart |

`<venv>` = the analysis venv; Whisper and lv-chordia have their own
(`references/environment-setup.md`). Below, `ST=stems/htdemucs_ft/<song>`.

## Phase 1 — Pulse and key (no meter assumed)

```bash
<venv>/bin/python scripts/foundation.py pulse <song.mp3> --out analysis/foundation.json
```

Tracks beats with **no bar assumption** — never pass `beats_per_bar=(3, 4)`: a constrained
candidate list can't say "neither", so it returns the least-bad option with full
confidence and every bar count inherits it. Writes `pulse_bpm`, `beat_times` and
`key_top2`.

**Key: the top two are the melody's key, not the tonic.** The madmom CNN beats chroma +
Krumhansl by ~20 MIREX points and fixes relative-major/minor flips, but knows only 24
major/minor keys, and its probability is not a confidence on modal or drone material (a
Lydian track came out as the wrong key at p = 0.59). After Phase 4, take the pitch class
the bass sustains longest: if it disagrees, trust the pedal as the tonic and name the mode
with the mode test (`references/modal-theory.md`).

## Phase 2 — Stems

```bash
demucs -n htdemucs_ft -d mps -o stems <song.mp3>     # → $ST/{bass,drums,vocals,other}.wav
```

`-d mps` on Apple Silicon (otherwise CPU, ~3× slower). **Check the model cache first** —
uncached, `htdemucs_ft` downloads 4 × 84 MB silently. Listen to `bass.wav` alone: piano or
guitar in it means separation struggled. Faster/other options and timings:
`references/stems.md`.

## Phase 3 — Meter (sweep every cycle, then decide)

```bash
<venv>/bin/python scripts/detect_meter.py <song.mp3> --drums $ST/drums.wav \
    --bass $ST/bass.wav --other $ST/other.wav \
    --foundation analysis/foundation.json --json analysis/meter.json
<venv>/bin/python scripts/foundation.py meter [--pulse-unit 8] [--use-alternative | --cycle N ...]
```

The sweep folds band-limited onsets onto every period 2–25 and ranks by accent contrast;
songs without a kit still carry the cycle in the bass and harmony, so always pass
`--bass` and `--other`. It reports a cycle, the downbeat (counted with the kick) and the
main split (`grouping`, e.g. 6+5) — or **INCONCLUSIVE**.

`foundation.py meter` then writes `beats_per_bar`, `pulse_unit`, `time_signature`,
`grouping`, `downbeat_times`, `num_bars`, `bar_bpm`, `tempo_drift_pct` and `live_tempo`.
**It stops with a question instead of guessing** — put that question to the user and
re-run with their answer: INCONCLUSIVE (count along), a phrase-length cycle (8/16 → 4/4?),
a bare duple (2/4 or 4/4?), two equally strong accents (which one is beat 1?), or an odd
cycle (eighth or quarter pulse — 11/8 vs 11/4 doubles Live's tempo). Reading the sweep,
calibration, and why beat trackers' own downbeats aren't used:
`references/meter-detection.md`.

**Cells.** Everything downstream (bass, chords, lyrics, chart) is keyed by `(bar, cell)`,
one cell per group in `grouping`: 4/4 → 2+2 (the familiar half-bars), 3/4 → one cell,
6/8 → 3+3, 11/8 as 6+5 → two unequal cells. Never split an odd bar at its midpoint.

**Sanity checks:** `tempo_drift_pct` above ~3% means one BPM misplaces notes by the end —
place them through the beat grid (`ableton-mcp` → "Timing"). Watch half/double time on
slow songs (60–90 BPM) — count along. A `num_bars` far from
`duration ÷ (beats_per_bar × beat)` means rubato, a wrong tempo octave or a wrong meter.

## Phase 4 — Bass → MIDI

**pyin** on `$ST/bass.wav` (code, cleanup rules and the octave cross-check are in the
`bass-transcribe` skill); basic-pitch only if the part is polyphonic. Then total each
pitch class's sounding time per `(bar, cell)` → `analysis/bass_per_cell.json`.

**Spell pitch classes from the key signature.** Flats for flat and neutral keys; sharps
for sharp keys — in F♯ minor a flat table writes the tonic `G♭m` and the dominant `D♭7`.

- Sub-0.5 s detections are noisy; ≥ 0.7 s sustained notes are usually right.
- Bass pedals, walks, sits on 3rds/5ths — it's a *clue* to the root, not the chord.
- **Bass enters late** in most songs: find the entry bar and ignore everything before it
  (stem bleed).

## Phase 5 — Lyric timing (Whisper on the vocals stem)

```bash
<whisper-venv>/bin/python scripts/whisper_gated.py $ST/vocals.wav [--language en] \
    --out analysis/lyrics.json
```

Gates Whisper on where the stem is actually sung (RMS → `clip_timestamps`; long-form lyric
WER 22.9% → 20.7% and far fewer filler hallucinations, arXiv 2506.15514), sets
large-v3-turbo's word-alignment heads, and drops words whose *whole* span is silent
(Whisper often starts a sung word before the voice is audible). Force `--language` when
detection wobbles (chant, non-English). Then drop known hallucinations ("Thank you.",
"Blah Blah", ".") and 3+ identical repeats.

Map each word to a bar:

```python
def locate(t, downbeats, beats_per_bar):     # from foundation.json — never assume 4
    for i in range(len(downbeats)-1):
        if downbeats[i] <= t < downbeats[i+1]:
            return (i+1, (t - downbeats[i]) / (downbeats[i+1] - downbeats[i]) * beats_per_bar)
    return None
```

## Phase 6 — Sections (from lyrics + audio)

For each canonical lyric line, find its first bar via the word timings + `locate()`.
Section boundaries = where each labelled section's first line lands. Automatic
segmentation can *suggest* boundaries, never decide them: `as_seg` (barwise CBM, fed this
song's own bars, `penalty_weight=0`) hit 80% of lyric-anchored boundaries within ±1 bar on
the one reference song with section truth, but only 27% within ±0.5 s.

## Phase 7 — Chords (lv-chordia, cross-checked)

```bash
<venv>/bin/python scripts/chord_proposal.py --other $ST/other.wav --bass $ST/bass.wav \
    --foundation analysis/foundation.json --bass-entry-bar <N> \
    --out analysis/chord_proposal.json                           # triad cross-check
<lv-venv>/bin/python scripts/lv_chords.py <song.mp3> --foundation analysis/foundation.json \
    --compare analysis/chord_proposal.json --out analysis/chords_lv.json
```

**lv-chordia is the provisional primary reading** — it names 7ths and inversions, which
the triad method can't, and led it on all three benchmark songs (two scored against
another automatic tool, one against a player's ear; `references/chord-proposal.md`). Three
songs is a small sample: it is weakest on rare qualities, and anything beyond 7ths
(add9, ♯11) is untested — read those by ear. Run it on the **full mix**.

**The triad method is the independent cross-check** (bass-root constraint with slash
relaxation, major bias **0**, flip count, per-cell margin). `--compare` lists cells where
the two disagree on the root — check those by ear with the Trap 1 tests.

## Phase 8 — Chart

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

## Local environment

Venvs, interpreters and cached models on this machine: `references/environment-setup.md`
→ "This machine". Scripts here supersede the older helpers in the tooling root.
