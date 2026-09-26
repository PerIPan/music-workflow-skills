# Chord proposal — lv-chordia first, the triad method as cross-check

Read this when tuning Phase 7, when its output looks wrong, or before quoting its
accuracy to anyone. lv-chordia is the *provisional* primary: three songs, two of them
scored against another automatic tool.

## Benchmark (2026-09-26, per cell, mir_eval)

| Song — truth | Metric | Triad method | lv-chordia (mix) |
|---|---|---|---|
| Minor-tonic soul, V7 in 1st inversion — Chordify | root / maj-min | 94.5 / 91.5% | 96.3 / 96.3% |
| | 7ths / with inversions | 79.3 / 79.3% | 84.8 / 92.1% |
| Modal-major dream pop — Chordify, time-aligned | root / maj-min | 97.1 / 76.0% | 100 / 95.2% |
| Static Emaj7 over an E pedal, 11/8 — a player's ear | 7ths | 0% (30% root) | 75% |

Chordify is itself automatic, so the first two rows measure agreement, not truth; the
third row is a player's verification. A bar-level Chordify chart drifted a bar against
the beat grid (83 vs 84.5 BPM) and scored both methods ~45% — **score against
time-aligned references**, not bar numbers from another tool's grid.

lv-chordia (ISMIR 2019, `pip install lv-chordia==1.1.0`, MIT) runs the `submission`
vocabulary by default. Its bundled model is the paper's no-re-weighting variant — the
weakest on rare qualities — and the `full` vocabulary (add9, ♯11) is untested upstream:
don't read extensions beyond 7ths off it. The accuracy figures in its README are not in
the paper. It reported the static-Emaj7 track's intro and outro as F♯7/F♯maj7 — either an
error or a real change; ask the player.

## The triad method (`scripts/chord_proposal.py`) — cross-check

### Method (per cell, on the `other.wav` stem)

1. **Chroma** — `librosa.feature.chroma_cqt` averaged over the cell.
2. **Score all 24 triads** (12 major + 12 minor, binary root/3rd/5th, sum-normalised) by
   dot product with the cell chroma.
3. **Bass-root constraint** — from the bass-entry bar on, when the bass carries one pitch
   class, prefer triads on that root…
4. **…unless that costs too much: slash-chord relaxation (required).** On a slash chord
   the bass plays the 3rd or 5th, and constraining to it forces a guaranteed-wrong answer.
   If the best triad on the bass note scores below 0.85 × the unconstrained best, the bass
   is a non-root chord tone: drop the constraint and let chroma decide (`RELAX = 0.85`;
   anything ≥ 0.85 behaves identically). Measured on a minor-tonic track built around a
   dominant-7th slash chord (C♯7/F, bass on the 3rd, E♯): without it every C♯7 cell became
   `Fm`, the minor triad on the bass note — 14 misses, a third of all errors. With it,
   **73.8% → 91.5%** root+quality.
5. **Output per cell:** chord, score, **margin** over the runner-up (small = near-tie), two
   alternatives, the bass pitch class, whether the slash relaxation fired, and a
   `re_attack` flag (onset at the cell start — corroborating evidence only, noisy).
6. **Major-bias diff pass** — re-scored with a 0.05 bias toward the same-root major; the
   script reports how many cells would flip.

### `MAJOR_BIAS`: default 0, never gated on the key

It is the single highest-leverage parameter. Same minor-tonic track (F♯m tonic), same
audio, only this changed:

| Major bias | root+quality |
|---|---|
| 0.05 | **27.4%** |
| 0.02 | 54.9% |
| 0 | **73.8%** |

A 46-point swing: at 0.05 the tonic minor flips to major on nearly every cell. The 0.05
bias was tuned on modal-major dream pop, where it reached 99% top-1 / 100% top-3 — that
figure does not transfer to other material.

**Never gate the bias on the detected key.** Key estimators report the *melody's* mode, so
a modal song pedalling on a major triad returns "major" — which switches on the very bias
that destroys its minor chords. Gating on a major key estimate flipped 70%+ of the cells
in one track, turning a minor loop into a phantom major one.

**Report the flip count.** A large one means the cells are near-ties and the quality call
is genuinely uncertain — say so rather than picking silently. To settle major vs minor on
one chord, compare the chroma energy of the major third against the minor third directly
(G♯ 14.4% vs G♮ 4.7% closes the question in one number), or run the mode test in
`modal-theory.md`.

### Where it fails

- **A static voicing over a moving bass** reads as several chords. The script's near-ties
  and flip count light up; confirm with register-pooled chroma (Trap 1 in the skill).
  A sustained maj7 or add9 voicing bounces between the triads it contains (Emaj7 →
  E / G♯m / B).
- **Before the bass enters** (bleed), in **sustained-organ smear**, and on **extended
  chords** — the templates are triads only; read 7ths/sus from the voicing by ear or
  expand the template set.

Why the combination works at all: bass MIDI gives the root but not the quality; chroma
gives the quality but confuses 4th/5th-related roots.

## Tests

`<venv>/bin/python tests/test_chord_proposal.py` — a synthetic A-minor progression with a
first-inversion G/B and a harmonic-minor V; checks minor chords stay minor at bias 0,
the slash relaxation fires, and flat spelling.
