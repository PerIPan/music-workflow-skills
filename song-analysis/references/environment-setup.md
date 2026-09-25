# Environment setup (first-time install)

Read this only when the toolchain isn't installed yet, or a venv broke.

Four virtualenvs, one per role — madmom pins old NumPy/Cython, demucs wants an old torch,
ADTOF and basic-pitch fight over TensorFlow, and Whisper wants a new Python. Keep them
apart. Versions below are the ones this skill's scripts were verified with; pin them, or
new installs drift (librosa 1.0 removed APIs these snippets use; torch ≥ 2.9 +
torchaudio needs FFmpeg 4 on macOS). Apple Silicon recommended; CUDA also works for
demucs.

```bash
# (1) Analysis — madmom, librosa, basic-pitch, crepe; runs scripts/*.py   (Python 3.10)
python3.10 -m venv .venv-bp && source .venv-bp/bin/activate
pip install --upgrade pip wheel
pip install 'numpy==1.26.4' 'setuptools<81' 'cython<3'  # madmom build + pkg_resources
pip install --no-build-isolation \
    'git+https://github.com/CPJKU/madmom.git@27f032e8947204902c675e5e341a3faf5dc86dae'
pip install 'librosa==0.11.0' 'basic-pitch==0.4.0' 'crepe==0.0.16' \
    'pretty_midi==0.2.11' 'soundfile==0.13.1' 'mir_eval==0.8.2' 'tensorflow==2.21.0'
deactivate

# (2) Stems — demucs   (Python 3.11)
python3.11 -m venv .venv-demucs && source .venv-demucs/bin/activate
pip install 'torch==2.4.1' 'torchaudio==2.4.1' 'demucs==4.0.1' 'soundfile==0.13.1'
deactivate                      # first run downloads htdemucs_ft (4 × 84 MB)

# (3) Lyrics — Whisper on Apple Silicon   (any recent Python; verified on 3.13)
python3 -m venv ~/mlx-openai-whisper
~/mlx-openai-whisper/bin/pip install 'mlx-whisper==0.4.3' 'librosa==0.11.0'
# first use downloads mlx-community/whisper-large-v3-turbo (~1.5 GB)

# (4) Optional — ADTOF drum transcription   (Python 3.10)
python3.10 -m venv .venv-adtof && source .venv-adtof/bin/activate
pip install 'numpy==1.26.4' 'tensorflow==2.21.0' 'tf_keras==2.21.0' 'pretty_midi==0.2.11'
pip install git+https://github.com/MZehren/ADTOF.git     # CC BY-NC-SA: install, never vendor
deactivate                      # set TF_USE_LEGACY_KERAS=1 before importing it
```

Notes:
- **madmom** must come from git (PyPI 0.16.1 breaks on Python 3.10) and builds only with
  `cython<3` and `--no-build-isolation`. `setuptools ≥ 81` drops `pkg_resources`, which it
  imports.
- **basic-pitch** runs on TF 2.21 here, outside its tested range (coremltools warns). If
  it breaks, `tensorflow-macos==2.15.1` is the last version it was built against.
- Not on Apple Silicon: `openai-whisper` instead of `mlx-whisper` (drop the alignment-head
  line in `whisper_gated.py`).
- **mlx-demucs** (optional batch path) runs **plain htdemucs** (not `_ft`) ~9× faster than
  torch-CPU demucs; for `_ft`, pass `-d mps` to torch demucs instead (~2.8× faster than
  CPU).
- Smoke tests: `.venv-bp/bin/python tests/test_detect_meter.py` and
  `tests/test_chord_proposal.py` (in `song-analysis/`), `python tests/test_push_notes.py`
  (in `ableton-mcp/`).

## Per-song working directory

Created fresh for each song:

```
<song-slug>/
├── <song>.mp3                          # input
├── lyrics.txt                          # input (canonical text)
├── PLAN.md                             # decisions log
├── analysis/
│   ├── foundation.json                 # pulse, meter, grouping, downbeats, key, bar_bpm
│   ├── meter.json                      # detect_meter.py --json
│   ├── lyrics.json                     # whisper_gated.py words
│   ├── bass.mid                        # bass transcription
│   ├── bass_per_cell.json              # per (bar, cell) pitch classes
│   └── chord_proposal.json             # chord_proposal.py
├── stems/htdemucs_ft/<song>/           # {bass,drums,vocals,other}.wav
└── gen_v<N>.py                         # chart generator (iterate)
```

Final chart HTML can be written anywhere convenient (e.g. a shared cloud-storage folder).
