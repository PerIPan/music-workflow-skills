#!/usr/bin/env python3
"""Write analysis/foundation.json in two steps: pulse + key first, meter after the sweep.

    foundation.py pulse <song.mp3> --out analysis/foundation.json
        madmom beats with NO bar assumption, pulse BPM, madmom CNN key (top two).

    foundation.py meter --foundation analysis/foundation.json --meter analysis/meter.json
        [--cycle N] [--grouping 6,5] [--downbeat-pulse K] [--use-alternative]
        [--pulse-unit 4|8]
        Adds the meter from detect_meter.py --json: beats_per_bar, pulse_unit,
        grouping, downbeat_times, num_bars, bar_bpm, tempo_drift_pct, live_tempo.

The meter step refuses to guess. It stops with the question to ask the user when
the sweep was INCONCLUSIVE, found a phrase-length cycle (8/16/24) or a bare duple
(2), could not tell which of two accents is beat 1, or found an odd cycle without
a stated pulse unit (11/8 and 11/4 differ by 2x in Live's tempo).

Run with the analysis venv (madmom + numpy; the meter step needs only numpy).
"""
import argparse, json, sys

CONVENTION = {2: [2], 3: [3], 4: [2, 2], 6: [3, 3], 9: [3, 3, 3], 12: [3, 3, 3, 3]}


def ask(msg):
    """Stop with the question the agent should put to the user."""
    sys.exit(f"NEEDS A DECISION: {msg}")


def cmd_pulse(a):
    import numpy as np
    from madmom.features.beats import RNNBeatProcessor, DBNBeatTrackingProcessor
    from madmom.features.key import CNNKeyRecognitionProcessor, KEY_LABELS
    beats = DBNBeatTrackingProcessor(fps=100)(RNNBeatProcessor()(a.audio))   # no bars
    probs = CNNKeyRecognitionProcessor()(a.audio)[0]
    key_top2 = [[KEY_LABELS[i], round(float(probs[i]), 2)] for i in np.argsort(probs)[::-1][:2]]
    F = dict(audio=a.audio, pulse_bpm=round(60.0 / float(np.median(np.diff(beats))), 2),
             beat_times=[round(float(b), 4) for b in beats], key_top2=key_top2, step="pulse")
    json.dump(F, open(a.out, "w"), indent=1)
    print(f"pulse {F['pulse_bpm']} BPM, {len(beats)} beats; key {key_top2[0][0]} "
          f"(p={key_top2[0][1]}), then {key_top2[1][0]} (p={key_top2[1][1]}) - the melody's "
          f"key; check it against the bass pedal later")


def cmd_meter(a):
    F = json.load(open(a.foundation))
    cons = json.load(open(a.meter)).get("consensus")
    bt = F["beat_times"]

    if cons is None and not a.cycle:
        ask("the meter sweep was INCONCLUSIVE. Ask the user to count along with the kick, "
            "then re-run with --cycle N --grouping a,b [--downbeat-pulse K].")
    found = cons["cycle"] if cons else None
    if found in (8, 16, 24) and not a.cycle:
        ask(f"the sweep found {found} pulses - usually {found // 4} bars of 4/4, not one bar. "
            f"Re-run with --cycle 4 (4/4 with a {found // 4}-bar pattern) or --cycle {found} "
            f"to keep it as one bar.")
    if found == 2 and not a.cycle:
        ask("the sweep found a duple pulse (2) - it can't tell 2/4 from 4/4. Ask the user to "
            "count, then re-run with --cycle 2 or --cycle 4.")
    cycle = a.cycle or found

    if a.downbeat_pulse is not None:
        dp = a.downbeat_pulse
    elif cons and a.use_alternative and "alternative" in cons:
        dp = cons["alternative"]["downbeat_pulse"]
    elif cons:
        if "alternative" in cons and not a.grouping and cycle == found:
            alt = cons["alternative"]
            ask(f"beat 1 is ambiguous - pulse {cons['downbeat_pulse']} "
                f"({'+'.join(map(str, cons['grouping']))}) or pulse {alt['downbeat_pulse']} "
                f"({'+'.join(map(str, alt['grouping']))}). Ask which kick hit is '1', then "
                f"re-run with --use-alternative or --grouping a,b --downbeat-pulse K.")
        dp = cons["downbeat_pulse"] % cycle
    else:
        ask("no downbeat to anchor on - pass --downbeat-pulse K (the beat index the user "
            "counts as '1').")

    if a.grouping:
        grouping = [int(x) for x in a.grouping.split(",")]
    elif cons and cycle == found:
        grouping = (cons["alternative"]["grouping"] if a.use_alternative and "alternative" in cons
                    else cons["grouping"])
    elif cycle in CONVENTION:
        grouping = CONVENTION[cycle]
    else:
        ask(f"no grouping for a {cycle}-pulse bar - pass --grouping (e.g. 3,2 or 6,5).")
    if sum(grouping) != cycle:
        sys.exit(f"grouping {grouping} sums to {sum(grouping)}, not the cycle {cycle}")

    if a.pulse_unit is None and cycle % 2 == 1 and cycle not in (3, 9):
        ask(f"is the pulse an eighth ({cycle}/8) or a quarter ({cycle}/4)? It doubles Live's "
            f"tempo. At {F['pulse_bpm']} BPM "
            f"{'an eighth is likely' if F['pulse_bpm'] >= 140 else 'a quarter is likely'}. "
            f"Re-run with --pulse-unit 8 or 4.")
    unit = a.pulse_unit or 4

    downbeats = bt[dp::cycle]
    bar_bpm = []
    for d0, d1 in zip(downbeats[:-1], downbeats[1:]):
        inside = [b for b in bt if d0 <= b <= d1]
        gaps = sorted(y - x for x, y in zip(inside[:-1], inside[1:]))
        bar_bpm.append(round(60.0 / gaps[len(gaps) // 2], 2))
    med = sorted(bar_bpm)[len(bar_bpm) // 2]
    F.update(beats_per_bar=cycle, pulse_unit=unit, time_signature=f"{cycle}/{unit}",
             grouping=grouping, downbeat_pulse=dp, pickup_pulses=dp,
             downbeat_times=downbeats, num_bars=len(downbeats) - 1, bar_bpm=bar_bpm,
             tempo_drift_pct=round((max(bar_bpm) - min(bar_bpm)) / med * 100, 1),
             live_tempo=round(med * 4 / unit, 3), step="meter")
    json.dump(F, open(a.foundation, "w"), indent=1)
    print(f"{cycle}/{unit} as {'+'.join(map(str, grouping))}, {F['num_bars']} bars from "
          f"{downbeats[0]:.2f}s ({dp} pickup pulses); bar tempo {min(bar_bpm)}-{max(bar_bpm)} "
          f"(drift {F['tempo_drift_pct']}%); Live tempo {F['live_tempo']}")
    if F["tempo_drift_pct"] > 3:
        print("  drift > 3%: place notes through the beat grid, not one BPM")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pulse")
    p.add_argument("audio")
    p.add_argument("--out", default="analysis/foundation.json")
    m = sub.add_parser("meter")
    m.add_argument("--foundation", default="analysis/foundation.json")
    m.add_argument("--meter", default="analysis/meter.json")
    m.add_argument("--cycle", type=int, help="pulses per bar, overriding the sweep")
    m.add_argument("--grouping", help="e.g. 6,5 or 2,2,3")
    m.add_argument("--downbeat-pulse", type=int, help="beat index of the first '1'")
    m.add_argument("--use-alternative", action="store_true",
                   help="take the sweep's alternative beat 1 / grouping")
    m.add_argument("--pulse-unit", type=int, choices=(4, 8))
    a = ap.parse_args()
    cmd_pulse(a) if a.cmd == "pulse" else cmd_meter(a)


if __name__ == "__main__":
    main()
