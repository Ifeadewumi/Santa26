"""Run triwalk (goodpjw2008, public) over alternative-lineage start programs only.
usage: python3 run_triwalk_lineages.py PUZZLES.csv BEST.txt LINEAGES.txt TRIWALK_BIN OUT.txt SECS [procs] [extra args]
LINEAGES.txt keys may be `id#n`. Every returned program is verified; improvements over BEST are written to OUT.txt."""
import os, subprocess, sys, tempfile, random
import elf
pz, bp, lp, exe, out, secs = sys.argv[1:7]
procs = int(sys.argv[7]) if len(sys.argv) > 7 else 4
extra = sys.argv[8] if len(sys.argv) > 8 else "--cap 2 --T 0.2 --rb 0.85 --deep 0.4"
P = elf.load_puzzles(pz); B = elf.read_progs_txt(bp); L = elf.read_progs_txt(lp)
blocks = [(k.split("#")[0], v) for k, v in L.items()]
random.Random(1).shuffle(blocks)
def enc(k, prog):
    p = P[k]
    h = ["P", k, str(len(p["start"]))] + list(map(str, p["start"])) + [str(len(p["targets"]))] + list(map(str, p["targets"]))
    h += [str(p["limit"]), str(p["R"]), str(len(prog))]
    return " ".join(h) + "\n" + "".join(f"{o} {i} {j} {d}\n" for o, i, j, d in prog)
d = tempfile.mkdtemp(prefix="tw_", dir=os.path.dirname(os.path.abspath(out)))
ps = []
for c in range(procs):
    open(f"{d}/in_{c}.txt", "w").write("".join(enc(k, v) for k, v in blocks[c::procs]))
    ps.append(subprocess.Popen(f"{exe} --time {secs} --seed {777+c} {extra} < {d}/in_{c}.txt > {d}/out_{c}.txt 2> {d}/log_{c}.txt", shell=True))
print(f"blocks={len(blocks)} dir={d}", flush=True)
for p in ps: p.wait()
best = {}; lin_gain = 0
for c in range(procs):
    lines = open(f"{d}/out_{c}.txt").read().split("\n"); i = 0
    while i < len(lines):
        t = lines[i].split()
        if t and t[0] in "RV" and len(t) == 4:
            n = int(t[3]); prog = [[x.split()[0], *map(int, x.split()[1:])] for x in lines[i+1:i+1+n]]; k = t[1]
            if t[0] == "R" and elf.check_program(P[k], prog)[0] and len(prog) < len(B[k]) and (k not in best or len(prog) < len(best[k])): best[k] = prog
            i += n + 1
        else: i += 1
g = sum(len(B[k]) - len(v) for k, v in best.items())
elf.write_progs_txt(best, out)
print(f"improved puzzles {len(best)} saved {g}", flush=True)
