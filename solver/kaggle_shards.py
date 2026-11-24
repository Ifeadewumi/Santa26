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


JOB_ELF = r'''
import base64, gzip, os, subprocess, glob, sys, time
SHARD, NSHARD, TOTAL, EXTRA = {shard}, {nshard}, {total}, {extra!r}
FILES = {files!r}
for name, data in FILES.items():
    open(name, 'wb').write(gzip.decompress(base64.b64decode(data)))
subprocess.run(['g++', '-O3', '-march=native', '-std=c++17', '-o', 'elfopt', 'elfopt.cpp'], check=True)
sys.path.insert(0, '.')
import elf
P = elf.load_puzzles(sorted(glob.glob('/kaggle/input/**/puzzles.csv', recursive=True))[0])
starts = [l.split() for l in open('starts.txt')]  # id<TAB-free> per block, programs in init/var files
init = elf.read_progs_txt('init.txt'); var = elf.read_progs_txt('variants.txt') if os.path.exists('variants.txt') else {{}}
ids = sorted(P)[SHARD::NSHARD]
blocks = [(k, init[k]) for k in ids if k in init] + [(k.split('#')[0], v) for k, v in var.items() if k.split('#')[0] in ids]
def enc(k, prog):
    p = P[k]
    h = ['P', k, str(len(p['start']))] + list(map(str, p['start'])) + [str(len(p['targets']))] + list(map(str, p['targets'])) + [str(p['limit']), str(p['R']), str(len(prog))]
    return ' '.join(h) + '\n' + ''.join(f'{{o}} {{i}} {{j}} {{d}}\n' for o, i, j, d in prog)
blocks.sort(key=lambda kb: -len(kb[1]))
nc = os.cpu_count()
per = max(5.0, TOTAL * nc / max(1, len(blocks)) * 0.95)
procs = []
for c in range(nc):
    open(f'in_{{c}}.txt', 'w').write(''.join(enc(k, pr) for k, pr in blocks[c::nc]))
    cmd = f'./elfopt --time {{per:.1f}} --seed {{1000 * SHARD + c + 7}} {{EXTRA}} < in_{{c}}.txt > out_{{c}}.txt 2> log_{{c}}.txt'
    procs.append(subprocess.Popen(cmd, shell=True))
for pr in procs: pr.wait()
best = {{}}
for c in range(nc):
    lines = open(f'out_{{c}}.txt').read().split('\n'); i = 0
    while i < len(lines):
        t = lines[i].split()
        if t and t[0] == 'R':
            n = int(t[3]); prog = [[x.split()[0], int(x.split()[1]), int(x.split()[2]), int(x.split()[3])] for x in lines[i + 1:i + 1 + n]]
            if elf.check_program(P[t[1]], prog)[0] and (t[1] not in best or len(prog) < len(best[t[1]])): best[t[1]] = prog
            i += n + 1
        else: i += 1
elf.write_progs_txt(best, '/kaggle/working/out.txt')
os.system('cat log_*.txt > /kaggle/working/solver.log')
print('improved', len(best), 'per-block seconds', per)
'''


def kid(tag, i):
    return f"elf-{tag}-{i:02d}"


def push(a):
    P = elf.load_puzzles(a.puzzles)
    init = elf.read_progs_txt(a.init) if a.init else {}
    if a.engine == "elfopt":
        src = {"elfopt.cpp": open(a.engine_src, "rb").read(), "elf.py": open(os.path.join(HERE, "elf.py"), "rb").read()}
    else:
        src = {n: open(os.path.join(HERE, n), "rb").read() for n in ("solver.cpp", "elf.py")}
    var = elf.read_progs_txt(a.variants) if a.variants else {}
    for i in (parse_shards(a.shards, a.n)):
        ids = sorted(P)[i::a.n]
        with tempfile.TemporaryDirectory() as d:
            ip = os.path.join(d, "init.txt")
            elf.write_progs_txt({k: init[k] for k in ids if k in init}, ip)
            files = {n: base64.b64encode(gzip.compress(b)).decode() for n, b in src.items()}
            files["init.txt"] = base64.b64encode(gzip.compress(open(ip, "rb").read())).decode()
            if var:
                vp = os.path.join(d, "variants.txt")
                elf.write_progs_txt({k: v for k, v in var.items() if k.split("#")[0] in ids}, vp)
                files["variants.txt"] = base64.b64encode(gzip.compress(open(vp, "rb").read())).decode()
            files["starts.txt"] = base64.b64encode(gzip.compress(b"")).decode()
            code = (JOB_ELF if a.engine == "elfopt" else JOB).format(shard=i, nshard=a.n, total=int(a.hours * 3600), extra=a.extra, files=files)
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
    ap.add_argument("--engine", default="solver", choices=["solver", "elfopt"])
    ap.add_argument("--engine-src", default="", help="path to elfopt.cpp (public DAG-LNS engine, Apache-2.0)")
    ap.add_argument("--variants", default="", help="extra LNS start programs, ids like scored_0001#2")
    a = ap.parse_args()
    {"push": push, "status": status, "collect": collect}[a.cmd](a)
