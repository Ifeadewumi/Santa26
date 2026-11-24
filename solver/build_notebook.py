"""Build santa2026_elf_solver.ipynb embedding solver.cpp and elf.py (run: python3 build_notebook.py)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
read = lambda f: open(os.path.join(HERE, f)).read()


def code(src):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": src}


def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src}


cells = [
    md("# Santa 2026 – The Elf Calculator: portfolio solver\n"
       "C++ greedy + backward beam search over `m = q*a ± r` / `m = x ± q` decompositions, "
       "meet-in-the-middle leaf closing, gcd seeding, exact IDDFS for small limits, "
       "SSA dead-code elimination + register allocation, and a strict replay of every program.\n\n"
       "**Inputs:** the competition data, plus (optional) any earlier `submission.csv` attached as a dataset/notebook output. "
       "Every `id,program` CSV under `/kaggle/input` (sample submission included) is used as a warm start; per puzzle the shortest valid program wins, "
       "so re-running with the previous output attached can only improve the score."),
    code("TOTAL_HOURS = 8.0      # wall-clock solver budget (Kaggle session limit is 12h)\n"
         "SEED = 2026            # change between runs to diversify the random portfolio\n"
         "import os\n"
         "THREADS = os.cpu_count()\n"
         "INPUT = '/kaggle/input'\n"
         "print(THREADS, 'threads')"),
    code("%%writefile solver.cpp\n" + read("solver.cpp")),
    code("%%writefile elf.py\n" + read("elf.py")),
    code("!g++ -O2 -march=native -std=c++17 -pthread -o solver solver.cpp && echo compiled"),
    code("import glob, subprocess, sys, time\n"
         "import elf\n"
         "puz_path = sorted(glob.glob(f'{INPUT}/**/puzzles.csv', recursive=True))[0]\n"
         "P = elf.load_puzzles(puz_path)\n"
         "print(puz_path, len(P), 'puzzles; lower bound (#targets not in start) =', sum(elf.lower_bound(p) for p in P.values()))\n"
         "elf.write_puzzles_txt(P, 'puzzles.txt')\n"
         "subs = elf.collect_submissions(INPUT)\n"
         "for path, s in subs:\n"
         "    print('warm start candidate:', path, len(s), 'rows')\n"
         "init = elf.merge_best(P, *[s for _, s in subs])\n"
         "print('valid warm-start programs:', len(init), ' score of those:', sum(map(len, init.values())))\n"
         "elf.write_progs_txt(init, 'init.txt')"),
    code("cmd = ['./solver', '--puzzles', 'puzzles.txt', '--init', 'init.txt', '--out', 'out.txt',\n"
         "       '--total', str(int(TOTAL_HOURS * 3600)), '--threads', str(THREADS), '--seed', str(SEED)]\n"
         "t0 = time.time()\n"
         "proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)\n"
         "for i, line in enumerate(proc.stderr):\n"
         "    if i < 3 or i % 25 == 0 or line.startswith('DONE'):\n"
         "        print(f'{time.time()-t0:7.0f}s', line, end='', flush=True)\n"
         "print('exit code', proc.wait())"),
    code("out = elf.read_progs_txt('out.txt')\n"
         "best = elf.merge_best(P, init, out)\n"
         "bad = [pid for pid, prog in out.items() if pid in P and not elf.check_program(P[pid], prog)[0]]\n"
         "print('solver programs rejected by the Python verifier:', len(bad), bad[:5])\n"
         "score = elf.write_submission(P, best, 'submission.csv')\n"
         "lb = sum(elf.lower_bound(p) for p in P.values())\n"
         "print(f'submission.csv written: score={score}  (warm start {sum(map(len, init.values()))}, lower bound {lb})')\n"
         "# re-check the written file end to end\n"
         "chk = elf.load_submission('submission.csv')\n"
         "assert set(chk) == set(P) and all(elf.check_program(P[k], v)[0] for k, v in chk.items())\n"
         "print('verified', len(chk), 'programs')"),
    code("import collections\n"
         "rows = sorted(((len(best[k]), elf.lower_bound(P[k]), len(P[k]['targets']), P[k]['limit'], k) for k in P), reverse=True)\n"
         "print('largest programs: len, lb, #targets, limit, id')\n"
         "for r in rows[:15]: print(r)\n"
         "ratio = collections.Counter(min(9, round(l / max(1, b))) for l, b, *_ in rows)\n"
         "print('len/lower_bound histogram:', sorted(ratio.items()))"),
]

nb = {
    "cells": cells,
    "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                 "language_info": {"name": "python"}},
    "nbformat": 4, "nbformat_minor": 5,
}
for c in nb["cells"]:
    c["source"] = c["source"].splitlines(keepends=True)
with open(os.path.join(HERE, "santa2026_elf_solver.ipynb"), "w") as f:
    json.dump(nb, f, indent=1)
print("wrote santa2026_elf_solver.ipynb")
