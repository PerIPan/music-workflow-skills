# Modal / chord-quality clarifications for charts

Read this when labeling chord quality, modes, or power chords on a chart.

## Power chord shorthand

Punk and rock charts often show chords as single letters (E, A, B) without "m" suffix.
**This is power-chord shorthand** — the 3rd is omitted, so quality is neither major nor
minor. Works in any modal context.

For bass-only charts this is fine (bass plays just the root). For full chord charts:
- **Add explicit "m" for minor** chords (Em, Am, Dm) when full triads are expected
- **Add a "chord quality note" callout** at the top of the chart explaining the convention
- **Use Roman numerals in the harmonic-role column**: lowercase = minor (i, iv, v),
  uppercase = major (V, ♭VII, ♭III)

## The modes, and the degree that tells each apart

| Mode | Degrees | Characteristic degree (vs. its neighbour) | On E |
|---|---|---|---|
| Lydian | 1 2 3 **♯4** 5 6 7 | ♯4 (vs. Ionian 4) — bright, floating | E F♯ G♯ **A♯** B C♯ D♯ |
| Ionian (major) | 1 2 3 4 5 6 7 | 4 and 7 (vs. Lydian ♯4, Mixolydian ♭7) | E F♯ G♯ A B C♯ D♯ |
| Mixolydian | 1 2 3 4 5 6 **♭7** | ♭7 (vs. Ionian 7) — rock / folk major | E F♯ G♯ A B C♯ **D** |
| Dorian | 1 2 ♭3 4 5 **6** ♭7 | 6 (vs. Aeolian ♭6) — "neutral minor" | E F♯ G A B **C♯** D |
| Aeolian (natural minor) | 1 2 ♭3 4 5 **♭6** ♭7 | ♭6 (vs. Dorian 6) | E F♯ G A B **C** D |
| Phrygian | 1 **♭2** ♭3 4 5 ♭6 ♭7 | ♭2 (vs. Aeolian 2) — Spanish / flamenco | E **F** G A B C D |
| Locrian | 1 ♭2 ♭3 4 **♭5** ♭6 ♭7 | ♭5 (vs. 5) — rare as a tonic | E F G A **B♭** C D |
| Phrygian dominant | 1 ♭2 **3** 4 5 ♭6 ♭7 | ♭2 + major 3 — flamenco / metal exotic | E F **G♯** A B C D |

## Mode test — measure the characteristic degree

Scripted as `scripts/mode_test.py` (tonic from `bass_notes.py`, per-section with
`sections.json`); the snippet below is the core of it.

Key estimators (Krumhansl, the madmom CNN) know only major and minor, so a mode has to be
measured, not looked up:

1. **Tonic from the bass pedal** — the pitch class the bass sustains longest.
2. **Third**: major vs minor (3 vs ♭3).
3. **Duel the characteristic degrees** for that third — major: 4 vs ♯4, 7 vs ♭7; minor:
   2 vs ♭2, 6 vs ♭6. Score each pair per bar in the harmonic stem, in narrow bands:

```python
C = np.abs(librosa.cqt(y, sr=sr, fmin=librosa.note_to_hz('C3'),
                       n_bins=60 * 3, bins_per_octave=60))    # 20-cent bins, C3–B5
t = librosa.times_like(C, sr=sr)

def degree_energy(pc, frames):                 # pc: 0 = C … 11 = B; ±20 c, 3 octaves
    bins = [o * 60 + pc * 5 + d for o in range(3) for d in (-1, 0, 1)]
    return C[[b for b in bins if 0 <= b < C.shape[0]]][:, frames].sum()

def mode_duel(pc_a, pc_b, downbeats):          # → [bars a wins, bars b wins]
    wins = [0, 0]
    for b0, b1 in zip(downbeats[:-1], downbeats[1:]):
        f = (t >= b0) & (t < b1)
        ea, eb = degree_energy(pc_a, f), degree_energy(pc_b, f)
        if max(ea, eb) > 0: wins[0 if ea > eb else 1] += 1
    return wins
```

Report the win count ("♯4 wins 30/30 bars"), not a guess. On a track with an E pedal
this settled E Lydian outright: A♯ over A, D♯ over D and G♯ over G in 30 of 30 bars.
A split count means the degree moves (a passing tone, or modal mixture) — say so. If
neither candidate carries energy, that axis is **undetermined** (a drone with no 6th
cannot be Dorian or Aeolian) — don't fill it in.

A degree only votes in a bar where it actually sounds (≥ 10% of the bar's chord-tone
energy) — otherwise leakage from a neighbouring chord tone decides the duel. Bins are
12-TET: on microtonal chant a degree's energy can split between bins.

Cross-check with a **duration-weighted** pitch-class profile from the transcribed notes
(total sounding time per pitch class). Note *counts* mislead: many short passing notes
outweigh one sustained chord tone.

For a band chart with modal songs, **call out the mode** in the header alongside the key,
e.g. "E natural minor (Aeolian) with Phrygian ♭2 inflections" rather than just "Em".

## Byzantine ≠ Phrygian

The Phrygian ♭2 sound is **widely associated with "Byzantine" / "Greek Orthodox" /
"Middle-Eastern" feel** in popular music, but it's NOT authentic Byzantine chant theory.

Real Byzantine chant uses the **Octoechos** (8 modes) with **microtonal intervals**
(8/10/12 moria tones, approximated as 72-EDO not 12-EDO). Most Byzantine hymns are in
**Plagal Mode 1**, closer to Western **Dorian** than Phrygian.

When charting a song with "Byzantine flavor", be honest in the chart note: "Modal
inflections (Phrygian ♭2) — Western popular-music shorthand for Eastern feel, not
authentic Byzantine chant theory."
