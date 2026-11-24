"""Verify every id,program CSV (and solver .txt program file) under the given paths and merge per puzzle.

usage: python3 merge_public.py PUZZLES.csv BEST.txt PATH [PATH ...]
Every candidate program is replayed with elf.check_program; BEST.txt is updated in place with the per-puzzle
shortest valid program. Prints the sources that contributed.
"""
import glob
import os
import sys

import elf

P = elf.load_puzzles(sys.argv[1])
best_path = sys.argv[2]
best = elf.read_progs_txt(best_path)
before = sum(len(v) for v in best.values())
files = []
for root in sys.argv[3:]:
    if os.path.isfile(root):
        files.append(root)
    else:
        files += glob.glob(os.path.join(root, "**", "*.csv"), recursive=True)
        files += glob.glob(os.path.join(root, "**", "*.txt"), recursive=True)
contrib = {}
for f in sorted(set(files)):
    try:
        progs = elf.load_submission(f) if f.endswith(".csv") else elf.read_progs_txt(f)
    except Exception:
        continue
    for k, v in progs.items():
        k0 = k.split("#")[0]
        if k0 not in P or (k0 in best and len(v) >= len(best[k0])):
            continue
        if elf.check_program(P[k0], v)[0]:
            gain = len(best[k0]) - len(v) if k0 in best else 0
            best[k0] = v
            contrib[f] = contrib.get(f, 0) + gain
elf.write_progs_txt(best, best_path)
after = sum(len(v) for v in best.values())
for f, g in sorted(contrib.items(), key=lambda x: -x[1]):
    print(f"  -{g:4d}  {f}")
print(f"{before} -> {after} ({len(best)} puzzles)")
