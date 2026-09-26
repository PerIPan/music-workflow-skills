# Meter detection — how the sweep works and how to read it

Read this when running `scripts/detect_meter.py` (Phase 1b), when its answer surprises
you, or before telling anyone a song has "no time signature".

## Why a sweep

A beat tracker asked for `beats_per_bar=(3, 4)` cannot answer "neither": it returns the
least-bad option with full confidence, and every downstream number (bar counts, chord
cells, drum histograms) inherits the error. So the pulse is tracked with no meter at all,
and the meter is derived afterwards by testing every cycle length.

## How it works

For every period P from 2 to 25 pulses, band-limited kick / snare / hat onsets are
phase-folded onto P positions, and each period is scored by **accent contrast** = loudest
position ÷ quietest. Then, per band:

- **Fundamental** = the smallest divisor of the winning period that keeps ≥ 60% of its
  contrast. All multiples of a cycle score alike (longer ones slightly higher, since each
  position averages fewer hits), so an 11-cycle often "wins" at 22 and a 5-cycle at 25.
- **Margin** = winner ÷ the strongest period *unrelated* to the fundamental (not a multiple
  or divisor, and sharing no factor ≥ 3). A band votes only if the margin is ≥ 1.3; below
  that every fold looks alike — noise, not meter.
- **Consensus** needs two bands on the same fundamental. When the drum bands don't agree,
  it falls back to the bass stem (30–250 Hz) and the harmonic stem (80–2000 Hz): plenty of
  songs have no kit, or a percussion part that is an undifferentiated pulse, and the cycle
  lives in the bass and the harmony instead.
- **Downbeat** = the strongest position of the fundamental's profile, reported as a pulse
  index: `downbeat_times = beat_times[downbeat_pulse::cycle]`.

`--json` writes every band's sweep, per-band verdicts (cycle, margin, accented positions,
downbeat pulse) and the consensus. Needs librosa, plus madmom unless `--foundation`
supplies the beat grid.

## Reading the output

| Output | Means | Do |
|---|---|---|
| Consensus, confidence HIGH | Real cycle, clear of unrelated periods | Use it. Odd winner → odd meter |
| Consensus on 8, 16, 24 (script prints a PHRASE note) | Usually plain 4/4 with an *n*-bar pattern | Report 4/4 + phrase length, not an *n*-beat bar |
| Consensus on 2 | Duple; the bar-level accent is too faint to fix 2/4 vs 4/4 | Report duple; ask the user to count |
| INCONCLUSIVE | Bands disagree, no usable accent, or no band clear of unrelated periods | Report the ambiguity. Do NOT pick one |
| Winner is prime (7, 11, 13) | Cannot be a phrase of anything smaller | Almost certainly the meter |

**The two strongest positions in an odd cycle mark its internal split** — that is the
`grouping`. An 11 with peaks at 1 and 7 is 6+5; peaks at 1 and 5 would be 4+7.

**The sweep can only find cycles on the pulse grid you hand it.** If the tempogram peaks
at twice the tracked pulse, the tracker is reading half-time: re-run on the doubled grid,
because a cycle of 8 there shows up as 4 here. Check the tempo octave *before* trusting
any cycle length.

**Keep madmom as the pulse source.** beat_this (CPJKU, 2024) was tested as a replacement
on seven songs: its grid turned a verified 11/8 into a LOW-confidence 25, read a 4/4 song
at half tempo, and sent two correct results to INCONCLUSIVE; it only tied on the rest. Its
downbeat head was chaotic on the 11/8 song (1–6 beats per "bar") — never take bar length
from a beat tracker's downbeats.

**A song with no percussion and no articulated bass cannot be metered this way** — say so
and ask the user to count, rather than straining a stem for an answer it doesn't contain.

## Calibration — the meter you never tested for looks like no meter at all

Folding onsets onto the wrong period does not produce a *low* score, it produces a
**flat** one. An 11-beat cycle folded onto 2, 3, 4 or 6 smears to near-perfect uniformity,
because 11 shares no factor with any of them.

| Top contrast in the sweep | Reading |
|---|---|
| 1.0–1.3 at *every* period tested | Wrong periods tested, or genuinely no accent. Widen the sweep |
| 1.5–2.5 | Weak or ambiguous — report it as such |
| 3–10 at one period, ≤ 2.5 at every unrelated one | A real cycle. Trust it |

Uniform contrast at every period you tested is not a finding — it means you haven't tested
the right period yet. Never report "no time signature" on the strength of a narrow sweep.
Assume odd meters are live: 5/4, 7/8 and 11/8 are ordinary in Balkan, Byzantine, prog and
much devotional music, and coprime blindness makes them invisible to a 4/4-shaped test.

The 1.3 vote threshold was calibrated on five reference songs (real cycles 2.0–17×,
drumless material 1.0–1.25×) — revisit it as more songs with a player-confirmed meter
come in.

## Tests

`<venv>/bin/python tests/test_detect_meter.py` — synthetic clicks in 4/4, 3/4, 6/8, 5/4,
7/8, 11/8 and a flat pulse; checks cycle and downbeat. ~8 s, no madmom needed.
