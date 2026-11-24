"""Per-family / per-strategy breakdown of a solver run.
usage: python3 analyze.py puzzles.csv out.txt [solver.log]
"""
import collections
import csv
import re
import sys

import elf

P = elf.load_puzzles(sys.argv[1])
fam = {}
with open(sys.argv[1], newline="") as f:
    for r in csv.DictReader(f):
        fam[r["id"]] = r.get("family", "?")
out = elf.read_progs_txt(sys.argv[2])
agg = collections.defaultdict(lambda: [0, 0, 0, 0])  # n, len, lb, invalid
for pid, p in P.items():
    a = agg[fam[pid]]
    a[0] += 1
    a[2] += elf.lower_bound(p)
    prog = out.get(pid)
    if prog is None or not elf.check_program(p, prog)[0]:
        a[3] += 1
        continue
    a[1] += len(prog)
tot = [sum(v[i] for v in agg.values()) for i in range(4)]
print(f"{'family':15s} {'n':>4s} {'len':>8s} {'lb':>7s} {'ratio':>6s} {'invalid':>7s}")
for k, (n, L, lb, bad) in sorted(agg.items()) + [("TOTAL", tot)]:
    print(f"{k:15s} {n:4d} {L:8d} {lb:7d} {L / max(lb, 1):6.2f} {bad:7d}")
if len(sys.argv) > 3:
    wins = collections.Counter()
    for line in open(sys.argv[3]):
        m = re.search(r"\| (\S+) (m\d\S*)?", line)
        if m:
            kind = m.group(1) if m.group(1) in ("exact", "init") else m.group(1) + " " + (m.group(2) or "")
            wins[kind] += 1
    print("winning strategy:", wins.most_common(12))
