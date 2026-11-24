"""Exact recombination of several programs for the same puzzle (CP-SAT).

Pool every value computed by any input program, enumerate every recipe a op b = c inside the pool, and let
CP-SAT choose the smallest acyclic set of values that contains every target (each chosen non-start value needs
one chosen recipe whose operands are chosen and ordered before it). The result is scheduled (list scheduling that
greedily frees registers), register-allocated (<= R live) and verified by elf.check_program.

usage: python3 recombine.py PUZZLES.csv OUT.txt SOURCES.txt... [--ids a,b] [--time 20] [--workers 4] [--shard i/n]
"""
import argparse
import sys
import time

from ortools.sat.python import cp_model

import elf


def values_of(p, prog):
    reg = list(p["start"]) + [None] * (p["R"] - len(p["start"]))
    out = []
    for op, i, j, d in prog:
        a, b = reg[i], reg[j]
        r = a + b if op == "+" else a - b if op == "-" else a * b if op == "*" else a // b
        reg[d] = r
        out.append(r)
    return out


def apply(op, a, b, lim):
    if op == "+":
        r = a + b
    elif op == "-":
        r = a - b if a > b else 0
    elif op == "*":
        r = a * b
    else:
        r = a // b if b > 1 and a % b == 0 else 0
    return r if 1 <= r <= lim else 0


def schedule(p, chosen, rec):
    """chosen: set of non-start values; rec[v] = (op, a, b). Returns a program or None (register limit)."""
    R, start = p["R"], p["start"]
    startset = set(start)
    deps = {v: {rec[v][1], rec[v][2]} - startset for v in chosen}
    users = {v: 0 for v in list(chosen) + list(start)}
    for v in chosen:
        _, a, b = rec[v]
        users[a] = users.get(a, 0) + 1
        if b != a:
            users[b] = users.get(b, 0) + 1
    remaining_uses = dict(users)
    reg_of = {}
    free = []
    for k, v in enumerate(start):
        if v in reg_of:
            free.append(k)  # duplicate start value
            continue
        reg_of[v] = k
        if remaining_uses.get(v, 0) == 0:
            free.append(k)
    free += list(range(len(start), R))
    done, prog = set(), []
    ready = [v for v in chosen if not deps[v]]
    pending = {v: len(deps[v]) for v in chosen}
    rdeps = {}
    for v in chosen:
        for d in deps[v]:
            rdeps.setdefault(d, []).append(v)
    while ready:
        # prefer the ready value that frees the most registers (operands at their last use), then smallest
        def gain(v):
            _, a, b = rec[v]
            g = (remaining_uses[a] == 1) + (b != a and remaining_uses[b] == 1)
            return (-g, v)
        ready.sort(key=gain)
        v = ready.pop(0)
        op, a, b = rec[v]
        ri, rj = reg_of[a], reg_of[b]
        for x in {a, b}:
            remaining_uses[x] -= 1 if x != b or a != b else 1
        # operand uses: a and b counted once each above; when a == b only one use was counted in users
        for x in {a, b}:
            if remaining_uses[x] == 0:
                free.append(reg_of[x])
        if not free:
            return None
        d = free.pop()
        reg_of[v] = d
        prog.append([op, ri, rj, d])
        if remaining_uses.get(v, 0) == 0:
            free.append(d)
        done.add(v)
        for w in rdeps.get(v, []):
            pending[w] -= 1
            if pending[w] == 0:
                ready.append(w)
    if len(done) != len(chosen):
        return None
    return prog


def recombine(p, progs, tlimit, workers):
    lim, start = p["limit"], p["start"]
    startset = set(start)
    U = set(start)
    for prog in progs:
        U.update(values_of(p, prog))
    targets = set(p["targets"])
    Ul = sorted(U)
    recipes = []  # (c, op, a, b)
    for a in Ul:
        for b in Ul:
            for op in "+*-/":
                if op in "+*" and a > b:
                    continue
                c = apply(op, a, b, lim)
                if c and c in U and c not in startset and c != a and c != b:
                    recipes.append((c, op, a, b))
    nonstart = [v for v in Ul if v not in startset]
    m = cp_model.CpModel()
    x = {v: m.NewBoolVar("") for v in nonstart}
    o = {v: m.NewIntVar(0, len(Ul), "") for v in nonstart}
    byc = {}
    y = []
    for idx, (c, op, a, b) in enumerate(recipes):
        yv = m.NewBoolVar("")
        y.append(yv)
        byc.setdefault(c, []).append(idx)
        for s in (a, b):
            if s not in startset:
                m.AddImplication(yv, x[s])
                m.Add(o[c] >= o[s] + 1).OnlyEnforceIf(yv)
    for v in nonstart:
        rs = byc.get(v, [])
        if not rs:
            m.Add(x[v] == 0)
        else:
            m.AddBoolOr([y[i] for i in rs]).OnlyEnforceIf(x[v])
        for i in rs:
            m.AddImplication(y[i], x[v])
    for t in targets - startset:
        if t not in x:
            return None
        m.Add(x[t] == 1)
    m.Minimize(sum(x.values()))
    # hint: the shortest input program
    best_in = min(progs, key=len)
    hv = set(values_of(p, best_in))
    for v in nonstart:
        m.AddHint(x[v], 1 if v in hv else 0)
    s = cp_model.CpSolver()
    s.parameters.max_time_in_seconds = tlimit
    s.parameters.num_workers = workers
    st = s.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    chosen = {v for v in nonstart if s.Value(x[v])}
    rec = {}
    for idx, (c, op, a, b) in enumerate(recipes):
        if s.Value(y[idx]) and c in chosen and c not in rec:
            rec[c] = (op, a, b)
    if set(rec) != chosen:
        return None
    prog = schedule(p, chosen, rec)
    return prog, len(chosen), st == cp_model.OPTIMAL, len(U), len(recipes)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("puzzles")
    ap.add_argument("out")
    ap.add_argument("sources", nargs="+")
    ap.add_argument("--ids", default="")
    ap.add_argument("--time", type=float, default=20)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--shard", default="0/1")
    a = ap.parse_args()
    P = elf.load_puzzles(a.puzzles)
    srcs = [elf.read_progs_txt(f) for f in a.sources]
    ids = a.ids.split(",") if a.ids else sorted(P)
    si, sn = map(int, a.shard.split("/"))
    ids = ids[si::sn]
    out = elf.read_progs_txt(a.out) if a.ids == "" and False else {}
    tot_gain = 0
    for n, k in enumerate(ids):
        p = P[k]
        progs = [s[k] for s in srcs if k in s and elf.check_program(p, s[k])[0]]
        if not progs:
            continue
        best = min(progs, key=len)
        t0 = time.time()
        r = recombine(p, progs, a.time, a.workers)
        msg = "fail"
        if r:
            prog, nval, opt, nu, nr = r
            msg = f"values={nu} recipes={nr} chosen={nval} opt={opt} sched={'ok' if prog else 'REGFAIL'}"
            if prog and elf.check_program(p, prog)[0] and len(prog) < len(best):
                tot_gain += len(best) - len(prog)
                best = prog
                msg += " IMPROVED"
        out[k] = best
        print(f"[{n + 1}/{len(ids)}] {k} in={min(map(len, progs))} out={len(best)} {msg} {time.time() - t0:.1f}s gain_total={tot_gain}", flush=True)
        if (n + 1) % 10 == 0:
            elf.write_progs_txt(out, a.out)
    elf.write_progs_txt(out, a.out)
    print("total gain", tot_gain)
