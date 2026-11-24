# Santa 2026 – The Elf Calculator

Score = total instructions over 1,000 puzzles (lower is better). Each instruction is `[op, i, j, d]`, meaning `reg[d] = reg[i] op reg[j]`. There are 48 registers, and every value must be a positive integer ≤ `value_limit`.

## Run on Kaggle
1. Upload `solver/santa2026_elf_solver.ipynb` as a notebook and attach the competition data.
2. Set `TOTAL_HOURS` and `SEED` in the first code cell, then run all cells. The notebook writes `/kaggle/working/submission.csv`, which every cell re-verifies.
3. To improve further, attach the previous run's output as an input and change `SEED`. Every `id,program` CSV under `/kaggle/input` is merged per puzzle, keeping the shorter program, so a re-run never gets worse.

## Solver (`solver/solver.cpp`)
- Builds targets greedily on a pool of at most R live values. The next target is chosen cheapest-first, ascending or in random order.
- Builds cost tables from the current pool: cost 0 is a pool value, cost 1 is `pool op pool`, cost 2 is `(pool op pool) op pool` (about 1M values).
- Plans each target with a backward beam search over `m = q*a ± r`, `m = q*a` and `m = x ± q`. Leaves are closed by a meet-in-the-middle check of `m = x op y`.
- Gcd seeding handles multiplicative structure. Exact IDDFS with canonical ordering covers small-limit puzzles, and a finished run proves optimality.
- Removes dead code, then assigns registers by linear scan. Every program is replayed by a strict simulator. A double-and-add fallback makes sure every puzzle gets a valid program.

Local CLI: `g++ -O2 -march=native -std=c++17 -pthread -o solver solver/solver.cpp`, then use `elf.py` to convert between CSV and text (see the notebook).
