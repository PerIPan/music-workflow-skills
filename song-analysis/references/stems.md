# Stems — separation options, speed, cache, quality

Read this when Phase 2 is slow, a model isn't cached, or a stem sounds wrong.

## Default: `htdemucs_ft` on the GPU

```bash
demucs -n htdemucs_ft -d mps -o stems <song.mp3>     # demucs 4.0.1, torch 2.4.1
```

- **`-d mps` on Apple Silicon.** demucs 4.0.1 defaults to CUDA-else-CPU, so without the
  flag it runs on the CPU. Measured on an M3 (30 s clip): CPU 64.5 s, MPS 23.0 s, stems
  within noise of each other.
- **Meter-only runs** need just the drums: `--two-stems=drums`.
- **Cache check first:** `du -sh ~/.cache/torch/hub/checkpoints` (4.0.1; 4.1.x loads from
  the Hugging Face cache). `htdemucs_ft` is a bag of 4 models, 4 × 84 MB. Uncached, the
  command downloads silently for as long as the connection takes — ~100 min at 3 MB/min
  once — and piping through `tail` hides all progress. Don't assume it's cached because
  it was used on a previous song.

## Alternatives, measured

| Option | Speed (M3) | Use when |
|---|---|---|
| `htdemucs_ft -d mps` (torch) | 66 s for a 2-min song | default |
| `mlx-demucs` (plain htdemucs) | 28 s for a 4-min song | batches; quality slightly below `_ft` |
| `demucs-mlx -n htdemucs_ft` | 96 s for the same 2-min song | never — slower than torch MPS, same output (22–29 dB SNR) |
| `htdemucs_6s` | — | isolating guitar/piano only; never for bass (bleeds keys into it) |
| BS-RoFormer-SW 6-stem (`audio-separator`) | 0.67× real time | a real piano/guitar stem matters; no chord gain (92.1 vs 91.5%), 699 MB, licence undeclared |

`mlx-demucs`: call its venv binary directly — `uv run mlx-demucs` re-resolves dependencies
over the network and hangs 10+ minutes. Its README lists `htdemucs_ft`, but only plain
htdemucs weights ship with it.

## Quality checks

- Listen to `bass.wav` alone: piano/guitar bleed means separation struggled; suppress
  bass-derived annotations where it does.
- Before the bass enters, the bass stem contains bleed — find the entry bar.
- The drums stem can be quiet (peaks around −5 dBFS): normalise before any level-sensitive
  tool (ADTOF).
