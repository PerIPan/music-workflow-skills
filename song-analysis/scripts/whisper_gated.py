#!/usr/bin/env python3
"""Phase 4: lyric word timing with mlx-whisper, gated on where the vocal stem is sung.

An RMS gate on the separated vocal stem becomes Whisper's clip_timestamps, so it
never transcribes silence (cut long-form lyric WER 22.9% -> 20.7% and most filler
hallucinations on separated vocals, arXiv 2506.15514). Also sets large-v3-turbo's
curated word-alignment heads, which mlx-whisper does not set itself, and drops
words whose whole span lies outside the gate.

Usage (the Whisper venv; Apple Silicon, needs mlx-whisper + librosa):
    <whisper-venv>/bin/python whisper_gated.py stems/<song>/vocals.wav \
        [--language en] [--gate 0.1] [--out analysis/lyrics.json]
"""
import argparse, json
import numpy as np
import librosa
import mlx.core as mx
import mlx_whisper
from mlx_whisper.transcribe import ModelHolder

REPO = "mlx-community/whisper-large-v3-turbo"     # large-v3 = extra ~3 GB, no gain
TURBO_HEADS = b"ABzY8j^C+e0{>%RARaKHP%t(lGR*)0g!tONPyhe`"   # openai-whisper's mask
HOP = 512


def sung_clips(y, sr, gate):
    """RMS gate -> padded [start, end] clips: merge gaps < 1 s, cap 30 s, pad 0.4 s."""
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=HOP)[0]
    t = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=HOP)
    sung = rms > gate * rms.max()
    segs, start = [], None
    for ti, on in zip(t, sung):
        if on and start is None: start = ti
        if not on and start is not None: segs.append([start, ti]); start = None
    if start is not None: segs.append([start, t[-1]])
    merged = []
    for s0, e0 in segs:
        if merged and s0 - merged[-1][1] < 1.0 and e0 - merged[-1][0] <= 30:
            merged[-1][1] = e0
        else:
            merged.append([s0, e0])
    dur = len(y) / sr
    # pad: sung onsets often lead the audible voice
    return [(max(0.0, s0 - 0.4), min(dur, e0 + 0.4)) for s0, e0 in merged], t, sung


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("vocals", help="separated vocal stem")
    ap.add_argument("--language", help="force it when auto-detect wobbles (chant, non-English)")
    ap.add_argument("--gate", type=float, default=0.1, help="fraction of max RMS counted as sung")
    ap.add_argument("--out", help="write words JSON here")
    a = ap.parse_args()

    y, sr = librosa.load(a.vocals, sr=16000, mono=True)
    clips, t, sung = sung_clips(y, sr, a.gate)
    ModelHolder.get_model(REPO, mx.float16).set_alignment_heads(TURBO_HEADS)
    res = mlx_whisper.transcribe(
        a.vocals, path_or_hf_repo=REPO, word_timestamps=True,
        clip_timestamps=[x for c in clips for x in c],
        condition_on_previous_text=False,          # avoids hallucination drift
        hallucination_silence_threshold=2.0, language=a.language)

    def in_gate(w):                                # judge the WHOLE span, not the start
        m = (t >= w["start"]) & (t <= w["end"])
        return bool(m.any() and sung[m].any())

    allw = [dict(word=w["word"].strip(), start=round(w["start"], 3), end=round(w["end"], 3),
                 probability=round(w.get("probability", 0.0), 3))
            for seg in res["segments"] for w in seg.get("words", [])]
    words = [w for w in allw if in_gate(w)]
    dropped = [w for w in allw if not in_gate(w)]
    sung_s = sum(e - s for s, e in clips)
    print(f"{len(clips)} sung clips, {sung_s:.0f}/{len(y) / sr:.0f} s; "
          f"{len(words)} words kept, {len(dropped)} dropped as silence; "
          f"language {res.get('language')}")
    if a.out:
        json.dump(dict(model=REPO, language=res.get("language"), clips=clips,
                       words=words, dropped=dropped), open(a.out, "w"),
                  indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
