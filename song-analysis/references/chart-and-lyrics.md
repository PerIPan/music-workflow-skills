# Chart structure, lyric placement, and HTML output

Read this when producing the chord+lyric chart (Phases 6–9 of the song-analysis skill).

## Chart structure

### One row per section

Every section starts a new row. Within a section, split into multiple rows if needed
(typically when bar count exceeds 8–10). Pair-symmetric sections (Chorus 1 / Chorus 2)
**must use the same row split** for visual readability.

### Bar numbering

**Chart bar = audio bar.** Do not insert "virtual" bars to make the chart breathe. If a
section ends with a sustained chord, use the natural audio bar where it sustains. This
keeps the chart trivially mappable back to audio for re-checking.

### Cells per bar

Two half-bars per bar (h1 = beats 1–2, h2 = beats 3–4). Each cell shows:
- **Chord** (large) — guitar/piano shape
- **(bass note)** in small blue parens — only if bass differs from chord root (slash-chord notation)
- **Lyric** (small italic) — words sung in this half-bar

Key the chord dict by `(bar, half)` so chords can change mid-bar (which they often do —
see "Bass walks reveal chord changes mid-bar" below).

### Grid widths

Use variable-width CSS grids per row, picking the smallest that fits the row's bar count
cleanly: `cols-2` (1 bar), `cols-4` (2), `cols-6` (3), `cols-8` (4, default), `cols-10`
(5), `cols-12` (6).

## Lyric placement rules

Vocalists anticipate beats — pickup syllables come early, resolutions land late. Raw
Whisper word-onset timing produces awkward, visually misleading placements.

### Rule 1 (the big one): Anchor at the chord that resolves the phrase

**Each lyric phrase visually lives in the cell of the chord it resolves INTO**, not where
the pickup syllable was sung. Pickup syllables are absorbed. Bands read cell-to-chord — a
pickup syllable visually attached to the wrong chord causes them to play that chord with
the wrong feel.

```
Sung:    [A♭ bar...] "Ev'ry night, baby,"|[E♭ bar] "that's where I"  [A♭ bar] "go"
Chart:   [A♭]                              |[E♭]    "Ev'ry night, baby, / that's where I"  [A♭] "go"
                                            ^ phrase anchored at the E♭ change
```

Apply per line: identify the chord the line *resolves on* (usually a chord change near the
phrase end) and place the phrase's first words in that bar's h1.

### Rule 2: Empty cells = sustain or rest

A cell with no lyric means the previous chord/lyric sustains, or it's an instrumental
rest. Don't fill empty cells with filler — the band reads emptiness as "hold". Common
patterns:

- Phrase ends mid-bar → next half-cell empty until the next phrase's resolution chord
- Section closes with a sustained chord → trailing cells of that bar empty
- 1–2 beats of silence between phrases → that half-cell empty

### Rule 3: Cascade right when phrase pushes through cells

When a phrase starts later than its current placement (Rule 1 shifts it right), shift
every subsequent lyric one cell right too, **until an empty cell absorbs the shift** or
you hit a phrase-anchor that should stay. Don't try to re-distribute words — slide the
whole sequence.

### Rule 4: Section-pickup overlay

When a phrase from the *next* section is sung inside the *current* section's last filled
cell, render it as a colored overlay in the same cell (e.g. the bridge's last A♭ box
contains both the bridge's "you fill" and the chorus link's "It's just that"). Don't
displace the current section's lyric; co-habit.

CSS pattern:
```css
.lyric .pickup { color: <chorus-color>; font-weight: 600; margin-left: 0.45em; font-style: normal; }
```

### Rule 5: Block absorption at section boundaries

For Whisper auto-fill of remaining words: a word landing past beat 2 of a bar normally
absorbs to the next bar's h1. But across section boundaries, that absorption can spill the
previous section's lyric into the next. Maintain
`extra_no_absorb_after = {bar numbers where section ends}` to block.

### Rule 6: Cascade-on-conflict for auto-fill

If Whisper auto-fill would land on a manually-anchored cell, push to h2, then next bar h1,
until empty.

## Iteration with the player (band perspective)

Patterns that recur across songs:

- **"Anchor at the chord, not the syllable."** Pickups are visual artifacts; the chart's
  job is to show *where to play the chord change*. Rule 1.
- **"Chord and lyric must live on the same row."** When moving a phrase to a new row, move
  the chord progression that supports it. If "It's just that I fell" lives on the chorus
  row, the chorus's E♭→F lift must live there too — even if it's the section's first bar.
- **"Verses with `(2-chord bar | 1-chord bar)` pairs."** Many songs use
  antecedent-consequent verse patterns: the first bar walks two chords (e.g. `i → ♭VI`)
  and the second bar answers with one sustained chord. Once you spot the pattern,
  sight-reading the section gets dramatically easier — note it in the chart header.
- **"Mirror parallel sections visually."** If Chorus 1 is 10 bars in a 6+4 row split,
  Chorus 2 must be the same — even when the lyric distribution differs. The band's eye
  expects symmetry.
- **"Bass walks reveal chord changes mid-bar."** When bass moves `C → A♭` across the two
  halves of a bar, that's *two chords* (Cm → A♭), not a static slash chord. Key the chord
  dict by `(bar, half)`, not by `bar`.
- **"Bass annotation only when it differs from chord root."** No redundant `(C)` under a
  `Cm` chord. Slash chord notation (`G/B` rendered as `G (B)`) is what bands actually read.
- **"Bass enters at bar X — suppress before."** Most songs have an instrumental setup of
  1–8 bars before bass enters. Stem separation picks up bleed in those bars; suppress
  annotations before the documented bass-entry bar.
- **"Chart bar = audio bar."** Only insert virtual bars when there is genuinely no
  corresponding audio bar (rare).

Each correction usually touches three places: (a) the chord dict, (b) the row layout,
(c) the cascading lyrics in subsequent cells. Plan for cascading edits.

## HTML output

**HTML** — browser-friendly, opens on any device, prints cleanly to PDF, hostable in any
cloud-storage folder for the band. A single self-contained `.html` (inline `<style>`, no
external assets) is the most portable.

Structure:
- CSS Grid for the bar boxes (one row per section as established above)
- `section-start` rows: top border + bold uppercase section name
- `section-cont` rows: continuation — bar range + sub-label only, no section name repeated
- Variable-width grids per row (`cols-2` … `cols-12`) — smallest that fits cleanly

Bottom of chart: **harmonic-notes block**. One short paragraph per section explaining the
chord pattern in scale-degree terms (`i → ♭VI → iv`, `♭III rising into IV`, Neapolitan
♭II, etc.). Bands read this once and internalize the pattern.

Print-friendly: `@page { size: A4 portrait; margin: 0.35in }`. Single page if possible,
two pages max. Use `@media print` to scale fonts down ~10% and tighten cell padding.
