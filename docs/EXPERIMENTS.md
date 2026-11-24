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

## Representative budget (sub48: 12 puzzles × 4 non-tiny families, lb 1,368; 360 s on 4 threads, about 30 s per puzzle)
| id | solver | config | total | ratio | Δ vs E10 | notes |
|---|---|---|---|---|---|---|
| E0' | v1 | 6 s per puzzle (from E1, same 48 puzzles) | 9,015 | 6.59 | +392 | 5× less time is only 4.5% worse |
| E10 | v3 | base, seed 2026 | 8,623 | 6.30 | ref | bandit: m1 arms collect nearly all savings |
| E11 | v3 | `--ablate deep` | 8,605 | 6.29 | −18 | deep MITM: no measurable gain |
| E12 | v3 | `--ablate L2` | 8,651 | 6.32 | +28 | |
| E13 | v3 | base, seed 7 | 8,598 | 6.28 | −25 | noise ≈ ±25 at this size |

Single-puzzle diagnostics (practice_0003, independent, start {2,16}):
- Trace: the first target costs 20 (tiny pool). With a full pool, 40-bit targets cost about 7 and 57–60-bit targets about 10–11.
- Beam sweep (beam 24/128/512 × w 0.12/0.18/0.25): 270–281 with no trend, so a wider search does not help.
- Exhaustive depth-6 enumeration from {2,16} (123,774 values): the first target is not `x±y` of two such values, so the bootstrap is inherently expensive for tiny start sets.

Leaderboard check (2026-11-24, `kaggle competitions leaderboard`): **top 125,289**, about 4.66 per target overall.
