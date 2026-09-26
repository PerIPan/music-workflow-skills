# How `song-analysis` compares

*Reviewed 2026-09-26: 75 tools and papers — 15 agent skills and MCP servers, 17 commercial
products, 43 open-source toolkits and research models. Every row about another tool comes
from its own README, docs or paper; "vendor claim" means nobody independent has measured
it. Corrections welcome — open an issue.*

## At a glance

| | **this skill** | score7 (MCP) | SongScope | ChordMini | Chordify | Moises | Logic Pro 12 |
|---|---|---|---|---|---|---|---|
| Meter search | **every cycle 2–25**, odd meters, grouping (11/8 as 6+5) | 2–7, binary-biased | 2–7, 5 and 7 penalised | fixed list 2–9, 12 | 3/4 or 4/4 toggle | — | — |
| When unsure | **stops and asks the right question** | `bpm_disputed` flag | per-field confidence labels | — | — | — | — |
| Key / mode | key CNN + **tonic from the bass + measured mode test** (7 modes) | 24 keys | 4 profiles + modulations | LLM-assisted numerals | key | key | key signature of chords |
| Chords | lv-chordia (7ths, inversions) + independent cross-check, **status per cell** | BTC (170 classes) | 7ths, no inversions | CNN-LSTM + BTC variants | triads (7ths by hand) | chord view | 7ths, 6ths, inversions (vendor claim) |
| Lyrics | Whisper, gated by the vocal stem, **aligned to your canonical lyrics** → sections | — | — | lookup (LRClib) | — | transcription | — |
| Output | band chord+lyric chart in any meter; **Ableton hand-off with the real meter** | Markdown/JSON/MIDI | dashboard | web player | play-along | practice app | Chord Track |
| Offline | **yes** (Apple Silicon, 16 GB) | likely (CPU) | engine yes | partly | no | no | yes |
| Benchmark | **real songs, published numbers, negative results** | tests on named tracks | synthetic only | paper for its chord models | — | vendor claims | vendor claims |
| Licence / cost | MIT, free | MIT | none declared | MIT | freemium | subscription | paid |

"—" = not offered or not documented.

## What only this does

- **Finds odd meters it was never told about.** The sweep tests every cycle from 2 to 25
  pulses on the drum, bass and harmonic stems and scores each against unrelated periods,
  so coprime meters (5, 7, 11) don't fold flat. Tools that test 2–7 or a fixed list cannot
  return 11.
- **Reports the grouping and asks when it can't know.** 11/8 comes back as 6+5 with beat 1
  counted from the kick; when two accents tie, it offers both and asks which hit is "1".
  The meter step also stops on phrase-length cycles, bare duple, and eighth-vs-quarter
  pulse (11/8 vs 11/4 doubles the DAW tempo) instead of guessing.
- **Names modes by measuring them.** Tonic from what the bass sustains; mode from
  bar-by-bar duels of the characteristic degrees (♯4, ♭7, ♭2, 6/♭6); a degree that doesn't
  sound doesn't vote, so a drone with no 6th says "undetermined". Other tools either stay
  major/minor or match templates, which modal music defeats.
- **Keys everything to the song's own bar cells** — unequal cells for odd bars, never a
  midpoint split — through chords, lyrics and the chart.
- **Publishes its failures.** A newer beat tracker broke a verified 11/8; a common major-bias
  setting cost 46 points on a minor song; a 6-stem separator gave the chord step nothing.
  Each is in the docs with its numbers.

## Where others are ahead

- **Lyric transcription accuracy.** AudioShake reports 16.1% WER on the public Jam-ALT
  benchmark (Whisper large-v3: 32.6%). This skill's gated Whisper large-v3-turbo plus
  canonical-lyric selection measured 17.9% on a six-song English subset — not directly
  comparable, and AudioShake is a paid cloud service.
- **Interactive playback.** ChordMini, Chordify and Moises sync chords, lyrics and sections
  to playback; this skill writes a static chart.
- **Stem quality.** Logic Pro's 6-stem splitter ranked first in an independent 11-tool
  listening test; this skill uses demucs `htdemucs_ft`, which is free and scriptable.
- **Note-level transcription** of melody and polyphonic parts: Klangio, AnthemScore and
  Melodyne go further (vendor claims).
- **Sections without lyrics.** Learned segmenters (SongFormer, All-In-One) label sections on
  instrumental music; this skill anchors sections to the lyrics and only uses a segmenter
  as a suggestion (as_seg: 80% of boundaries within one bar on one reference song).
- **Packaging.** score7 exposes one-call MCP tools; this skill is a set of scripts an agent
  runs in sequence.

## Measured numbers (local benchmark)

Scored by `song-analysis/bench/run_bench.py` against local ground truth that is not in this
repo (player-verified meters and modes, time-aligned chord references, Jam-ALT lyrics).
Small samples — read them as evidence, not as a leaderboard.

| Task | Result | n |
|---|---|---|
| Meter consistent with the true bar (bar or 2–4-bar phrase) | 3 of 4; 1 inconclusive, 0 wrong | 4 songs |
| Grouping of a verified 11/8 | 6+5 offered (as the alternative; player chose) | 1 |
| Mode of a verified Lydian drone | E Lydian, ♯4 in 32/32 bars | 1 |
| Chords, lv-chordia, maj/min | 73–96% (static maj7 drone lowest) | 3 songs |
| Lyric word error, best of stem/mix | 17.9% (stem 19.8%, mix 23.6%) | 6 songs, 1,809 words |
| Lyric line starts within 1 s | 83% (median error ~0.5 s) | 263 lines |
| Section starts within 2 s | 98% | 6 songs |
| Human ceiling, chords | experts agree on 73% (maj/min) / 54% (full labels) | CASD, 50 songs |

## Sources

score7 <https://github.com/KTCrisis/score7> · SongScope <https://github.com/imnaiteek/SongScope> ·
ChordMini <https://github.com/ptnghia-j/ChordMiniApp> and <https://arxiv.org/abs/2602.19778> ·
Chordify <https://support.chordify.net/hc/en-us/articles/360002148717-How-to-edit-chords> ·
Moises <https://moises.ai/blog/latest/moises-features/> ·
Logic Pro <https://support.apple.com/guide/logicpro/analyze-chords-audio-midi-regions-logic-pro-lgcp4993e80c/mac> ·
AudioShake / Jam-ALT <https://www.audioshake.ai/compare>, <https://arxiv.org/abs/2408.06370> ·
Capo <https://supermegaultragroovy.com/products/capo/help/mac/3.7/automatic-music-analysis/> ·
Klangio <https://klang.io/transcription-studio/> ·
SongFormer <https://github.com/ASLP-lab/SongFormer/> · All-In-One MLX <https://github.com/ssmall256/all-in-one-mlx> ·
Beat This! <https://arxiv.org/abs/2407.21658> · CASD (Koops et al., JNMR 2019).
