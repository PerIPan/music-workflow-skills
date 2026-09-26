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
# Cells for common meters follow convention; odd cycles are split at their accents.
# Even cycles: kick accents show the groove (a syncopated kick splits 8 as 5+3), not the
# meter, so they follow convention; an aksak 8 (3+3+2) must come from the user.
CONVENTION = {2: [2], 3: [3], 4: [2, 2], 6: [3, 3], 8: [4, 4], 9: [3, 3, 3], 12: [3, 3, 3, 3]}


def grouping_from(rows, P):
    """Downbeat + main split of cycle P from one band's sweep rows.

    Downbeat = strongest position. Split = where the second-strongest accent falls
    (an 11 with accents 6 pulses apart is 6+5). Only the main split is found - a
    finer aksak grouping (2+2+3) needs the ear. When the two accents are within 10%,
    either could be beat 1: returns the alternative too.
    """
    r = next(x for x in rows if x["period"] == P)
    prof, ph = np.asarray(r["profile"]), r["phase"]
    order = np.argsort(prof)[::-1]
    p1, p2 = int(order[0]), int(order[1])
    down = (ph + p1) % P
    if P in CONVENTION:
        return dict(grouping=CONVENTION[P], downbeat_pulse=down, grouping_source="convention")
    d = (p2 - p1) % P
    grouping = [d, P - d] if min(d, P - d) >= 2 else [P]
    out = dict(grouping=grouping, downbeat_pulse=down, grouping_source="accents")
    if prof[p2] >= 0.9 * prof[p1] and len(grouping) == 2:
        out["alternative"] = dict(grouping=grouping[::-1], downbeat_pulse=(ph + p2) % P)
    return out


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


def analyse(bt, beat, y, sr, stems, pmax, quiet=False):
    """Sweep drum bands (+ bass/harmonic fallback) on grid bt. Returns consensus etc."""
    out, verdicts = {}, {}
    fundamentals, margins = [], []
    weak = 0
    say = (lambda *x, **k: None) if quiet else print

    def run(name, rows):
        nonlocal weak
        out[name] = rows
        f = verdict(rows, name) if not quiet else _silent(verdict, rows, name)
        verdicts[name] = (dict(cycle=f[0], margin=round(f[1], 2), accented=f[2],
                               downbeat_pulse=f[3]) if f else None)
        if f: fundamentals.append(f[0]); margins.append(f[1])
        else: weak += 1

    for name, (lo, hi) in BANDS.items():
        run(name, sweep(band_pulse_strength(y, sr, bt, beat, lo, hi), pmax))
    drum_agree = max((fundamentals.count(f) for f in fundamentals), default=0)
    if drum_agree < 2 and any(stems.values()):
        say("\n  drum bands inconclusive — falling back to bass / harmonic stems")
        say("  (a song with no kit still articulates its cycle through pitch)")
        for nm, path in (("bass", stems.get("bass")), ("harmonic", stems.get("other"))):
            if not path: continue
            yy, _ = librosa.load(path, sr=22050, mono=True)
            lo, hi = FALLBACK[nm]
            run(nm, sweep(band_pulse_strength(yy, sr, bt, beat, lo, hi), pmax))
    tested = len(verdicts)
    agree = max(set(fundamentals), key=fundamentals.count) if fundamentals else None
    n = fundamentals.count(agree) if agree else 0
    if n < 2:
        return None, verdicts, out, dict(weak=weak, tested=tested, fundamentals=fundamentals)
    mg = float(np.median(margins))
    voters = [k for k, v in verdicts.items() if v and v["cycle"] == agree]
    anchor = "kick" if "kick" in voters else max(voters, key=lambda k: verdicts[k]["margin"])
    g = grouping_from(out[anchor], agree)       # beat 1 is counted with the kick
    consensus = dict(cycle=agree, bands_agree=n, bands_tested=tested, margin=round(mg, 2),
                     confidence="HIGH" if mg >= 2.0 else "LOW", anchor_band=anchor, **g)
    return consensus, verdicts, out, dict(weak=weak, tested=tested, fundamentals=fundamentals)


def _silent(fn, *args):
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args)


def uneven_beats(bt):
    """Share of successive beat intervals in a ~3:2 or ~2:3 ratio (aksak read as beats)."""
    ibi = np.diff(bt)
    r = np.log(ibi[1:] / ibi[:-1])
    return float(np.mean(np.abs(np.abs(r) - np.log(1.5)) < 0.1)) if len(r) else 0.0


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
    bpm = 60 / beat
    print(f"pulse {bpm:.1f} BPM ({beat*1000:.0f} ms), {len(bt)} pulses, "
          f"source {'drums stem' if a.drums else 'full mix'}")
    if not a.drums:
        print("  WARNING: no drums stem. Separate first — full-mix accents are muddier.")
    stems = dict(bass=a.bass, other=a.other)
    uneven = uneven_beats(bt)
    if uneven > 0.25:
        print(f"  WARNING: {uneven:.0%} of successive beat intervals are ~3:2 - the tracker may")
        print("    be following aksak groups (2+2+3) as uneven beats. Track the fast pulse:")
        print(f"    foundation.py pulse --min-bpm {bpm * 1.6:.0f}  (then re-run this sweep)")

    consensus, verdicts, out, info = analyse(bt, beat, y, sr, stems, a.max)
    tested = info["tested"]

    # A half-time grid hides odd cycles (a 7 of eighths is invisible on quarters), and a
    # slow pulse is often half-time: try the grid subdivided by 2 before giving up.
    subdivided = None
    if consensus is None or bpm < 70:
        fine = np.sort(np.concatenate([bt, (bt[:-1] + bt[1:]) / 2]))
        c2, _, _, _ = analyse(fine, beat / 2, y, sr, stems, a.max, quiet=True)
        if c2:
            subdivided = dict(factor=2, pulse_bpm=round(bpm * 2, 1), consensus=c2)

    print("\n" + "=" * 62)
    if consensus:
        agree, g = consensus["cycle"], consensus
        print(f"CONSENSUS: {agree} pulses per cycle ({consensus['bands_agree']}/{tested} bands agree)")
        print(f"  cycle = {agree} x {beat*1000:.0f} ms = {agree*beat:.2f} s")
        print(f"  -> ~{(bt[-1]-bt[0])/(agree*beat):.0f} bars across the tracked span")
        print(f"  downbeat: pulse {g['downbeat_pulse']} of the grid ({g['anchor_band']} band); "
              f"grouping {'+'.join(map(str, g['grouping']))} ({g['grouping_source']})")
        if "alternative" in g:
            alt = g["alternative"]
            print(f"  AMBIGUOUS: the two strongest {g['anchor_band']} accents are within 10% - beat 1 may")
            print(f"    be pulse {alt['downbeat_pulse']} instead, giving "
                  f"{'+'.join(map(str, alt['grouping']))}. Ask the user which hit is '1'.")
        mg = consensus["margin"]
        if mg >= 2.0:
            print(f"  confidence HIGH: {mg:.1f}x clear of unrelated periods.")
        else:
            print(f"  confidence LOW: only {mg:.1f}x clear of unrelated periods.")
            print(f"    A low margin on a multiple of 4 usually means plain 4/4 with a")
            print(f"    {agree//4}-bar pattern, not a {agree}-beat bar. Say so, don't overclaim.")
        if bpm > 160:
            print(f"  FAST PULSE ({bpm:.0f} BPM): probably eighth notes - the quarter tempo is "
                  f"~{bpm/2:.0f}. Say so when choosing the pulse unit.")
    else:
        why = (f"{info['weak']}/{tested} bands showed no usable accent"
               if info["weak"] else f"the {tested} bands disagree: {info['fundamentals']}")
        print(f"INCONCLUSIVE: {why}.")
        print("  Do NOT pick a meter from this. Common causes: the percussion is an")
        print("  undifferentiated pulse, there is no kit at all, or the part is")
        print("  played rubato. Report the ambiguity rather than resolving it.")
        if not (a.bass or a.other):
            print("  TRY FIRST: re-run with --bass and --other before giving up.")
    if subdivided:
        c2 = subdivided["consensus"]
        print(f"ON A 2x GRID ({subdivided['pulse_bpm']} BPM): cycle {c2['cycle']} "
              f"({c2['confidence']}, {c2['margin']}x), grouping "
              f"{'+'.join(map(str, c2['grouping']))}. If the user's count agrees, adopt it:")
        print(f"  foundation.py pulse <song> --min-bpm {bpm * 1.6:.0f}  then re-run this sweep")
    print("NEXT: ask the user to count along with the kick. Their ear is ground truth")
    print("      and settles in seconds what this sweep can only rank.")
    print("=" * 62)
    if a.json:
        json.dump(dict(pulse_bpm=bpm, n_pulses=len(bt), uneven_beats=round(uneven, 2),
                       consensus=consensus, subdivided=subdivided, verdicts=verdicts, bands=out),
                  open(a.json, "w"), indent=1)


if __name__ == "__main__":
    main()
