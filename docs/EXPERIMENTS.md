# Experiment table

Unless noted, the development set is `practice_puzzles.csv` (200 puzzles, lower bound 5,288), run on 4 threads with `--seed 2026` and a 300 s total budget (about 6 s per puzzle). Runs are time-bounded, so repeated runs of the same config differ by a little noise. Scored-set runs are listed separately.

## Practice set
| id | solver | config | total | ratio vs lb | Δ vs reference | notes |
|---|---|---|---|---|---|---|
| E1 | v1 | default portfolio (uniform random arms) | 34,814 | 6.58 | — | cheapest-first wins 184/200 |
