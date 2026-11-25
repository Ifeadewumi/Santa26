"""Run the public DAG-LNS engine (elfopt, Apache-2.0, goodpjw2008) locally over best programs + variants.

usage: python3 run_elfopt_local.py PUZZLES.csv BEST.txt VARIANTS.txt ELFOPT_BIN OUT.txt --top N --hours H [--procs 4]
Picks the N puzzles with the longest best programs, feeds best + variant programs as LNS start blocks to
`procs` engine processes (per-block time fills the budget), verifies every result and writes improvements.
"""
import argparse
import os
import subprocess
import tempfile

import elf

ap = argparse.ArgumentParser()
for x in ("puzzles", "best", "variants", "bin", "out"):
    ap.add_argument(x)
ap.add_argument("--top", type=int, default=200)
ap.add_argument("--hours", type=float, default=2)
ap.add_argument("--procs", type=int, default=4)
ap.add_argument("--seed", type=int, default=11)
ap.add_argument("--extra", default="--kicks 1000 --kslack 2")
a = ap.parse_args()
P = elf.load_puzzles(a.puzzles)
B = elf.read_progs_txt(a.best)
V = elf.read_progs_txt(a.variants) if os.path.exists(a.variants) else {}
ids = sorted(B, key=lambda k: -len(B[k]))[: a.top]
idset = set(ids)
blocks = [(k, B[k]) for k in ids] + [(k.split("#")[0], v) for k, v in V.items() if k.split("#")[0] in idset]
blocks.sort(key=lambda kb: -len(kb[1]))


def enc(k, prog):
    p = P[k]
    h = ["P", k, str(len(p["start"]))] + list(map(str, p["start"])) + [str(len(p["targets"]))] + list(map(str, p["targets"]))
    h += [str(p["limit"]), str(p["R"]), str(len(prog))]
    return " ".join(h) + "\n" + "".join(f"{o} {i} {j} {d}\n" for o, i, j, d in prog)


per = max(5.0, a.hours * 3600 * a.procs / len(blocks) * 0.95)
d = tempfile.mkdtemp(prefix="elfopt_", dir=os.path.dirname(os.path.abspath(a.out)))
procs = []
for c in range(a.procs):
    open(f"{d}/in_{c}.txt", "w").write("".join(enc(k, pr) for k, pr in blocks[c :: a.procs]))
    cmd = f"{a.bin} --time {per:.1f} --seed {a.seed * 100 + c} {a.extra} < {d}/in_{c}.txt > {d}/out_{c}.txt 2> {d}/log_{c}.txt"
    procs.append(subprocess.Popen(cmd, shell=True))
print(f"blocks={len(blocks)} per-block={per:.0f}s dir={d}", flush=True)
for pr in procs:
    pr.wait()
best = {}
for c in range(a.procs):
    lines = open(f"{d}/out_{c}.txt").read().split("\n")
    i = 0
    while i < len(lines):
        t = lines[i].split()
        if t and t[0] == "R":
            n = int(t[3])
            prog = [[x.split()[0], int(x.split()[1]), int(x.split()[2]), int(x.split()[3])] for x in lines[i + 1 : i + 1 + n]]
            k = t[1]
            if elf.check_program(P[k], prog)[0] and len(prog) < len(B[k]) and (k not in best or len(prog) < len(best[k])):
                best[k] = prog
            i += n + 1
        else:
            i += 1
elf.write_progs_txt(best, a.out)
print("improved puzzles", len(best), "saved", sum(len(B[k]) - len(v) for k, v in best.items()))
