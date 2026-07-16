# Real-time / plugin alternatives to the offline CREPE pipeline

Read this when the user wants MIDI *while or right after playing inside Live*, rather
than the most accurate offline transcription.

## NeuralNote (free, AU/VST3) — best convenience/accuracy tradeoff

- Open-source plugin (github.com/DamRsn/NeuralNote) running the **basic-pitch** model.
- Sits on the bass's audio track in Live; record/route a take into it, it transcribes
  in-plugin, then **drag the MIDI out** onto a MIDI track.
- No terminal work, good accuracy on clean DI bass. Not literally real-time — it
  transcribes the captured take.
- Best when: the user is inside Live and wants MIDI seconds after playing.

## Jam Origin MIDI Bass (~$50, AU/VST) — true real-time

- Tracks bass → MIDI **as you play** (low latency); use it to drive a synth live or
  record MIDI directly while performing.
- Commercial; the only real option for "play bass, hear a synth doubling me now".
- Best when: live conversion is the point, not transcription accuracy.

## Ableton native: right-click → "Convert Melody to New MIDI Track"

- Zero setup, works on any audio clip. Rough — octave errors and timing smear on bass.
- Best when: a quick sketch is enough and precision doesn't matter.

## Decision rule

- Accuracy / charts / analysis → offline CREPE pipeline (the skill's default).
- In-Live convenience, free → NeuralNote.
- Playing bass to drive a synth live → Jam Origin MIDI Bass.
- Fast rough sketch → Live's native convert.
