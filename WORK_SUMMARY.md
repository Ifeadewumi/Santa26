# Santa 2026 (The Elf Calculator): summary of work

**Repo:** `ifeadewumi/santa26`. Branch `claude/quirky-hopper-papxg6` has 22 commits, all made on 2026-11-24. The branch `ccr-2d54f42b-chf3kl` is an older snapshot that stops at commit `9394a93`.
**Sources:** `docs/LOG.md` (the full run log), `docs/EXPERIMENTS.md`, `docs/STRATEGY.md`, `docs/CREDITS.md`.

## Outcome
| Milestone | Public LB score | Approx. rank |
|---|---|---|
| `sample_submission.csv` (naive double-and-add) | 1,490,379 (local) | — |
| Run 1, own solver v3 | **166,079** | ~2,110 / 2,894 |
| Own lineage after wave 1 (Kaggle shards + local run 2) | **149,008** | — |
| Public frontier ∪ own lineage | **128,311** | ~190 |
| Fresh public re-pull and merge (current best) | **128,295** | ~190 |

Leaderboard reference points: rank 1 = 125,289, rank 50 = 127,999 (the stated goal is top 50), rank 100 = 128,275. Wave 2 (Kaggle `elf-v9-00..04` plus local run 3) was launched, but its results have not been logged yet.

## Problem
- 1,000 puzzles, each with R=48 registers. Each instruction is `reg[d] = reg[i] op reg[j]`, every value must be a positive integer ≤ `value_limit`, and the score is the total instruction count.
- 26,902 targets in total. The trivial lower bound is 26,898.
- `practice_puzzles.csv` (200 puzzles with `family` and `lower_bound`) served as the development set. Its families are shared, mixed, independent, multiplicative and tiny.

## What was built (`solver/`)
| File | Purpose |
|---|---|
| `solver.cpp` (~1.5k lines) | Portfolio solver; versions v1 to v9, described below |
| `elf.py` | Independent Python verifier, I/O, per-puzzle best merge, submission writer |
| `santa2026_elf_solver.ipynb` + `build_notebook.py` | Self-contained Kaggle notebook. It merges every CSV in `/kaggle/input`, so re-runs never get worse |
| `analyze.py` | Per-family ratio against the lower bound, plus winning-strategy tags |
| `ablate.sh` | Runs 8 component ablations on the practice set |
| `kaggle_shards.py` | `push`/`status`/`collect` for sharded private Kaggle kernels (4 CPUs each, at most 5 at once). Has an `--engine elfopt` mode |
| `recombine.py` | CP-SAT exact recombination of pooled values from several programs |
| `merge_public.py` | Verifies and merges every public CSV/txt into a best file |
| `submit_best.sh` | Verifies end to end, writes the CSV and submits to Kaggle |

### Solver evolution
- **v1:** greedy construction over a shared pool. Cost tables (pool, then pool op pool, then about 1M two-step values). Backward beam search (`q*a±r`, `x±q`) with a meet-in-the-middle leaf check. Gcd seeding, exact IDDFS for tiny limits, dead-code elimination, linear-scan register allocation, strict replay and a double-and-add fallback. Practice set: 34,814 (6.58× the lower bound).
- **v2:** ablation switches and a strategy bandit over ordering × gcd seeding.
- **v3:** whole-table two-pointer meet-in-the-middle (`deep`) and a radix-sorted table. Bandit v2 gives credit per second, with L2 as an arm.
- **v4:** value-graph polisher (`--polish`), which removes a value's private cone and rebuilds it with ≤3 instructions. `poolCap` lets the build pool exceed 48 values. `--fresh-polish` adds a construct-then-polish pipeline. **−7.8% vs v3, better on 8/8 puzzles.**
- **v5:** two-root polish moves (30% of moves).
- **v6/v7:** hub seeding (kept at 20% of random runs). A seed sieve finds mid-size multiplicative seeds (scored_0923: 219→188) and seeds cofactor partners.
- **v8:** a portfolio switch between raw and normalised seed lists.
- **v9:** backward-beam rebuild inside the polisher, better on 3 of 3 test puzzles.

## Key findings
- **Ablations** (E2–E13, see `EXPERIMENTS.md`):
  - Gcd seeding is essential (+564 when removed).
  - At about 30 s per puzzle, deep meet-in-the-middle, the L2 table and a wider beam all fall within noise (about ±25 on sub48).
  - 5× more time gives only 4.5%, so the move set is the limit, not search effort.
- **Gap analysis against the frontier:** the own lineage is about 1.31× longer overall. The worst class is 50-bit "shared" puzzles at 1.50×. Good programs build a small dictionary plus mid-size seeds and express targets as `seed_i*seed_j ± small`.
- **The public frontier is a hard local optimum:**
  - CP-SAT recombination found 0 gains on 10 puzzles.
  - The v9 polisher found 0 gains on 8 puzzles (about 5M moves).
  - The public `elfopt` DAG-LNS engine found 0 gains, and its fresh construction came out 16–21% above the frontier.
- **Main lesson from the public write-ups:** value-graph local search plus regular merges of public programs give most of the gains. Fresh constructors provide new lineages.

## Process and infrastructure
- Personal cloud environment `santa26` with the Kaggle hosts allowed. Credentials live only in the container.
- The two Drive playbook docs were mapped to this deterministic optimisation problem in `STRATEGY.md`.
- Every program is checked by two independent replays (C++ `simulate()` and Python `elf.check_program`) before merging or submitting.
- Public sources (9 notebook authors, 13 datasets) are credited in `CREDITS.md`.
- Running the third-party engine was first blocked by the permission classifier. It ran after the user approved and a safety scan of its sources.
- User policy: submit whenever the merged score beats the previous best (limit 100 per day).

## Open items / next steps
1. Collect wave 2 (Kaggle `elf-v9-00..04` plus local run 3), merge, and submit if the score improves.
2. Run a frontier LNS wave with `elfopt` (5 shards × 3 h) and measure yield per hour to project the cost of reaching top 50 (≤127,999, which is about 300 below the current best).
3. Keep re-pulling and merging public datasets.
4. Improve the own constructor on 50-bit "shared" puzzles (cheaper seed and dictionary building) so the own lineage can serve as an LNS donor within +1 to +3 of the frontier.
