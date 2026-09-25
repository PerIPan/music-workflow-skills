#!/usr/bin/env python3
"""Smoke test for scripts/detect_meter.py on synthetic click tracks.

Each case renders a pulse train whose accents repeat every N pulses (loud
downbeat, medium group starts, ghost notes elsewhere) and checks the reported cycle.
Coprime cases (5, 7, 11) are the ones a 4/4-shaped test cannot see.

Run with the analysis venv (needs numpy, librosa, soundfile; no madmom):
    <venv>/bin/python tests/test_detect_meter.py
"""
import json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "detect_meter.py"
SR, PULSE = 22050, 0.4                                  # 150 BPM pulse
CASES = [  # name, grouping (None = no accent), accepted cycles (None = INCONCLUSIVE)
    ("4/4", [2, 2], {2, 4}),        # duple: the bar-level accent is too faint to insist on 4
    ("3/4", [3], {3}),
    ("6/8 as 3+3", [3, 3], {3, 6}),
    ("5/4 as 3+2", [3, 2], {5}),
    ("7/8 as 2+2+3", [2, 2, 3], {7}),
    ("11/8 as 6+5", [6, 5], {11}),
    ("flat pulse", None, {None}),
]


def render(grouping, n_pulses=176):
    rng = np.random.default_rng(0)
    # a real stem is never digitally silent: without a bleed floor, log-scaled onset
    # strength makes a ghost note on silence look almost as big as a downbeat
    y = 0.02 * rng.standard_normal(int(SR * PULSE * (n_pulses + 2)))
    starts = set(np.cumsum([0] + (grouping or [1])[:-1]))
    cycle = sum(grouping) if grouping else 1
    t = np.arange(int(SR * 0.12)) / SR
    env = np.exp(-t * 40)
    for i in range(n_pulses):
        pos = i % cycle
        acc = (1.0 if pos == 0 else 0.5 if pos in starts else 0.05) if grouping else 0.6
        burst = acc * env * (np.sin(2 * np.pi * 60 * t) + np.sin(2 * np.pi * 300 * t)
                             + 0.3 * rng.standard_normal(len(t)))
        k = int(SR * PULSE * (i + 1))
        y[k:k + len(t)] += burst
    return y / np.abs(y).max() * 0.9, [PULSE * (i + 1) for i in range(n_pulses)]


def main():
    fails = 0
    with tempfile.TemporaryDirectory() as d:
        for name, grouping, want in CASES:
            y, beats = render(grouping)
            wav, fj, out = (Path(d) / f for f in ("x.wav", "f.json", "o.json"))
            sf.write(wav, y, SR)
            json.dump({"beat_times": beats}, open(fj, "w"))
            subprocess.run([sys.executable, str(SCRIPT), str(wav), "--drums", str(wav),
                            "--foundation", str(fj), "--json", str(out)],
                           check=True, capture_output=True)
            cons = json.load(open(out))["consensus"]
            got = cons["cycle"] if cons else None
            ok = got in want and (cons is None or cons["downbeat_pulse"] == 0)  # beat 1 = pulse 0
            fails += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {name:14s} want {sorted(want, key=str)}  got {got}"
                  + (f"  ({cons['confidence']}, {cons['margin']}x, downbeat pulse "
                     f"{cons['downbeat_pulse']})" if cons else ""))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
