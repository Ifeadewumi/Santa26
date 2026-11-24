# Experiment table

Unless noted, the development set is `practice_puzzles.csv` (200 puzzles, lower bound 5,288), run on 4 threads with `--seed 2026` and a 300 s total budget (about 6 s per puzzle). Runs are time-bounded, so repeated runs of the same config differ by a little noise. Scored-set runs are listed separately.

## Practice set
| id | solver | config | total | ratio vs lb | Δ vs reference | notes |
|---|---|---|---|---|---|---|
| E1 | v1 | default portfolio (uniform random arms) | 34,814 | 6.58 | — | cheapest-first wins 184/200 |
| E2 | v2 | base (bandit on, credit per try) | 34,888 | 6.60 | ref | bandit concentrated on m1 |
| E3 | v2 | `--ablate bandit` | 34,590 | 6.54 | −298 | |
| E4 | v2 | `--ablate L2` | 34,237 | 6.47 | −651 | about 10× more runs completed |
| E5 | v2 | `--ablate add` | 34,282 | 6.48 | −606 | |
| E6 | v2 | `--ablate rw` | 34,641 | 6.55 | −247 | |
| E7 | v2 | `--ablate gcd` | 35,452 | 6.70 | **+564** | gcd seeding is essential (independent +545) |
| E8 | v2 | `--ablate exact` | 34,582 | 6.54 | −306 | tiny unchanged at 50, so the difference is time noise |
| E9 | v2 | `--modes 1` (cheapest-first only) | 34,305 | 6.49 | −583 | |

**Reading of E2–E9 (6 s per puzzle):** at this short budget, run count matters more than per-run quality, so dropping the expensive table level (L2) or the additive moves helps. Gcd is the only component whose removal clearly hurts. Run-to-run noise is about ±100–300 (E1 vs E2 differ by 74, and E8 changed nothing that can affect tiny yet moved by 306). Two design conclusions:
1. The bandit's credit must be **per second**, not per try, because runs differ about 10× in cost. L2 on/off should be an arm.
2. Ablations must use a per-puzzle budget close to the scored run's (about 30–45 s), otherwise they select for speed only.
