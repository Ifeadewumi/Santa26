# Santa 2026 – run log

Record of every step in this session, in order. Scores are total instructions (lower is better). All numbers come from the Python verifier `solver/elf.py` unless stated otherwise.

## 0. Setup (2026-11-24)
- Created the personal cloud environment `santa26`, allowing `www.kaggle.com`, `api.kaggle.com` and `storage.googleapis.com`. Kaggle credentials are at `~/.kaggle/kaggle.json` (container only, not committed).
- Downloaded the data with `kaggle competitions download -c santa-2026`: `puzzles.csv` (1,000 scored puzzles), `practice_puzzles.csv` (200 puzzles with `family`, `design_tier` and `lower_bound` columns) and `sample_submission.csv`.

## 1. Data profile
- Scored set: 1,000 puzzles, all with R=48 registers. 26,902 targets in total (1 to 32 per puzzle, median 30). 1 to 8 starting values (mostly 2 to 5).
- Value limits: mostly 1e12 to 1e17. 37 puzzles have a limit ≤ 1e5 (tiny or exactly solvable).
- Trivial lower bound (number of targets not among the starting values): **26,898**.
- `sample_submission.csv` scores **1,490,379** and is valid. It uses naive double-and-add.
- Practice families: shared 51, mixed 48, independent 45, multiplicative 40, tiny 16. In "shared", targets come in near-duplicate clusters (e.g. 1867940 and 1868647).

## 2. Solver v1 smoke test
- `solver.cpp` v1, compiled with `g++ -O2 -march=native`. On scored_0001 (32 targets) with a 20 s budget on 1 thread it found 268 instructions in 15 portfolio runs. The Python verifier accepts it.
