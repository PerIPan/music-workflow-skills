# Drum pattern analysis (from the drums stem)

Read this when you need to know "is this song kick-on-1+3 / snare-on-2+4 rock, or
something else?" — e.g. before reinterpreting a song in a different genre, when comparing
an arrangement to a reference, or when debugging "why does the drum pattern feel wrong".

Operates on the **drums stem** from htdemucs_ft (`stems/htdemucs_ft/<song>/drums.wav`).

## Method

```python
import librosa, numpy as np

y, sr = librosa.load("drums.wav", sr=22050, mono=True)

# Skip intro (drums often start late) — analyze 30-90s where pattern is established
start_t, end_t = 30.0, 90.0
y_seg = y[int(start_t*sr):int(end_t*sr)]

# Tempo + beats — NOTE: librosa.beat.beat_track returns tempo as ARRAY in librosa >= 0.10
tempo_arr, beats = librosa.beat.beat_track(y=y_seg, sr=sr)
tempo = float(tempo_arr[0]) if hasattr(tempo_arr, "__len__") else float(tempo_arr)

# Frequency-band onset detection
S = librosa.stft(y_seg, n_fft=2048, hop_length=512)
freqs = librosa.fft_frequencies(sr=sr)

kick_band   = (freqs >= 40)   & (freqs <= 120)    # kick fundamental
snare_body  = (freqs >= 180)  & (freqs <= 280)    # snare body (skin tone)
snare_xient = (freqs >= 1500) & (freqs <= 5000)   # snare transient (snares rattling)

kick_env  = np.abs(S[kick_band, :]).sum(axis=0)
snare_env = np.abs(S[snare_body, :]).sum(axis=0) + 0.5 * np.abs(S[snare_xient, :]).sum(axis=0)

kick_onsets  = librosa.onset.onset_detect(onset_envelope=kick_env,  sr=sr, hop_length=512,
                                          units="time", delta=0.5, wait=4)
# SNARE: use a LOW threshold and the UN-NORMALIZED envelope (see lessons below)
snare_onsets = librosa.onset.onset_detect(onset_envelope=snare_env, sr=sr, hop_length=512,
                                          units="time", delta=0.15, wait=2)
```

## Interpretation

**Precondition: establish the meter first.** Every pattern below is written in 4/4, and
reading a 4/4 template onto an odd cycle produces a flat, meaningless histogram — see
SKILL.md Phase 1b and Trap 3. Run `scripts/detect_meter.py` before this step and fold
onsets onto the cycle length it returns, not onto 4.

Compare onset positions to beat times:

| Detected pattern | Conclusion |
|---|---|
| Kick on every beat, snare sparse | Greek laiko / tsifteteli / dance — kick-driven |
| Kick on 1+3, snare on 2+4 (4/4) | Standard rock backbeat |
| Kick on 1+3, snare on 2+4, strong hi-hat | Disco / motorik |
| Snare on every beat, kick syncopated | Half-time / break feel |
| No backbeat, just snare accents | Singer-songwriter, folk |
| Asymmetric (e.g. kick on 1/4/8 in 11/4) | Modal/Eastern / progressive |

## Confirmed genre patterns (validated by listening)

| Pattern | Kick | Snare | Example |
|---|---|---|---|
| Rock backbeat (4/4) | 1, 3 | 2, 4 | Standard rock |
| Punk (4/4) | 1, 3 | 2, 4 + ghost 8ths | Classic fast punk |
| Hardcore punk (11/4) | 1, 4, 8 | 3, 7, 11 | Custom 11/4 arrangement |
| **Greek laiko (4/4)** | **every beat** | **& of every beat (1&, 2&, 3&, 4&)** | Rolling laiko dance track |
| Odd meter, grouped | accents mark the split | often none | 7/8 as 3+2+2, 11/8 as 6+5 |
| Undifferentiated pulse | every pulse, equal weight | equal weight | ritual / devotional drone |
| Reggae one-drop | 3 only | 3 (rim) | Roots reggae |
| Disco / Motorik | 1, 2, 3, 4 | 2, 4 | Four-on-the-floor disco |
| Trap | 1, 3 | on 3 or rolled | Modern hip-hop |

Genre notes:
- **Greek laiko**: kick every beat, snare punctuating each "&" — rolling, danceable. If
  arranging in this style, MIRROR it; don't impose a rock backbeat.
- **Tsifteteli**: kick-driven 4/4, heavy bass emphasis; snare often replaced by darbuka/claps.
- **Zeibekiko (9/8, 4+5)**: heavy on specific beats, sparse snare, hand-percussion driven.
- **Reggae/dub**: snare on 3 (skank); kick on 1+3 (one drop) or off-beat (steppers).

## Pitfalls

- **librosa.beat.beat_track returns tempo as a numpy array** in librosa ≥ 0.10 — use
  `float(tempo[0])`.
- **Beat tracker can lock to half/double time.** If BPM seems 2× off, count along.
- **htdemucs sometimes bleeds vocals into the snare transient band** (1.5–5 kHz). If snare
  detection seems off, listen to the stem.
- **Greek/Middle-Eastern tracks may use darbuka/def/claps instead of snare** — the "snare
  band" may pick those up or miss them. Listen first.

## Lessons learned (snare undercount case)

Measured on a Greek laiko track (~99 BPM): first pass returned **4 snare hits in 60 s**;
listening confirmed snare on **every offbeat** (~120 hits/60 s) — 97% missed. Causes:

1. **`delta=0.5` too strict** for snare. Use `delta=0.15–0.25`.
2. **Normalization flattened the envelope** — consistent-velocity snares have low std, so
   median-subtract/std-divide makes them noisy. Use the un-normalized envelope for snare.
3. **Consistent offbeats are the PATTERN, not anomalies.** >2 snares at the same relative
   position (mid-beat) = the pattern, not outliers.
4. **Kick bleed into the snare band** can mask real snares.

Fix protocol when snare count seems too low:

```python
# 1. Lower threshold
snare_onsets = librosa.onset.onset_detect(
    onset_envelope=snare_env, sr=sr, hop_length=512,
    units="time", delta=0.15, wait=2)  # was 0.5, 4

# 2. Un-normalized envelope (skip median subtraction)
snare_env_raw = np.abs(S[snare_body, :]).sum(axis=0)

# 3. Cross-check: count snares per detected beat. Consistent positions
#    (e.g. always 0.3s after each kick) = the pattern, not noise.
```


## Odd meters

Once `detect_meter.py` returns an odd cycle, the two strongest positions in the folded
profile mark the internal split — that is the grouping a drummer actually feels, and the
thing to write in a chart.

Worked example — an 11/8 profile:

```
beat    1    2    3    4    5    6  │  7    8    9   10   11
str    97   13   79   45   61   79  │ 100   27   71   55   88
```

Peaks at 1 and 7 → **6+5**. The holes at 2 and 8 are the pulses right after each
downbeat, which is what makes the split audible. Accents then fall in pairs inside each
group (1·3·5 | 7·9·11), so the feel is duple throughout with one pulse left over.

Write it as `11/8 (6+5)`, not as `11/8` alone — the grouping is what a player needs.

**Do not** describe an odd meter as "no backbeat" and stop there. It has strong beats;
they just don't land where a 4/4 template looks for them.
