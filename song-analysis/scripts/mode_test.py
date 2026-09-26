#!/usr/bin/env python3
"""Mode test: name the mode by measuring its characteristic degrees, bar by bar.

Key estimators know only major and minor. This takes the tonic from the bass (the
pitch class it sustains longest) and then duels each characteristic degree against
its neighbour in narrow bands (+-20 cents, 3 octaves) of the harmonic stem, one
vote per bar:

    third        3 vs b3   -> major side or minor side
    major side   4 vs #4   (Ionian vs Lydian),   7 vs b7 (Ionian vs Mixolydian),
                 2 vs b2   (Phrygian dominant, with a major third)
    minor side   2 vs b2   (Aeolian/Dorian vs Phrygian), 6 vs b6 (Dorian vs Aeolian)

A duel is decided at >= 70% of the voting bars, "mixed" below that (a moving
degree or modal mixture), "undetermined" when neither degree sounds (a drone with
no 6th cannot be Dorian or Aeolian). The madmom key is reported as information
only - it names the melody's major/minor key and is wrong on modal music by design.
Bins are 12-TET: on microtonal chant a degree's energy can split between bins.

Usage (analysis venv):
    mode_test.py --other stems/htdemucs_ft/<song>/other.wav --foundation analysis/foundation.json \
        --bass-cells analysis/bass_per_cell.json [--sections analysis/sections.json] \
        [--tonic E] [--out analysis/mode.json]
"""
import argparse, json
import numpy as np
import librosa

PCN = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
DECIDE = 0.7
SOUNDS = 0.1                # a degree votes only at >= 10% of the bar's chord-tone energy
MIN_SECTION_BARS = 8        # a new tonic must hold this long to count as a key change


def tonic_from(cells, bars=None):
    tot = np.zeros(12)
    for c in cells:
        if bars is None or c["bar"] in bars:
            for pc, s in c["pc_seconds"].items():
                tot[PCN.index(pc)] += s
    if tot.sum() == 0:
        return None, 0.0
    i = int(np.argmax(tot))
    return i, float(tot[i] / tot.sum())


class Energy:
    def __init__(self, path):
        y, sr = librosa.load(path, sr=22050, mono=True)
        self.C = np.abs(librosa.cqt(y, sr=sr, fmin=librosa.note_to_hz("C3"),
                                    n_bins=60 * 3, bins_per_octave=60))   # 20-cent bins
        self.t = librosa.times_like(self.C, sr=sr)

    def degree(self, pc, t0, t1):
        f = (self.t >= t0) & (self.t < t1)
        bins = [o * 60 + pc * 5 + d for o in range(3) for d in (-1, 0, 1)]
        return float(self.C[[b for b in bins if 0 <= b < self.C.shape[0]]][:, f].sum())

    def reference(self, t0, t1):
        """Median energy of the bar's three strongest pitch classes (its chord tones)."""
        e = sorted((self.degree(pc, t0, t1) for pc in range(12)), reverse=True)
        return float(np.median(e[:3]))


def duel(E, tonic, a, b, spans):
    """Votes per bar for degree a vs degree b (semitones above the tonic)."""
    wa = wb = 0
    for t0, t1 in spans:
        ea, eb = E.degree((tonic + a) % 12, t0, t1), E.degree((tonic + b) % 12, t0, t1)
        if max(ea, eb) >= SOUNDS * E.reference(t0, t1):   # silent degrees don't vote
            wa += ea > eb
            wb += eb >= ea
    n = wa + wb
    verdict = ("undetermined" if n == 0 else "a" if wa / n >= DECIDE else
               "b" if wb / n >= DECIDE else "mixed")
    return dict(wins=[wa, wb], verdict=verdict)


def name_mode(E, tonic, spans):
    third = duel(E, tonic, 4, 3, spans)                 # a = major 3rd
    d = dict(third=third)
    if third["verdict"] == "a":
        d["4_vs_#4"] = duel(E, tonic, 5, 6, spans)
        d["7_vs_b7"] = duel(E, tonic, 11, 10, spans)
        d["2_vs_b2"] = duel(E, tonic, 2, 1, spans)
        four, seven, two = d["4_vs_#4"]["verdict"], d["7_vs_b7"]["verdict"], d["2_vs_b2"]["verdict"]
        if two == "b":
            mode = "phrygian-dominant"
        elif four == "b" and seven == "a":
            mode = "lydian"
        elif four == "b" and seven == "b":
            mode = "lydian-dominant"
        elif four == "a" and seven == "b":
            mode = "mixolydian"
        elif four == "a" and seven == "a":
            mode = "ionian"
        else:
            mode = "major (4th/7th " + "/".join(v for v in (four, seven)) + ")"
    elif third["verdict"] == "b":
        d["2_vs_b2"] = duel(E, tonic, 2, 1, spans)
        d["6_vs_b6"] = duel(E, tonic, 9, 8, spans)
        two, six = d["2_vs_b2"]["verdict"], d["6_vs_b6"]["verdict"]
        mode = {("a", "a"): "dorian", ("a", "b"): "aeolian", ("b", "b"): "phrygian",
                ("b", "a"): "dorian-b2"}.get((two, six), f"minor (2nd {two}, 6th {six})")
    else:
        mode = f"third {third['verdict']}"
    return mode, d


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--other", required=True, help="harmonic stem")
    ap.add_argument("--foundation", required=True)
    ap.add_argument("--bass-cells", help="bass_notes.py bass_per_cell.json (tonic source)")
    ap.add_argument("--tonic", help="override, e.g. E")
    ap.add_argument("--sections", help="align_lyrics.py sections.json for per-section modes")
    ap.add_argument("--out", default="analysis/mode.json")
    a = ap.parse_args()
    F = json.load(open(a.foundation))
    db = F["downbeat_times"]
    bars = list(zip(db[:-1], db[1:]))
    cells = json.load(open(a.bass_cells))["cells"] if a.bass_cells else []
    if a.tonic:
        tonic, share = PCN.index(a.tonic), None
    else:
        tonic, share = tonic_from(cells)
        if tonic is None:
            raise SystemExit("no tonic: pass --bass-cells from bass_notes.py or --tonic")
    E = Energy(a.other)
    mode, duels = name_mode(E, tonic, bars)
    res = dict(song=dict(tonic=PCN[tonic], mode=mode, tonic_share=share and round(share, 2),
                         duels=duels),
               key_cnn_info=F.get("key_top2"))
    print(f"tonic {PCN[tonic]}" + (f" ({share:.0%} of bass time)" if share else " (given)") +
          f" -> {mode}")
    for k, v in duels.items():
        print(f"  {k:8s} wins {v['wins'][0]:3d} : {v['wins'][1]:<3d} -> {v['verdict']}")

    if a.sections and cells:
        secs = json.load(open(a.sections))["sections"]
        starts = [s["where"][0] if s.get("where") else None for s in secs]
        out = []
        for k, s in enumerate(secs):
            b0 = starts[k]
            b1 = next((x for x in starts[k + 1:] if x), len(bars) + 1)
            if not b0 or b1 <= b0:
                continue
            rng = set(range(b0, b1))
            t, sh = tonic_from(cells, rng)
            if t is None:
                continue
            m, _ = name_mode(E, t, bars[b0 - 1:b1 - 1])
            out.append(dict(label=s["label"], bars=[b0, b1 - 1], tonic=PCN[t], mode=m,
                            tonic_change=bool(t != tonic and (b1 - b0) >= MIN_SECTION_BARS)))
        res["sections"] = out
        for o in out:
            print(f"  {o['label']:10s} bars {o['bars'][0]}-{o['bars'][1]}: {o['tonic']} {o['mode']}"
                  + ("  <- tonic change" if o["tonic_change"] else ""))
    if F.get("key_top2"):
        print(f"  (madmom key, the melody's major/minor: {F['key_top2'][0][0]} - info only)")
    json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
