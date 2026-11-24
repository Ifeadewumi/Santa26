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

## 8. Representative-budget results, diagnostics and leaderboard
- See `docs/EXPERIMENTS.md` E10–E13: all configs fall within ±25 noise. Deep MITM and L2 bring no gain, and 5× more time gives only 4.5%.
- Added `--debug` (per-target trace) and `--beam/--w/--termk/--deepk` overrides. A wider beam does not help, so the move set is the limit, not the search.
- Leaderboard top is 125,289. The practice ratio (6.3) projects to about 170k on the scored set.
- Started **scored run 1**: v3, 3,600 s, 4 threads, warm start from `sample_submission`, bandit statistics saved to `bandit.stats`.

## 9. Closing the gap: research (user request), public frontier, value-graph polisher (v4)
- **Public notebooks** (`kaggle kernels list --competition santa-2026 --sort-by voteCount`): read the method write-ups of 8 top notebooks. The most informative is "Santa 2026: Claude Coding | LB 128,524" (177 logged experiments). Its main points:
  1. Local search on the value graph gives most of the gain: remove a value's private instructions, rebuild exactly with ≤3 new instructions, walk plateaus, prefer small new values.
  2. Daily merges of public programs.
  3. A backward beam for private chains.
  4. Fresh constructors as new lineages ("every method decays; new sources move the score").
  5. Random targets sit near an information floor of 5/6/7 instructions for 40/50/60-bit targets.
  It also lists many failed ideas: toolkits, lattices, wider beams, removing the register limit.
- Added `www.kaggleusercontent.com` to the `santa26` environment so notebook outputs can be downloaded (`kaggle kernels output`).
- **Public frontier:** per-puzzle best of 11 public output files (all re-verified by `elf.check_program`) = **128,324**. That equals the best single file, so the public lineage has converged.
- **Solver v4:** added `polishProgram` and `--polish`. The move removes value v's private cone S and rebuilds value(v) exactly with ≤min(|S|,3) new instructions from all non-descendant values (1-step and 2-step tables plus two meet-in-the-middle forms). Then a stable Kahn re-schedule, DCE, linear-scan allocation and strict replay. Equal-length results are accepted. The one-step table uses an open-addressing map.
- Polisher trials, 30 s on 1 thread:
  - Frontier programs scored_0001 (219), scored_0104 (221) and scored_0500 (75): no change, as expected for converged programs.
  - Positive control on our run-1 programs: scored_0606 199→187 and scored_0542 128→117. The polisher works, but our raw lineage is about 20–25% above the frontier on these (151, 99).

## 10. Solver v4 constructor changes
- `poolCap`: the builder's value pool may exceed the 48 registers, and final register allocation decides whether the program fits (failed runs are discarded). Single-run probe on practice_0003/0010/0020:

  | cap | lengths |
  |---|---|
  | 48 | 275/144/105 |
  | 64 | 258/138/103 |
  | 72 | 254/137/103 |
  | 88 | 245/136/102 |
  | 120 | 248/132/102 |
  | ≥160 | the largest program fails allocation |

  Defaults: fixed runs use 88, plus one fixed run at 48 that always fits. Random runs draw from {64,72,88,88,104,120}. `--poolcap` forces a value.
- `--fresh-polish SEC`: every constructed program within 15% of the current best gets SEC seconds of value-graph polish before comparison (construct + polish, the "new lineage" method).
- A/B started on 8 practice puzzles (2 per non-tiny family, 20 s each, 1 thread): v3 against v4 with `--fresh-polish 2`.

## 11. Scale-out on Kaggle compute (user: "why assume you can't close the gap?")
- Re-framed: the limits are compute and algorithm quality, and both can be moved. Compute: private Kaggle script kernels have 4 CPUs, g++ 13 and the competition data attached (verified with the test kernel `elf-shard-test`).
- `solver/kaggle_shards.py` has three commands:
  - `push` creates one private kernel per shard, embedding solver.cpp, elf.py and the shard's warm-start programs (gzip+base64).
  - `status` shows each kernel's state.
  - `collect` downloads outputs, verifies every program with `elf.check_program` and does a per-puzzle best merge.
- Own-lineage warm start `ours.txt` = sample ∪ run-1 checkpoint (878,214 at push time, because run 1 is only partly done).
- Pushed `elf-v5-00..04` (v5 solver, `--fresh-polish 3`, 3 h each, shards i::10). **Kaggle limits batch CPU sessions to 5 at a time**, so shards 5–9 are queued for the next wave (`--shards 5-9`).
