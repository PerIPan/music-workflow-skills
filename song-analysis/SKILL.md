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
| Pulse (beats only) | **madmom** `DBNBeatTrackingProcessor` | No meter assumed — see Phase 1a |
| Meter / bar length | **`scripts/detect_meter.py`** | Sweeps every cycle 2–25; finds odd meters |
| Key (melodic mode) | **librosa** chroma + Krumhansl | Signal only — see Trap 2 |
| Stem separation | **demucs `htdemucs_ft`** (4-stem) | Cleanest bass; NEVER `htdemucs_6s` (bleeds piano/guitar into bass) |
| Bass → MIDI | **CREPE** (`full` + viterbi) | Monophonic tracker; gives the ROOT, not quality |
| Polyphonic parts → MIDI | **basic-pitch** | Piano/guitar/pads, double-stops |
| Chords | **chroma + bass-root + major-bias** | 99% top-1 validated (see Phase 5b) |
| Lyrics + word timing | **mlx-whisper `large-v3-turbo`** (Apple Silicon) | Word timestamps, hallucination-filterable |
| Drum-pattern read | **librosa** band-limited onsets | see reference |
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
# Key via librosa chroma_cqt mean + Krumhansl correlation → melodic mode ONLY (Trap 2)
```

**Never pass `beats_per_bar=(3,4)`.** A constrained candidate list cannot return "none of
these" — it returns the least-bad of the options you supplied, with full confidence, and
every downstream number (bar counts, per-bar chord cells, drum histograms) silently
inherits the error. Get the pulse first; derive the meter in 1b.

### 1b. Derive the meter by sweeping every cycle length

```bash
scripts/detect_meter.py <song.mp3> --drums stems/<song>/drums.wav \
    --bass stems/<song>/bass.wav --other stems/<song>/other.wav \
    --foundation analysis/<song>_foundation.json
```

**Always pass `--bass` and `--other` too.** Plenty of songs have no drum kit, or a
percussion part that is an undifferentiated pulse carrying no accent — and the cycle is
still there, articulated by the bass and the harmony instead. The signature is a drum
contrast stuck near 1.2 while the bass reaches 3–4 and resolves the cycle cleanly. The
script falls back to these stems automatically when fewer than two drum bands decide.

Phase-folds band-limited kick / snare / hat onsets onto every cycle length from 2 to 25
pulses and ranks by **accent contrast** = loudest position in the cycle ÷ quietest.
Run it AFTER Phase 2 so it has a drums stem; a full mix works but reads muddier.

Reading the output:

| Output | Means | Do |
|---|---|---|
| Consensus, confidence HIGH | Real cycle, clear of unrelated periods | Use it. Odd winner → odd meter |
| Consensus on a multiple of 4, confidence LOW | Plain 4/4 with an *n*-bar pattern | Report 4/4 + phrase length, not an *n*-beat bar |
| INCONCLUSIVE | Bands disagree, or no usable accent | Report the ambiguity. Do NOT pick one |
| Winner is prime (7, 11, 13) | Cannot be a phrase of anything smaller | Almost certainly the meter |
| Winner = 2× a strong period | The half is the bar, the double is two bars | Take the fundamental |

**The sweep can only find cycles on the pulse grid you hand it.** If the tempogram peaks
at twice the tracked pulse, the beat tracker is reading half-time: re-run on the doubled
grid, because a cycle of 8 there shows up as 4 here. Check the tempo octave *before*
trusting any cycle length.

**A song with no percussion at all cannot be metered this way** — say so and move on
rather than straining the harmonic stem for an answer it does not contain.

**The two strongest positions in an odd cycle mark its internal split.** An 11 with peaks
at 1 and 7 is 6+5; peaks at 1 and 5 would be 4+7.

Save as `analysis/foundation.json`: `pulse_bpm`, `beat_times`, `beats_per_bar` (from 1b,
**not** from madmom), `downbeat_times` (every *n*-th beat from the winning phase),
`num_bars`, `key`.

**Sanity checks:** BPM stable (no jumps); watch half/double-time on slow songs (60–90
BPM) — count along the audio; cross-check `num_bars` against
`duration ÷ (beats_per_bar × beat)`. A large mismatch means rubato, a wrong tempo octave,
or a wrong meter.

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

**Default `MAJOR_BIAS_MARGIN` to 0, and never gate it on the detected key.** The key
estimator reports the *melody's* mode, so a modal song pedalling on a major triad returns
"major" — which switches on the very bias that destroys its minor chords. Measured: gating
on a major key estimate is enough to flip **the majority of cells in a track** (70%+),
turning a minor loop into a phantom major one.

Always run bias 0 and bias 0.05 and **report the flip count**. A large count means the
cells are near-ties and the quality call is genuinely uncertain — say so rather than
picking silently. To settle major vs minor on one chord, compare chroma energy of the
major third against the minor third directly: G♯ at 14.4% vs G♮ at 4.7% closes the
question in a single number.

Per-song tuning: `BASS_ENTRY_BAR`, template set.

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

1. `htdemucs_ft`, never `htdemucs_6s` — 6-stem bleeds piano/guitar into bass MIDI.
2. Trust the user's ear over any analyzer disagreement.
3. Chart bar = audio bar.
4. Whisper timing is precise; musical placement is not strict timing (Rule 1).
5. Bass walks mid-bar = chord changes → key by `(bar, half)`.
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
- `mlx-demucs/.venv/bin/mlx-demucs` — for any multi-song batch. `htdemucs_ft` on CPU runs
  >10 min per track even with weights cached; MLX did 5 songs in 3.5 min.
- Existing helpers: `analyze_chords.py` (Phase 5b), `analyze_chord_onsets.py`,
  `scripts/whisper_vocals.py` (Phase 4), chart generators `gen_*.py` per song folder.
- Source docs (read-only): `WORKFLOW-song-analysis.md` in the tooling root.
