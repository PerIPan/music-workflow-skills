# Lead guitar / keys → MIDI (isolated stems)

Read this when you need one instrument's line — a guitar lead or riff, a piano part — as
MIDI. The 4-stem `other.wav` mixes guitar, keys and pads together, and nothing downstream
can pull them apart again.

## Pipeline

1. **Separate with 6 stems:** decode to WAV first (`ffmpeg -i <song.mp3> -c:a pcm_s16le
   /tmp/<song>.wav`), then `demucs -n htdemucs_6s -d mps -o stems /tmp/<song>.wav` →
   `guitar.wav`, `piano.wav` (plus the usual four). Take nothing else from this run —
   bass still comes from `htdemucs_ft`. Heavier alternative: **BS-RoFormer-SW** via
   `audio-separator` (6 stems incl. a real piano and guitar stem; 699 MB model, licence
   undeclared). On an M3 it ran at 0.67× real time and gave the chord step no gain (92.1 vs
   91.5%), so use it only when an isolated piano/guitar line matters.
2. **basic-pitch** on the stem. It is polyphonic and over-detects (overtones, strums):
   expect thousands of raw notes for a full song.
3. **Floor at the instrument's real range.** basic-pitch invents notes at exact octaves
   below the real content. Start at MIDI 60 (C4) for a guitar lead, 48 (C3) for piano.
4. **Lead-only filter** (for a melody): drop chord clusters (≥ N notes starting within
   ~50 ms — N ≥ 5 is usually safe, because overtones form small clusters of their own),
   notes shorter than ~0.06 s and velocities under ~25; keep the top voice.
5. **Legato:** extend each note to the next onset when the gap is ≤ ~0.4 beats.
6. **Quantize strums as a unit.** Group onsets within ~50 ms into a cluster and move the
   whole cluster to the grid with one shift. Per-note quantizing smears a strum across
   grid lines.
7. Drop everything before the instrument's entry bar (stem bleed), convert to Live beats
   through the beat grid, and push over the bulk path (`ableton-mcp`).

## Tuning

| Symptom | Loosen / tighten |
|---|---|
| Missing notes | cluster size 6+, min velocity 25, min duration 0.06 s, lower pitch floor |
| Too many notes | cluster size 3, min duration 0.18 s, pitch floor 64, min velocity 45 |
| Staccato, choppy | raise the legato gap |

## Traps

- **pyin is too strict for guitar** — it returned about 20 notes for a whole song, losing
  octaves and double-stops. Keep pyin for bass.
- **Don't subtract a rhythm track by interval overlap.** Sustained rhythm chords overlap
  any lead note that hits a chord tone; it cut one lead from 3,208 notes to 463 and
  sounded broken. To de-double, match on onset only (same pitch, onset within 50–100 ms).
