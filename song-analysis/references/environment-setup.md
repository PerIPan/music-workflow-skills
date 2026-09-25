# Environment setup (first-time install)

Read this only when the analysis toolchain isn't installed yet.

Two virtualenvs — madmom pins old NumPy/Cython, demucs wants torch; keep them apart.
Apple Silicon (M-series) recommended; CUDA also works for demucs.

```bash
# (1) Analysis venv  (Python 3.10 — madmom 0.17.dev0 from GitHub needs <3.12)
python3.10 -m venv .venv-analysis && source .venv-analysis/bin/activate
pip install --upgrade pip wheel
pip install 'numpy<2' 'setuptools<81'                       # madmom wheels + pkg_resources
pip install git+https://github.com/CPJKU/madmom.git@main    # PyPI build breaks on 3.10
pip install librosa pretty_midi mido soundfile basic-pitch crepe
deactivate

# (2) Demucs venv  (Python 3.11)
python3.11 -m venv .venv-demucs && source .venv-demucs/bin/activate
pip install --upgrade pip wheel
pip install demucs==4.0.1        # first run downloads htdemucs_ft (4 × 84 MB)
deactivate

# (3) Whisper venv  (Apple Silicon; any recent Python)
python3 -m venv ~/mlx-openai-whisper && ~/mlx-openai-whisper/bin/pip install mlx-whisper
# first use downloads mlx-community/whisper-large-v3-turbo (~1.6 GB)
```

Notes:
- Not on Apple Silicon: use `openai-whisper` instead of `mlx-whisper`.
- On Apple Silicon, `mlx-demucs` runs **plain htdemucs** (not `_ft`) ~9× faster than
  torch-CPU demucs. For `_ft`, pass `-d mps` to torch demucs instead (~2.8× faster than CPU).
- Optional chord cross-check (autochord / Chordino): `pip install vamp` in a third venv +
  `brew install vamp-plugin-sdk` + the chordino/nnls-chroma plugin in
  `~/Library/Audio/Plug-Ins/Vamp/`. Rarely needed — the chroma+bass-root proposal
  outperforms it.

## Per-song working directory

Created fresh for each song:

```
<song-slug>/
├── <song>.mp3                          # input
├── lyrics.txt                          # input (canonical text)
├── PLAN.md                             # decisions log
├── analysis/
│   ├── foundation.json                 # bpm, downbeats, key
│   ├── lyrics.json                     # Whisper word-level
│   ├── bass.mid                        # bass transcription
│   ├── bass_per_bh.json                # per (bar, half) pitch classes
│   └── chord_proposal.json             # chroma+bass-root proposals
├── stems/htdemucs_ft/<song>/           # {bass,drums,vocals,other}.wav
└── gen_v<N>.py                         # chart generator (iterate)
```

Final chart HTML can be written anywhere convenient (e.g. a shared cloud-storage folder).
