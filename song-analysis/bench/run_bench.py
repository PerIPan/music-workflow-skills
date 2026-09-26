#!/usr/bin/env python3
"""Score the pipeline's artifacts against local ground truth.

Truth and audio never enter this repo: point $MWS_BENCH_ROOT (or --manifest) at a
local folder holding manifest.json, keyed by opaque song IDs:

    {"songs": [{"id": "s01", "analysis": "work/s01/analysis",
                "truth": {"meter":    {"bar_seconds": 4.1, "grouping": [6, 5]},
                          "chords":   {"lab": "truth/s01.lab"}          # time-aligned Harte
                                   or {"cycle": ["F#:min", ...], "anchor_bar": 7},
                                   or {"all": "E:maj7"},
                          "sections": {"times": [0.1, 22.9, ...]},     # boundary seconds
                          "mode":     {"tonic": "E", "mode": "lydian"},
                          "lyrics":   {"text": "truth/s01.txt"},
                          "lines":    {"json": "truth/s01_lines.json"}}}]}   # [{start, text}]

Relative paths resolve from the manifest's folder. Each task reads the standard
artifact names in the song's analysis folder (meter.json, chords_lv.json,
chord_proposal.json, sections.json, mode.json, lyrics.json, lyrics_aligned.json).
Meter is scored from the sweep's own consensus, before any user answer, in SECONDS:
the found cycle's duration vs the true bar's, so a double-time grid that finds "8"
for a 4/4 bar counts as right. A cycle of 2 or 4 bars counts as a phrase (consistent),
anything else as wrong; grouping is compared only when the cycle is the bar.

Human ceiling for chords: four expert annotators agreed on 73% (maj/min) and 54%
(full labels) of Billboard segments (CASD, Koops et al. 2019) - scores above that
on hard songs deserve suspicion, not celebration.

Usage (analysis venv: needs numpy + mir_eval):
    run_bench.py [--manifest PATH] [--tasks meter,chords,...] [--json out.json]
                 [--baseline prev.json]   # exit 1 on a drop of more than 2 points
"""
import argparse, json, os, re, sys, unicodedata
from pathlib import Path
import numpy as np

TASKS = ("meter", "chords", "sections", "mode", "lyrics", "lines")


def harte(label):
    """Our triad names ('F#m', 'A', 'C#7/F') or Harte labels -> Harte."""
    if not label or label in ("N", "X"):
        return "N"
    if ":" in label:
        return label
    bass = None
    if "/" in label:
        label, bass = label.split("/", 1)
    for suffix, q in (("maj7", "maj7"), ("m7", "min7"), ("7", "7"), ("m", "min")):
        if label.endswith(suffix):
            return f"{label[:-len(suffix)]}:{q}" + (f"/{bass}" if bass else "")
    return f"{label}:maj" + (f"/{bass}" if bass else "")


def load_lab(path):
    rows = [l.split() for l in open(path) if l.strip()]
    return [(float(a), float(b), c) for a, b, c in rows]


def overlap_label(segs, t0, t1):
    best, cover = None, 0.0
    for a, b, c in segs:
        o = min(t1, b) - max(t0, a)
        if o > cover:
            best, cover = c, o
    return best


def norm_words(text):
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).replace("ς", "σ")
    return re.findall(r"[\w']+", text)


def wer(ref, hyp):
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
    return d[-1] / max(len(ref), 1)


def score_song(song, root, tasks):
    A = (root / song["analysis"]).resolve()
    T = song["truth"]
    res = {}
    rd = lambda n: json.load(open(A / n)) if (A / n).exists() else None

    if "meter" in tasks and "meter" in T and rd("meter.json"):
        m = rd("meter.json")
        c, want = m.get("consensus"), T["meter"]
        if not c:
            res["meter"] = dict(verdict="inconclusive", consistent=False)
        else:
            ratio = c["cycle"] * 60.0 / m["pulse_bpm"] / want["bar_seconds"]
            near = lambda x: abs(ratio / x - 1) < 0.08
            verdict = ("bar" if near(1) else "phrase x2" if near(2) else "phrase x4" if near(4)
                       else "half-bar" if near(0.5) else f"wrong ({ratio:.2f} bars)")
            gs = [c.get("grouping"), c.get("alternative", {}).get("grouping")]
            # compare splits as positions within the bar: 4+4 eighths == 2+2 quarters
            split = lambda g: g and [round(sum(g[:i + 1]) / sum(g), 3) for i in range(len(g) - 1)]
            same = lambda g: bool(g) and split(g) == split(want.get("grouping"))
            res["meter"] = dict(verdict=verdict, consistent=verdict == "bar" or verdict.startswith("phrase"),
                                grouping_ok=verdict == "bar" and same(gs[0]),
                                grouping_ok_with_alternative=verdict == "bar" and any(same(g) for g in gs),
                                got=f"{c['cycle']} pulses at {m['pulse_bpm']:.0f} BPM, {gs[0]}"
                                    + (f" (alt {gs[1]})" if gs[1] else ""))

    if "chords" in tasks and "chords" in T:
        import mir_eval
        F = rd("foundation.json") or {}
        arts = sorted(x.name for x in A.glob("chords_*.json")) + ["chord_proposal.json"]
        for art in arts:
            data = rd(art)
            if not data:
                continue
            cells = data["cells"]
            spec = T["chords"]
            if "lab" in spec:
                segs = load_lab(root / spec["lab"])
                ref = [overlap_label(segs, c["t0"], c["t1"]) for c in cells]
            elif "cycle" in spec:
                ref = [spec["cycle"][(c["bar"] - spec["anchor_bar"]) % len(spec["cycle"])]
                       if c["bar"] >= spec["anchor_bar"] else None for c in cells]
            else:
                ref = [spec["all"] for c in cells]
            pairs = [(r, harte(c["chord"])) for r, c in zip(ref, cells) if r and r != "N"]
            if not pairs:
                continue
            r, e = zip(*pairs)
            out = {}
            for m in ("root", "majmin", "sevenths", "majmin_inv"):
                v = np.asarray(getattr(mir_eval.chord, m)(list(r), list(e)), float)
                out[m] = round(float(v[v >= 0].mean() * 100), 1) if (v >= 0).any() else None
            res[f"chords:{art.split('.')[0]}"] = out

    if "sections" in tasks and "sections" in T and rd("sections.json"):
        import mir_eval
        ref_t = sorted(T["sections"]["times"])
        est_t = sorted(s["t"] for s in rd("sections.json")["sections"])
        end = max(ref_t[-1], est_t[-1] if est_t else 0) + 1
        iv = lambda b: np.array(list(zip([0.0] + b, b + [end])))
        bar = float(np.median(np.diff(rd("foundation.json")["downbeat_times"]))) \
            if rd("foundation.json") else 2.0
        res["sections"] = {f"F@{lab}": round(mir_eval.segment.detection(
            iv(ref_t), iv(est_t), window=w, trim=True)[2] * 100, 1)
            for w, lab in ((0.5, "0.5s"), (bar, "1bar"))}

    if "mode" in tasks and "mode" in T and rd("mode.json"):
        m = rd("mode.json")["song"]
        res["mode"] = dict(ok=(m.get("tonic"), m.get("mode")) == (T["mode"]["tonic"], T["mode"]["mode"]),
                           got=f"{m.get('tonic')} {m.get('mode')}")

    if "lyrics" in tasks and "lyrics" in T and rd("lyrics.json"):
        ref = norm_words(open(root / T["lyrics"]["text"]).read())
        hyp = norm_words(" ".join(w["word"] for w in rd("lyrics.json")["words"]))
        res["lyrics"] = dict(wer=round(wer(ref, hyp) * 100, 1), ref_words=len(ref), hyp_words=len(hyp))

    if "lines" in tasks and "lines" in T and rd("lyrics_aligned.json"):
        truth = json.load(open(root / T["lines"]["json"]))
        truth = truth["lines"] if isinstance(truth, dict) else truth
        got = [l.get("start") for l in rd("lyrics_aligned.json")["lines"]]
        n = min(len(truth), len(got))
        err = [abs(got[i] - truth[i]["start"]) for i in range(n) if got[i] is not None]
        res["lines"] = dict(n=n, within_0_5s=round(100 * float(np.mean([e <= 0.5 for e in err])), 1),
                            within_1s=round(100 * float(np.mean([e <= 1.0 for e in err])), 1),
                            median_err_s=round(float(np.median(err)), 2)) if err else None
    return res


def flatten(results):
    flat = {}
    for sid, r in results.items():
        for task, v in r.items():
            if isinstance(v, dict):
                for k, x in v.items():
                    if isinstance(x, (int, float)) and not isinstance(x, bool):
                        flat[f"{sid}/{task}/{k}"] = x
                    elif isinstance(x, bool):
                        flat[f"{sid}/{task}/{k}"] = 100.0 * x
    return flat


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--manifest", default=os.path.join(os.environ.get("MWS_BENCH_ROOT", "."),
                                                        "manifest.json"))
    ap.add_argument("--tasks", default=",".join(TASKS))
    ap.add_argument("--json")
    ap.add_argument("--baseline")
    a = ap.parse_args()
    mpath = Path(a.manifest)
    if not mpath.exists():
        sys.exit(f"no manifest at {mpath} - set MWS_BENCH_ROOT or pass --manifest")
    M = json.load(open(mpath))
    tasks = set(a.tasks.split(","))
    results = {s["id"]: score_song(s, mpath.parent, tasks) for s in M["songs"]}
    for sid, r in results.items():
        for task, v in r.items():
            print(f"{sid:8s} {task:24s} {v}")
    if a.json:
        json.dump(results, open(a.json, "w"), indent=1)
    if a.baseline:
        old, new = flatten(json.load(open(a.baseline))), flatten(results)
        drops = [(k, old[k], new[k]) for k in old if k in new and "err" not in k
                 and new[k] < old[k] - 2]
        for k, o, n in drops:
            print(f"REGRESSION {k}: {o} -> {n}")
        sys.exit(1 if drops else 0)


if __name__ == "__main__":
    main()
