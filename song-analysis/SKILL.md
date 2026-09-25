---
name: song-analysis
description: Use when analyzing a song recording — extracting tempo/downbeats/key, separating stems, transcribing bass to MIDI, identifying chords per bar, timing lyrics, reading drum patterns, or producing a chord+lyric chart for a band. Covers madmom, demucs (htdemucs_ft), CREPE, basic-pitch, chroma chord proposal, and Whisper word timing.
---

# Song Analysis — recording → bars, chords, lyrics, chart

Song-agnostic pipeline, validated over many real projects (dream pop, Greek
laiko, punk reinterpretations). Works for any song, genre, or key.

**References (read on demand):**
- `references/environment-setup.md` — first-time venv install + per-song folder layout
- `references/chart-and-lyrics.md` — chart structure, the 6 lyric-placement rules, HTML output
- `references/drum-pattern-analysis.md` — kick/snare pattern reading from the drums stem
- `references/modal-theory.md` — power-chord shorthand, the mode test, Byzantine ≠ Phrygian
- `references/lead-and-keys-extraction.md` — isolated guitar/piano lines via `htdemucs_6s`

## Inputs

1. **Audio file** — mp3/wav of the song (full mix).
2. **Lyrics** — canonical text from an official source. Section labels (Verse, Chorus,
   Bridge…) come from this, not from the analyzer.

## Tool per step

| Step | Tool | Why |
|---|---|---|
| Pulse (beats only) | **madmom** `DBNBeatTrackingProcessor` | No meter assumed — see Phase 1a |
| Meter / bar length | **`scripts/detect_meter.py`** | Sweeps every cycle 2–25; finds odd meters |
| Key (melodic mode) | **madmom** `CNNKeyRecognitionProcessor` + bass-pedal check | 24-key probabilities; signal only — see Trap 2 |
| Stem separation | **demucs `htdemucs_ft`** (4-stem) | Cleanest bass. `htdemucs_6s` only for an isolated guitar/piano stem — never for bass |
| Bass → MIDI | **librosa pyin** (40–220 Hz) | Monophonic tracker; gives the ROOT, not quality. Not CREPE — see Phase 3 |
| Polyphonic parts → MIDI | **basic-pitch** | Piano/guitar/pads, double-stops |
| Chords | **chroma + bass-root** (+ slash relax) | See Phase 5b |
| Lyrics + word timing | **mlx-whisper `large-v3-turbo`** (Apple Silicon) | Word timestamps, hallucination-filterable |
| Drum-pattern read | **librosa** band-limited onsets (ADTOF optional) | see reference |
| Chart output | Python → self-contained **HTML** | see reference |

## Phase 1 — Foundation (pulse + meter + key)

### 1a. Track the pulse WITHOUT assuming a meter

```python
from madmom.features.beats import RNNBeatProcessor, DBNBeatTrackingProcessor
import librosa, numpy as np

act  = RNNBeatProcessor()(audio_path)
beat_times = DBNBeatTrackingProcessor(fps=100)(act)   # beats only, NO bar assumption
beat = float(np.median(np.diff(beat_times)))
pulse_bpm = 60.0 / beat

from madmom.features.key import CNNKeyRecognitionProcessor, KEY_LABELS
probs = CNNKeyRecognitionProcessor()(audio_path)[0]    # 24 key probabilities
key_top2 = [(KEY_LABELS[i], round(float(probs[i]), 2)) for i in np.argsort(probs)[::-1][:2]]
```

**Key: report the top two with probabilities, then check the bass pedal.** The CNN beats
chroma + Krumhansl by ~20 MIREX points and fixes relative-major/minor flips, but it knows
only 24 major/minor keys and its probability is not a confidence on modal or drone
material (a Lydian track came out as the wrong key at p = 0.59). So also take the pitch
class the bass sustains longest (duration-weighted, after Phase 3): if it disagrees with
the key estimate, trust the pedal as the tonic and name the mode with the mode test in
`references/modal-theory.md`. Either way this is the *melody's* key — Trap 2.

**Never pass `beats_per_bar=(3,4)`.** A constrained candidate list cannot return "none of
these" — it returns the least-bad of the options you supplied, with full confidence, and
every downstream number (bar counts, per-bar chord cells, drum histograms) silently
inherits the error. Get the pulse first; derive the meter in 1b.

### 1b. Derive the meter by sweeping every cycle length

```bash
<venv>/bin/python scripts/detect_meter.py <song.mp3> --drums stems/<song>/drums.wav \
    --bass stems/<song>/bass.wav --other stems/<song>/other.wav \
    --foundation analysis/foundation.json
```

**Always pass `--bass` and `--other` too.** Plenty of songs have no drum kit, or a
percussion part that is an undifferentiated pulse carrying no accent — and the cycle is
still there, articulated by the bass and the harmony instead. The signature is a drum
contrast stuck near 1.2 while the bass reaches 3–4 and resolves the cycle cleanly. The
script falls back to these stems automatically when no two drum bands agree.

Phase-folds band-limited kick / snare / hat onsets onto every cycle length from 2 to 25
pulses and ranks by **accent contrast** = loudest position in the cycle ÷ quietest.
Run it AFTER Phase 2 so it has a drums stem; a full mix works but reads muddier.

Reading the output:

| Output | Means | Do |
|---|---|---|
| Consensus, confidence HIGH | Real cycle, clear of unrelated periods | Use it. Odd winner → odd meter |
| Consensus on 8, 16, 24 (script prints a PHRASE note) | Usually plain 4/4 with an *n*-bar pattern | Report 4/4 + phrase length, not an *n*-beat bar |
| Consensus on 2 | Duple; the bar-level accent is too faint to fix 2/4 vs 4/4 | Report duple; ask the user to count |
| INCONCLUSIVE | Bands disagree, no usable accent, or no band clear of unrelated periods (margin < 1.3) | Report the ambiguity. Do NOT pick one |
| Winner is prime (7, 11, 13) | Cannot be a phrase of anything smaller | Almost certainly the meter |
| Winner = 2× a strong period | The half is the bar, the double is two bars | Take the fundamental |

**The sweep can only find cycles on the pulse grid you hand it.** If the tempogram peaks
at twice the tracked pulse, the beat tracker is reading half-time: re-run on the doubled
grid, because a cycle of 8 there shows up as 4 here. Check the tempo octave *before*
trusting any cycle length.

Needs librosa, plus madmom unless `--foundation` supplies the beat grid. `--json` writes
every band's sweep, per-band verdicts (cycle, margin, accented positions) and the
consensus. Smoke test: `<venv>/bin/python tests/test_detect_meter.py` (synthetic 4/4,
3/4, 6/8, 5/4, 7/8, 11/8 and flat clicks; ~8 s).

**A song with no percussion at all cannot be metered this way** — say so and move on
rather than straining the harmonic stem for an answer it does not contain.

**The two strongest positions in an odd cycle mark its internal split.** An 11 with peaks
at 1 and 7 is 6+5; peaks at 1 and 5 would be 4+7.

Save as `analysis/foundation.json`: `pulse_bpm`, `beat_times`, `beats_per_bar` (from 1b,
**not** from madmom), `pulse_unit` (4 if the pulse is a quarter note, 8 if an eighth),
`grouping` (the internal split, e.g. `[6, 5]`; `[2, 2]` for 4/4), `downbeat_times` (every
*n*-th beat from the winning phase), `num_bars`, `key` (top two + probabilities),
`bar_bpm` (per bar: 60 / median inter-beat interval in that bar, same unit as the pulse) and
`tempo_drift_pct` ((max − min) / median of `bar_bpm`).

**Cells.** Everything downstream (bass, chords, lyrics, chart) is keyed by `(bar, cell)`,
one cell per group in `grouping`: 4/4 → 2+2 (the familiar half-bars), 3/4 → one cell,
6/8 → 3+3, 11/8 as 6+5 → two unequal cells. Never split an odd bar at its midpoint — that
lands mid-pulse.

**Sanity checks:** read `bar_bpm`, not just one BPM — played music drifts, and above
~±3% a single tempo misplaces notes by the end (`ableton-mcp` → "Timing"). Watch
half/double-time on slow songs (60–90 BPM) — count along the audio; cross-check `num_bars` against
`duration ÷ (beats_per_bar × beat)`. A large mismatch means rubato, a wrong tempo octave,
or a wrong meter.

## Phase 2 — Stems

```bash
demucs -n htdemucs_ft -d mps -o stems <song.mp3>
# → stems/htdemucs_ft/<song>/{bass,drums,vocals,other}.wav
```

**Always pass `-d mps` on Apple Silicon.** demucs 4.0.1 defaults to CUDA-else-CPU, so
without the flag it runs on the CPU. Measured on an M3 (30 s clip): CPU 64.5 s, MPS 23.0 s,
stems within noise of each other. Meter-only runs need just the drums:
`--two-stems=drums`.

**CHECK THE CACHE FIRST — `du -sh ~/.cache/torch/hub/checkpoints`** (demucs 4.0.1; 4.1.x
loads from the Hugging Face cache instead). `htdemucs_ft` is a bag of 4 models (4 × 84
MB). If it isn't cached, that command silently downloads for as long as your connection
takes — measured at ~3 MB/min (≈100 min) on 2026-08-06 — and shows no progress at all if
you pipe it through `tail`. Don't assume it's cached because you used it
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

Default: **pyin** on `bass.wav` (monophonic → root line). For the pyin→MIDI code and
cleanup rules, use the `bass-transcribe` skill — same pipeline. Use **basic-pitch** only
if the part is polyphonic. CREPE is for vocals, not bass (reasons in `bass-transcribe`).

Then aggregate per `(bar, cell)`: for each cell, total each pitch class's overlapping
note duration and rank → `analysis/bass_per_cell.json`.

**Spell pitch classes from the key signature, not from a fixed table.** Flat spelling
(C, D♭, D, E♭ … B♭, B) is the right default for flat and neutral keys — it matches how
guitarists read pop/indie charts. But applying it blindly in a **sharp key produces
nonsense**: in F♯ minor (three sharps) the flat table renders the tonic as `G♭m`
instead of `F♯m`, and the dominant as `D♭7` instead of `C♯7`. Rule: if the
key signature has sharps, use sharp spelling (C♯, D♯, F♯, G♯, A♯); if flats or none, use
flats.

**Pitfalls:**
- Sub-0.5 s detections are noisy; ≥0.7 s sustained notes are usually right.
- Bass doesn't always play roots — it pedals, walks, sits on 3rds/5ths. Bass note is a
  *clue*; annotate in chart only when bass ≠ chord root.
- **Bass enters late** in most songs. Find the bass-entry bar (first clearly audible bar)
  and suppress all bass-derived annotations before it — pre-entry content is stem bleed.

## Phase 4 — Lyric timing (Whisper on the VOCALS STEM)

Whisper is far more accurate on isolated vocals than the full mix. **Gate it on where
the stem is actually sung** instead of fiddling with `no_speech_threshold`: an RMS gate
on the vocal stem, fed in as `clip_timestamps`, cut long-form lyric WER 22.9% → 20.7% and
removed most filler hallucinations on separated vocals (arXiv 2506.15514).

```python
import librosa, numpy as np, mlx.core as mx, mlx_whisper
from mlx_whisper.transcribe import ModelHolder

REPO = "mlx-community/whisper-large-v3-turbo"      # large-v3 = extra ~3 GB, no gain
y, sr = librosa.load(VOCALS, sr=16000, mono=True)
rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
t = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)
sung = rms > 0.1 * rms.max()                       # the gate

segs, start = [], None                             # sung runs → [start, end]
for ti, on in zip(t, sung):
    if on and start is None: start = ti
    if not on and start is not None: segs.append([start, ti]); start = None
if start is not None: segs.append([start, t[-1]])
merged = []                                        # merge gaps < 1 s, cap at 30 s
for s0, e0 in segs:
    if merged and s0 - merged[-1][1] < 1.0 and e0 - merged[-1][0] <= 30: merged[-1][1] = e0
    else: merged.append([s0, e0])
dur = len(y) / sr
clips = [(max(0, s0 - 0.4), min(dur, e0 + 0.4)) for s0, e0 in merged]  # pad: onsets lead

# turbo's curated word-alignment heads — mlx-whisper never sets them itself
ModelHolder.get_model(REPO, mx.float16).set_alignment_heads(
    b"ABzY8j^C+e0{>%RARaKHP%t(lGR*)0g!tONPyhe`")
res = mlx_whisper.transcribe(
    VOCALS, path_or_hf_repo=REPO, word_timestamps=True,
    clip_timestamps=[x for c in clips for x in c],
    condition_on_previous_text=False,              # avoids hallucination drift
    hallucination_silence_threshold=2.0)           # add language="en"/"el"/… if known

def in_gate(w):                                    # keep a word if ANY of its span is sung
    m = (t >= w["start"]) & (t <= w["end"])
    return bool(m.any() and sung[m].any())
words = [w for seg in res["segments"] for w in seg.get("words", []) if in_gate(w)]
```

Judge a word by its **whole span**, not its start — Whisper often starts a sung word
before the voice is audible, and filtering on start time drops real words. Force
`language=` when the auto-detect wobbles (chant, non-English). Then post-filter known
hallucinations ("Thank you.", "Blah Blah", ".") and 3+ identical repeats. On a
three-minute stem the gated run took ~4 min on an M3 including model load.

`no_speech_threshold=0.8` (if you skip the gate) also drops real, sparse vocals — it can
return nothing for a track that has singing. The curated alignment heads are what
openai-whisper uses for this model; their effect on sung vocals hasn't been A/B'd.

Map each word's start time to (bar, beat):

```python
def locate(t, downbeats, beats_per_bar):     # from foundation.json — no default, never assume 4
    for i in range(len(downbeats)-1):
        if downbeats[i] <= t < downbeats[i+1]:
            return (i+1, (t - downbeats[i]) / (downbeats[i+1] - downbeats[i]) * beats_per_bar)
    return None
```

## Phase 5 — Sections (manual, from lyrics + audio)

For each canonical lyric line, find its first bar via Whisper + `locate()`. Section
boundaries = where each labeled section's first line lands. **Don't trust automatic
section detection** (librosa recurrence segmentation is ±1 bar off around bridges/outros);
the lyrics + word timing are far more reliable.

## Phase 5b — Chord proposal (chroma + bass-root)

Per cell, on the `other.wav` stem (everything harmonic except bass/drums/vocals).

1. **Chroma**: average `librosa.feature.chroma_cqt(other.wav)` over the cell's frames.
2. **Score all 24 triad templates** (12 maj + 12 min, binary root/3rd/5th, sum-normalized)
   by dot product with the cell chroma.
3. **Bass-root constraint** (only when `bar >= BASS_ENTRY_BAR`): if one bass pitch class
   has ≥0.5 s sustain in the cell, restrict candidates to the maj+min triads on that root —
   **unless step 4 relaxes it**.
4. **Slash-chord relaxation (REQUIRED — +17.7 points).** The constraint assumes the bass
   note *is* the root. On a slash chord the bass plays the 3rd or 5th, and constraining to
   it forces a guaranteed-wrong answer:

   ```python
   allc = sorted(all 24 templates by score, desc)
   con  = [c for c in allc if root_of(c) == bass_pc]
   use_constrained = con and con[0].score >= RELAX_FACTOR * allc[0].score   # 0.85
   ```

   If the best chord rooted on the bass note scores materially worse than the
   unconstrained best, the bass is a non-root chord tone — drop the constraint and let
   chroma decide. `RELAX_FACTOR = 0.85`; anything ≥0.85 behaves identically, 0.0 = off.
   Measured on a minor-tonic track built around a dominant-7th slash chord (C♯7/F, bass
   on the 3rd, E♯): without it every C♯7 cell became `Fm`, the minor triad on the bass
   note (14 misses, a third of all errors). With it: **73.8% → 91.5%** root+quality.
5. **Emit top-3** per cell + `beat3_re_attack` flag from onset detection on the same stem
   (corroborating evidence only — noisy).
6. **Major-bias diff pass.** Re-run with `MAJOR_BIAS_MARGIN = 0.05` (if the top template is
   minor and the same-root major is within the margin, swap) and **report the flip
   count**. Never adopt the biased result silently.

### `MAJOR_BIAS_MARGIN`: default 0, never gated on the key

It is the single highest-leverage parameter. Same minor-tonic track (F♯m tonic), same
audio, only this changed:

| `MAJOR_BIAS_MARGIN` | root+quality |
|---|---|
| 0.05 | **27.4%** |
| 0.02 | 54.9% |
| 0 | **73.8%** |

A 46-point swing: at 0.05 the tonic minor flips to major on nearly every cell. The 0.05
bias was tuned on modal-major dream pop, where it reached 99% top-1 / 100% top-3 — that
figure does not transfer to other material.

**Never gate the bias on the detected key.** The key estimator reports the *melody's*
mode, so a modal song pedalling on a major triad returns "major" — which switches on the
very bias that destroys its minor chords. Measured: gating on a major key estimate flipped
the majority of cells in a track (70%+), turning a minor loop into a phantom major one.

A large flip count means the cells are near-ties and the quality call is genuinely
uncertain — say so rather than picking silently. To settle major vs minor on one chord,
compare chroma energy of the major third against the minor third directly: G♯ at 14.4%
vs G♮ at 4.7% closes the question in a single number.

Why the combination works: bass MIDI gives the root but not the quality; chroma gives the
quality but confuses 4th/5th-related roots. Errors concentrate in pre-bass-entry bars,
sustained-organ smear, and extended chords (expand templates with 7th/sus for jazz/R&B).

Per-song tuning: `BASS_ENTRY_BAR`, template set.

## Phases 6–9 — Chart

Read `references/chart-and-lyrics.md` before building the chart. Core invariants:
- One row per section; parallel sections get identical row splits.
- Chart bar = audio bar. A virtual bar only where the audio has none (e.g. a rubato hold
  the beat tracker skipped) — and mark it on the chart.
- Chord dict keyed by `(bar, cell)` (cells from `grouping`, Phase 1).
- **Lyric phrases anchor at the chord they resolve INTO** (Rule 1 — the big one).
- Output: single self-contained HTML, print-friendly, harmonic-notes block at bottom.

## Hard rules — the cardinal traps

### Trap 1 — A bass walk is one chord or two; the upper voicing decides

Bass moving within a bar (`C → A♭`) has two readings, and both are common: (1) one held
chord over a moving bass (`Cm/A♭`, or a drone with a walking bass) or (2) **two chords**
(`Cm → A♭`). The bass alone cannot tell them apart — and a bass-constrained matcher
simply follows the bass, so it reports (2) either way.

**Discriminating test — look above the bass:**
- **Re-attack**: a new voicing struck where the bass moves (in `other.wav`) = two chords.
- **Register-pooled chroma**: pool chroma per cell in the chord instrument's own register
  (high-pass above ~165 Hz). If the pitch-class set changes with the bass = two chords;
  if it stays put = one chord over a moving bass.

Bass movement alone is a suspicion signal, never the decision.

### Trap 2 — "Minor key" ≠ minor chords

Key estimators report the **melody's mode** (the PCP is melody-dominant), not chord
quality. Many songs put **major triads under a minor melody** — that's the bittersweet
sound. Default each chord to major, then verify: play root+maj3+5 against the melody; if
the maj-3rd fights the melody's ♭3, go minor. Never propagate the key label to chord
quality. Also: many modal songs pivot between relative major and minor — label the key as
a pair (`E♭ / Cm`) when both centers appear.

### Trap 3 — The meter you never tested for looks like no meter at all

Folding onsets onto the wrong period does not produce a *low* score, it produces a
**flat** one. An 11-beat cycle folded onto 2, 3, 4 or 6 smears to near-perfect uniformity,
because 11 shares no factor with any of them.

Calibration — read your own contrast numbers against this:

| Top contrast in the sweep | Reading |
|---|---|
| 1.0–1.3 at *every* period tested | Wrong periods tested, or genuinely no accent. Widen the sweep |
| 1.5–2.5 | Weak or ambiguous — report it as such |
| 3–10 at one period, ≤2.5 at every unrelated one | A real cycle. Trust it |

A coprime cycle read through the wrong fold lands squarely in the first row: uniform, not
low.

**Uniform contrast at every period you tested is not a finding. It means you have not
tested the right period yet.** Widen the sweep before concluding anything, and never
report "no time signature" on the strength of a narrow sweep.

Corollary: assume odd meters are live. 5/4, 7/8 and 11/8 are ordinary in Balkan,
Byzantine, prog and much devotional music — exactly the material this pipeline gets used
on. Coprime blindness makes them invisible to a 4/4-shaped test.

**Verify with a player.** All automated signals are wrong ~30% of the time on
modal-mixture songs. A musician who knows the song is ground truth — plan a verification
pass before declaring the chart done.

## Lessons learned

1. `htdemucs_ft` for bass, never `htdemucs_6s` — 6-stem bleeds piano/guitar into bass
   MIDI. `htdemucs_6s` is for isolating guitar or piano only.
2. Trust the user's ear over any analyzer disagreement.
3. Chart bar = audio bar.
4. Whisper timing is precise; musical placement is not strict timing (Rule 1).
5. A mid-bar bass walk may or may not change the chord (Trap 1) → key by `(bar, cell)`
   so either reading can be written down.
6. Chord-recognition tools are starting points, never ground truth.
7. Each chart correction touches ~3 places (chord dict, row layout, cascading lyrics).
8. Mirror parallel sections visually.
9. Section-boundary pickups: overlay in the same cell, don't displace.
10. Never hand an analyzer a candidate list it can't say "none of these" to — a
    constrained `beats_per_bar` and a key-gated `MAJOR_BIAS_MARGIN` both produced
    confident wrong answers that survived every downstream check.
11. Ask the user to count. A player's count settles in seconds what a sweep can only
    rank, and it outranks the sweep.
12. A static upper voicing over a moving bass reads as several chords to a triad matcher.
    Before reporting a progression, pool chroma **per bar in the instrument's own
    register** (high-pass away the bass) and check whether the set actually changes — a
    drone with a walking bass is one chord, not four.
13. `basic-pitch` duplicates notes at exact octaves and invents low-register content that
    the stem does not contain. Floor the output at the instrument's real range (C3 for a
    piano out of `other.wav`) before pushing anything to Ableton.

## Local environment (this machine)

- Tooling root: `/Users/peripan/dev/abletonAI/audio-analysis/`
- `.venv-bp/bin/python` — madmom, librosa, basic-pitch, crepe, pretty_midi.
  `.venv-demucs/bin/python` — demucs.
- **Whisper is NOT in any audio-analysis venv.** It lives at
  `/Users/peripan/mlx-openai-whisper/bin/python`, and only
  `mlx-community/whisper-large-v3-turbo` is cached — naming `whisper-large-v3-mlx`
  triggers a ~3 GB download.
- `mlx-demucs/.venv/bin/mlx-demucs` — for any multi-song batch (plain htdemucs; 5 songs in
  3.5 min). `htdemucs_ft` without `-d mps` runs on the CPU at ~2 s per second of audio.
- Existing helpers: `analyze_chords.py` (Phase 5b — stale: set `MAJOR_BIAS_MARGIN = 0`),
  `analyze_chord_onsets.py`, `scripts/whisper_vocals.py` (Phase 4), chart generators
  `gen_*.py` per song folder.
- Source docs (read-only): `WORKFLOW-song-analysis.md` in the tooling root.
