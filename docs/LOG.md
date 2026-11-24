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

## 3. Practice-set diagnostic, solver v1 (about 6 s per puzzle, 4 threads, 300 s total)
Command: `solver --puzzles practice.txt --out prac_v1.txt --total 300 --threads 4`. All 200 programs are valid.

| family | n | instructions | lower bound | ratio |
|---|---|---|---|---|
| independent | 45 | 12,071 | 1,307 | 9.24 |
| mixed | 48 | 10,187 | 1,356 | 7.51 |
| multiplicative | 40 | 4,727 | 1,161 | 4.07 |
| shared | 51 | 7,779 | 1,428 | 5.45 |
| tiny | 16 | 50 | 36 | 1.39 |
| **total** | 200 | **34,814** | 5,288 | **6.58** |

Winning strategy per puzzle: cheapest-first ordering (`m1`) won 184 of 200, of which 47 were with gcd seeding (`m1g`). Ascending order won 9 and random order 7.
Takeaways: "independent" and "mixed" (random large targets) dominate the remaining cost. Cheapest-first should get most of the time budget.

## 4. Playbook integration (user approved all four items)
- Read the Drive docs *Kaggle Competitions Template* and *Competitive AI ML Challenge Primer*. Mapped them to this competition in `docs/STRATEGY.md`.
- Solver v2 (still one file):
  - `--ablate L2,add,rw,gcd,exact,bandit` and `--modes 012` turn components off for ablations.
  - A strategy bandit over (ordering mode × gcd seeding). The credit is instructions saved by a randomized run, per try. Arms are chosen in proportion to `(gain+0.5)/(tries+5)` with 15% uniform exploration. Statistics can persist via `--stats FILE`.
- `solver/ablate.sh` runs 8 configs on the practice set with the same budget and seed (300 s each): base, no_bandit, no_L2, no_additive, no_rootwide, no_gcd, no_exact, only_cheapest.
- Created `docs/EXPERIMENTS.md` (the experiment table).

## 5. Solver v3: whole-table meet-in-the-middle leaf check (`deep`)
- Hypothesis: most of the cost in independent and mixed comes from closing out large leftovers. The v1 leaf check pairs about 3.5k cost≤1 values with the table. A two-pointer search for `m = x + y` / `m = x − y` over the whole radix-sorted table (about 1M × 1M pairs) extends the closable range by about 2.5 orders of magnitude for about 3–5 ms per call.
- Implemented behind `Params.deep`/`deepK` (root plus the top `deepK` beam states per depth). Ablate with `--ablate deep`. Off for the cheap-ordering estimates.
- The table's sorted copy moved from `std::sort` of pairs to a 4-pass 16-bit LSD radix sort (also used by the additive moves).
- Built as `solver_v3`. Evaluation is pending until the ablation suite (run on the v2 binary) finishes.

## 6. Ablation results (v2 binary, practice set, 300 s per config)
Totals are in `docs/EXPERIMENTS.md` rows E2–E9. Conclusions: gcd seeding is essential. At 6 s per puzzle, speed dominates and the expensive components (L2 table, additive moves) are net negative. The per-try bandit was the wrong metric and hurt slightly. Next: per-second bandit credit with L2 as an arm, and re-test at a representative budget (about 30 s per puzzle) with a repeat seed to measure noise.

## 7. Bandit v2 and a representative-budget experiment
- Bandit arms are now (ordering mode × gcd seeding × L2 table), 12 in total. Credit is instructions saved per **second** of run time, and the prior is `(saved+0.5)/(seconds+5)`, keeping 15% uniform exploration.
- Dev subset `sub48`: the first 12 practice puzzles of each non-tiny family (tiny is already near optimal). Budget 360 s on 4 threads, about 30 s per puzzle, close to the planned scored-run budget.
- Configs: v3 base (seed 2026), v3 `--ablate deep`, v3 `--ablate L2`, and v3 base with seed 7 (noise estimate).
