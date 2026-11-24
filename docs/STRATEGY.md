# Strategy: applying the AI-native competition playbook to Santa 2026

Sources: the Drive docs *Kaggle Competitions Template* and *Competitive AI ML Challenge Primer*. Both target predictive ML. Santa 2026 is a **deterministic combinatorial optimisation** problem: the scored data is fixed, there is no hidden test set, there is no public/private split, and the score is exact and computable locally. This document maps each playbook principle to what it means here and where it lives in the repo.

## 1. Principle mapping

| Playbook principle | Meaning for Santa 2026 | Implementation |
|---|---|---|
| Deep EDA and domain immersion (template §I.1) | Read the rules exactly. Profile puzzle sizes and limits. Learn the hidden generator families from `practice_puzzles.csv`. | `docs/LOG.md` §1; `analyze.py` |
| Local validation and CV–LB alignment (primer §2, template §III) | The local score **is** the leaderboard score. The practice set (200 puzzles with `family` and `lower_bound`) is the development set for algorithm choices, so the scored set is never used to tune. | `analyze.py` per-family ratios against the lower bound |
| Anti-leakage guardrails | Not applicable. The equivalent risk is **invalidity**: one bad program rejects the whole file. | Two independent replays: the C++ `simulate()` and the Python `elf.check_program()` |
| Rigid compute budgeting (primer §2) | Per-puzzle time share is proportional to the target count and recomputed from the remaining wall clock. Checkpoints are written every 120 s. | `solver.cpp` `main()` |
| Submission integrity verification (primer §6) | Header, every id exactly once, compact JSON, re-read and re-verify after writing. | `elf.write_submission`; the last notebook cell |
| Ensembling / OOF blending (primer §6) | **Portfolio plus per-puzzle best-of merge.** Several search strategies and parameter draws run per puzzle and the shortest valid program wins. Merging with earlier submissions makes progress monotone. | `solvePuzzle()`; `elf.merge_best` |
| Component-wise ablation (primer §5, MLE-STAR) | Switch off one solver component at a time on the practice set with the same budget and seed, and keep only components that pay for themselves. | `solver --ablate ...`, `ablate.sh`, `docs/EXPERIMENTS.md` |
| Meta-learning across tasks (template's guiding philosophy) | A **bandit over strategy arms** (ordering mode × gcd seeding). Instructions saved per try steer later random runs towards the arms that win. Statistics persist across runs. | `pickArm`/`creditArm`, `--stats` |
| Avoid agent failure modes: crashes, idle recovery (primer §5) | Compiled, pre-verified pipeline. A guaranteed double-and-add fallback means every puzzle always has a valid program. | `fallbackSteps()` |
| Documentation and reflection (template §V) | Every action and number is recorded. | `docs/LOG.md`, `docs/EXPERIMENTS.md` |

Not applicable: OOF target encoding, adversarial validation, GBDT and NN stacks, threshold post-processing, leaderboard-overfitting management.

## 2. Problem-specific approach
1. **Greedy construction with sharing.** Targets are built one at a time. Every intermediate value stays in a pool of at most 48 values (LRU eviction, small values kept longest), so later targets reuse earlier ones.
2. **Cost tables from the current pool.** Cost 0 is the pool, cost 1 is `pool op pool`, and cost 2 is `(pool op pool) op pool` (about 1M values, open addressing plus a bit filter).
3. **Backward beam search per target.** Moves: `m = q*a`, `m = q*a ± r` and `m = x ± q`, where a, r and x come from the tables. Leaves are closed by the meet-in-the-middle check `m = x op y`.
4. **Structure exploitation.** Pairwise gcd seeding handles the multiplicative family. Additive moves and cheapest-first ordering handle shared and near-duplicate clusters.
5. **Exact IDDFS with canonical ordering** for small limits. A finished search is a proof of optimality.
6. **Post-processing.** Dead-code elimination over SSA, then linear-scan register allocation (exact for interval graphs).

## 3. Iteration loop
`hypothesis → implement behind a switch → practice-set ablation (same seed/budget) → EXPERIMENTS.md row → keep/revert → scored run with warm start → LOG.md`
