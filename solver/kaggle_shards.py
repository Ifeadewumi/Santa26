"""Scale out the solver over private Kaggle script kernels (4 CPUs each).

  push    --n N --hours H --init BEST.txt [--extra "solver args"] [--tag t]   -> one private kernel per shard
  status  --n N [--tag t]
  collect --n N --best BEST.txt [--tag t]                                    -> verify + per-puzzle merge into BEST.txt

Each kernel embeds solver.cpp, elf.py and the shard's warm-start programs (gzip+base64), compiles,
solves puzzles sorted(ids)[shard::N] and writes /kaggle/working/out.txt and solver.log.
"""
import argparse
import base64
import gzip
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import elf  # noqa: E402

USER = "ifeadewumi"
JOB = r'''
import base64, gzip, os, subprocess, glob, sys
SHARD, NSHARD, TOTAL, EXTRA = {shard}, {nshard}, {total}, {extra!r}
FILES = {files!r}
for name, data in FILES.items():
    open(name, 'wb').write(gzip.decompress(base64.b64decode(data)))
subprocess.run(['g++', '-O2', '-march=native', '-std=c++17', '-pthread', '-o', 'solver', 'solver.cpp'], check=True)
sys.path.insert(0, '.')
import elf
P = elf.load_puzzles(sorted(glob.glob('/kaggle/input/**/puzzles.csv', recursive=True))[0])
ids = sorted(P)[SHARD::NSHARD]
elf.write_puzzles_txt({{k: P[k] for k in ids}}, 'shard.txt')
cmd = ['./solver', '--puzzles', 'shard.txt', '--init', 'init.txt', '--out', '/kaggle/working/out.txt',
       '--total', str(TOTAL), '--threads', str(os.cpu_count()), '--seed', str(1000 + SHARD)] + EXTRA.split()
print(' '.join(cmd), flush=True)
with open('/kaggle/working/solver.log', 'w') as log:
    subprocess.run(cmd, stderr=log)
print(open('/kaggle/working/solver.log').read()[-600:])
'''


def parse_shards(spec, n):
    if not spec:
        return list(range(n))
    out = []
    for part in spec.split(","):
        lo, _, hi = part.partition("-")
        out += list(range(int(lo), int(hi or lo) + 1))
    return out


def kid(tag, i):
    return f"elf-{tag}-{i:02d}"


def push(a):
    P = elf.load_puzzles(a.puzzles)
    init = elf.read_progs_txt(a.init) if a.init else {}
    src = {n: open(os.path.join(HERE, n), "rb").read() for n in ("solver.cpp", "elf.py")}
    for i in (parse_shards(a.shards, a.n)):
        ids = sorted(P)[i::a.n]
        with tempfile.TemporaryDirectory() as d:
            ip = os.path.join(d, "init.txt")
            elf.write_progs_txt({k: init[k] for k in ids if k in init}, ip)
            files = {n: base64.b64encode(gzip.compress(b)).decode() for n, b in src.items()}
            files["init.txt"] = base64.b64encode(gzip.compress(open(ip, "rb").read())).decode()
            code = JOB.format(shard=i, nshard=a.n, total=int(a.hours * 3600), extra=a.extra, files=files)
            open(os.path.join(d, "job.py"), "w").write(code)
            meta = {"id": f"{USER}/{kid(a.tag, i)}", "title": kid(a.tag, i), "code_file": "job.py", "language": "python",
                    "kernel_type": "script", "is_private": True, "enable_gpu": False, "enable_internet": False,
                    "competition_sources": ["santa-2026"], "dataset_sources": [], "kernel_sources": []}
            json.dump(meta, open(os.path.join(d, "kernel-metadata.json"), "w"))
            r = subprocess.run(["kaggle", "kernels", "push", "-p", d], capture_output=True, text=True)
            print(i, (r.stdout + r.stderr).strip().splitlines()[-1])


def status(a):
    for i in parse_shards(a.shards, a.n):
        r = subprocess.run(["kaggle", "kernels", "status", f"{USER}/{kid(a.tag, i)}"], capture_output=True, text=True)
        print(i, (r.stdout + r.stderr).strip().splitlines()[-1])


def collect(a):
    P = elf.load_puzzles(a.puzzles)
    best = elf.read_progs_txt(a.best)
    before = sum(len(best[k]) for k in best)
    got = 0
    for i in parse_shards(a.shards, a.n):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["kaggle", "kernels", "output", f"{USER}/{kid(a.tag, i)}", "-p", d], capture_output=True)
            o = os.path.join(d, "out.txt")
            if not os.path.exists(o):
                print(i, "no output yet")
                continue
            progs = elf.read_progs_txt(o)
            ok = {k: v for k, v in progs.items() if k in P and elf.check_program(P[k], v)[0]}
            imp = sum(1 for k, v in ok.items() if k not in best or len(v) < len(best[k]))
            print(i, f"programs={len(progs)} valid={len(ok)} improved={imp}")
            got += imp
            best = elf.merge_best(P, best, ok)
    elf.write_progs_txt(best, a.best)
    after = sum(len(best[k]) for k in best)
    print(f"merged: {before} -> {after} ({got} puzzles improved, {len(best)} puzzles)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["push", "status", "collect"])
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--shards", default="", help="e.g. 5-9 (default: all)")
    ap.add_argument("--tag", default="v5")
    ap.add_argument("--hours", type=float, default=3.0)
    ap.add_argument("--init")
    ap.add_argument("--best")
    ap.add_argument("--extra", default="--fresh-polish 3")
    ap.add_argument("--puzzles", required=True)
    a = ap.parse_args()
    {"push": push, "status": status, "collect": collect}[a.cmd](a)
