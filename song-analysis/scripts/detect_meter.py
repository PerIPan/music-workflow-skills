#!/usr/bin/env python3
"""Detect a song's metric cycle WITHOUT assuming 3/4 or 4/4.

Sweeps every cycle length from 2 to --max pulses, phase-folds band-limited
percussion onsets onto each, and ranks by accent contrast (loudest position in
the cycle / quietest). Onset-envelope autocorrelation per period is printed
alongside for reference; it does not enter the verdict.

Why not madmom's beats_per_bar: it needs candidate meters up front, and a
constrained list returns a confident wrong answer rather than an error. This
sweep is unconstrained, so 11/8 and 7/8 are as reachable as 4/4.

Usage (run with the analysis venv's python — needs librosa, and madmom unless
--foundation is given):
    <venv>/bin/python detect_meter.py <audio.wav|mp3> [--drums stems/drums.wav]
        [--bass stems/bass.wav] [--other stems/other.wav] [--max 25]
        [--foundation analysis/foundation.json] [--json out.json]

Reads the pulse grid from --foundation if given (avoids recomputing madmom),
otherwise tracks beats itself. --drums is strongly preferred: a separated drum
stem gives a far cleaner accent profile than the full mix. --bass / --other are
used automatically when no two drum bands agree.
"""
import argparse, json, sys
from math import gcd
import numpy as np
import librosa

BANDS = {"kick": (30, 110), "snare": (180, 450), "hat": (6000, 11000)}
# Fallback when the drum bands say nothing: many songs have no kit at all, but the
# bass and the harmonic part still articulate the cycle. Typical signature is a drum
# contrast stuck near 1.2 while the bass reaches 3-4 and resolves the cycle.
FALLBACK = {"bass": (30, 250), "harmonic": (80, 2000)}
# A band only votes if its winner stands clear of every unrelated period. On five
# reference songs, real cycles measured 2.0-17x; drumless or kit-less material sat
# at 1.0-1.25x (every fold alike). Calibrated on that small set — revisit with more.
MIN_MARGIN = 1.3


def pulse_grid(audio_path, foundation=None):
    if foundation:
        F = json.load(open(foundation))
        bt = np.array(F["beat_times"])
        return bt, float(np.median(np.diff(bt)))
    from madmom.features.beats import RNNBeatProcessor, DBNBeatTrackingProcessor
    act = RNNBeatProcessor()(audio_path)
    bt = DBNBeatTrackingProcessor(fps=100)(act)   # beats only, NO bar assumption
    return bt, float(np.median(np.diff(bt)))


def band_pulse_strength(y, sr, bt, beat, lo, hi):
    """Onset strength of one frequency band, sampled at each pulse."""
    S = librosa.stft(y, n_fft=2048)
    fr = librosa.fft_frequencies(sr=sr, n_fft=2048)
    band = librosa.istft(S * ((fr >= lo) & (fr < hi))[:, None])
    oe = librosa.onset.onset_strength(y=band, sr=sr, hop_length=256)
    oe = oe / max(oe.max(), 1e-9)
    t = librosa.times_like(oe, sr=sr, hop_length=256)
    out = []
    for b in bt:
        m = (t >= b - beat * 0.2) & (t < b + beat * 0.3)
        out.append(float(oe[m].max()) if m.any() else 0.0)
    return np.array(out)


def sweep(ps, pmax):
    """For every period, the best phase alignment and its accent contrast."""
    x = ps - ps.mean()
    ac = np.correlate(x, x, "full")[len(x) - 1:]
    ac = ac / max(ac[0], 1e-9)
    rows = []
    for P in range(2, pmax + 1):
        best = None
        for ph in range(P):
            acc = np.zeros(P); cnt = np.zeros(P)
            for i, v in enumerate(ps):
                k = (i - ph) % P
                acc[k] += v; cnt[k] += 1
            prof = acc / np.maximum(cnt, 1)
            c = float(prof.max() / max(prof.min(), 1e-9))
            if best is None or c > best[0]:
                best = (c, ph, prof)
        rows.append(dict(period=P, contrast=round(best[0], 2), phase=best[1],
                         profile=[round(float(v), 3) for v in best[2]],
                         autocorr=round(float(ac[P]), 3) if P < len(ac) else 0.0))
    return rows


def verdict(rows, label):
    ranked = sorted(rows, key=lambda r: -r["contrast"])
    win = ranked[0]
    P = win["period"]
    # fundamental: smallest divisor of the winner that keeps most of its contrast.
    # Search every divisor, not just the top few: all multiples of a cycle score
    # alike (longer ones slightly higher, fewer samples per position), so a 5- or
    # 3-cycle's own period can rank below four of its multiples.
    fund = min((r["period"] for r in rows
                if P % r["period"] == 0 and r["contrast"] > 0.6 * win["contrast"]),
               default=P)
    # rival: the strongest period UNRELATED to the fundamental. Related = a multiple
    # or divisor of it, or sharing a factor >= 3 (the same bar or beat group): for a
    # cycle of 8, periods 4, 12, 16, 20, 24 are all one 4/4 grid, not competitors.
    def related(q):
        return q % fund == 0 or fund % q == 0 or gcd(q, fund) >= 3
    rival = next((r for r in ranked if not related(r["period"])), None)
    margin = win["contrast"] / rival["contrast"] if rival else float("inf")
    print(f"\n  [{label}] top periods by accent contrast:")
    for r in ranked[:6]:
        tag = ""
        if r["period"] == fund: tag = "  <- fundamental"
        elif fund and r["period"] % fund == 0: tag = f"  (={r['period']//fund}x{fund})"
        print(f"    {r['period']:3d} pulses  contrast {r['contrast']:6.2f}  "
              f"autocorr {r['autocorr']:+.2f}{tag}")
    if win["contrast"] < 1.5:
        print(f"    VERDICT: no measurable accent (best contrast {win['contrast']:.2f}).")
        print("      Either this part has no metric accent, or the cycle is longer")
        print(f"      than --max. Re-run with a larger --max before concluding anything.")
        return None
    if margin < MIN_MARGIN:
        print(f"    VERDICT: no distinct cycle — best ({fund}) is only {margin:.2f}x clear of")
        print(f"      unrelated periods (< {MIN_MARGIN}). Every fold looks alike: noise, not meter.")
        return None
    print(f"    VERDICT: cycle of {fund} pulses"
          + (f" (winner {P} = {P//fund}x)" if P != fund else "")
          + f", {margin:.1f}x clear of the nearest unrelated period.")
    frow = next(r for r in rows if r["period"] == fund)
    prof = frow["profile"]
    downbeat = (frow["phase"] + int(np.argmax(prof))) % fund   # pulse index of beat 1
    mx = max(prof)
    print(f"    accent profile: " + " ".join(f"{int(v/mx*99):3d}" for v in prof))
    strong = [i + 1 for i, v in enumerate(prof) if v > np.mean(prof)]
    print(f"    accented positions (1-indexed): {strong}")
    if fund % 2 and fund not in (3, 9):
        print(f"    NOTE: {fund} is odd — likely an odd meter ({fund}/8 or {fund}/4).")
        print(f"      Look at the two strongest positions; they mark the internal split.")
    elif fund % 4 == 0 and fund > 4:
        print(f"    NOTE: {fund} divides by 4 — this may be a PHRASE "
              f"({fund//4} bars of 4/4) rather than one bar.")
        print(f"      Check whether {fund//2} and {max(fund//4,2)} also score well, and "
              f"whether the profile is one busy bar plus quiet ones (= phrase, not meter).")
    return (fund, margin, strong, downbeat)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--drums", help="separated drums stem (strongly preferred)")
    ap.add_argument("--bass", help="bass stem — used automatically if the drums say nothing")
    ap.add_argument("--other", help="harmonic stem — same fallback role as --bass")
    ap.add_argument("--max", type=int, default=25, help="longest cycle to test")
    ap.add_argument("--foundation", help="reuse a beat grid from foundation.json")
    ap.add_argument("--json", help="write full sweep here")
    a = ap.parse_args()

    bt, beat = pulse_grid(a.audio, a.foundation)
    src = a.drums or a.audio
    y, sr = librosa.load(src, sr=22050, mono=True)
    print(f"pulse {60/beat:.1f} BPM ({beat*1000:.0f} ms), {len(bt)} pulses, "
          f"source {'drums stem' if a.drums else 'full mix'}")
    if not a.drums:
        print("  WARNING: no drums stem. Separate first — full-mix accents are muddier.")

    out, verdicts = {}, {}
    fundamentals, margins = [], []
    weak = 0

    def run(name, rows):
        nonlocal weak
        out[name] = rows
        f = verdict(rows, name)
        verdicts[name] = (dict(cycle=f[0], margin=round(f[1], 2), accented=f[2],
                               downbeat_pulse=f[3]) if f else None)
        if f: fundamentals.append(f[0]); margins.append(f[1])
        else: weak += 1

    for name, (lo, hi) in BANDS.items():
        run(name, sweep(band_pulse_strength(y, sr, bt, beat, lo, hi), a.max))

    # --- fallback: no kit, or a kit that carries no agreed accent
    drum_agree = max((fundamentals.count(f) for f in fundamentals), default=0)
    if drum_agree < 2 and (a.bass or a.other):
        print("\n  drum bands inconclusive — falling back to bass / harmonic stems")
        print("  (a song with no kit still articulates its cycle through pitch)")
        for nm, path in (("bass", a.bass), ("harmonic", a.other)):
            if not path: continue
            yy, _ = librosa.load(path, sr=22050, mono=True)
            lo, hi = FALLBACK[nm]
            run(nm, sweep(band_pulse_strength(yy, sr, bt, beat, lo, hi), a.max))
    tested = len(verdicts)

    print("\n" + "=" * 62)
    agree = max(set(fundamentals), key=fundamentals.count) if fundamentals else None
    n = fundamentals.count(agree) if agree else 0
    if n >= 2:
        print(f"CONSENSUS: {agree} pulses per cycle ({n}/{tested} bands agree)")
        print(f"  cycle = {agree} x {beat*1000:.0f} ms = {agree*beat:.2f} s")
        print(f"  -> ~{(bt[-1]-bt[0])/(agree*beat):.0f} bars across the tracked span")
        mg = float(np.median(margins))
        best = max((v for v in verdicts.values() if v and v["cycle"] == agree),
                   key=lambda v: v["margin"])
        consensus = dict(cycle=agree, bands_agree=n, bands_tested=tested,
                         margin=round(mg, 2), confidence="HIGH" if mg >= 2.0 else "LOW",
                         downbeat_pulse=best["downbeat_pulse"])
        print(f"  downbeat: pulse {best['downbeat_pulse']} of the grid (strongest position)")
        if mg >= 2.0:
            print(f"  confidence HIGH: {mg:.1f}x clear of unrelated periods.")
        else:
            print(f"  confidence LOW: only {mg:.1f}x clear of unrelated periods.")
            print(f"    A low margin on a multiple of 4 usually means plain 4/4 with a")
            print(f"    {agree//4}-bar pattern, not a {agree}-beat bar. Say so, don't overclaim.")
    else:
        consensus = None
        why = (f"{weak}/{tested} bands showed no usable accent"
               if weak else f"the {tested} bands disagree: {fundamentals}")
        print(f"INCONCLUSIVE: {why}.")
        print("  Do NOT pick a meter from this. Common causes: the percussion is an")
        print("  undifferentiated pulse, there is no kit at all, or the part is")
        print("  played rubato. Report the ambiguity rather than resolving it.")
        if not (a.bass or a.other):
            print("  TRY FIRST: re-run with --bass and --other before giving up.")
        print("  ALSO CHECK THE TEMPO OCTAVE: this sweep can only find cycles on the")
        print("  pulse grid it was given. If the tempogram peaks at 2x the tracked")
        print("  pulse, re-run on that grid — a cycle of 8 there is 4 here.")
    print("NEXT: ask the user to count along with the kick. Their ear is ground truth")
    print("      and settles in seconds what this sweep can only rank.")
    print("=" * 62)
    if a.json:
        json.dump(dict(pulse_bpm=60/beat, n_pulses=len(bt), consensus=consensus,
                       verdicts=verdicts, bands=out), open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
