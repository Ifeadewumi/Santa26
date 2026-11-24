#!/usr/bin/env bash
# Component ablations on the practice set: same budget and seed per config.
# usage: ablate.sh SOLVER PRACTICE_TXT OUTDIR [SECONDS]
set -u
SOLVER=$1; PRAC=$2; OUT=$3; SEC=${4:-300}
mkdir -p "$OUT"
run() { name=$1; shift; "$SOLVER" --puzzles "$PRAC" --out "$OUT/$name.txt" --total "$SEC" --threads 4 --seed 2026 "$@" 2> "$OUT/$name.log"; echo "$name $(grep DONE "$OUT/$name.log")"; }
run base
run no_bandit --ablate bandit
run no_L2 --ablate L2
run no_additive --ablate add
run no_rootwide --ablate rw
run no_gcd --ablate gcd
run no_exact --ablate exact
run only_cheapest --modes 1
