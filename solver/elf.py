"""Santa 2026 - The Elf Calculator: CSV <-> solver text I/O, strict verifier, best-of merging."""
import csv
import glob
import json
import os

csv.field_size_limit(2**31 - 1)
OPS = {"+", "-", "*", "/"}


def load_puzzles(path):
    P = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            P[r["id"]] = dict(
                start=[int(x) for x in json.loads(r["starting_values"])],
                targets=[int(x) for x in json.loads(r["targets"])],
                limit=int(r["value_limit"]),
                R=int(r.get("registers") or 48),
            )
    return P


def write_puzzles_txt(P, path):
    with open(path, "w") as f:
        for pid, p in P.items():
            f.write(" ".join(map(str, [pid, len(p["start"]), *p["start"], len(p["targets"]), *p["targets"], p["limit"], p["R"]])) + "\n")


def check_program(p, prog):
    """Strict replay of the published rules. Returns (ok, message)."""
    if not isinstance(prog, list) or len(prog) > 4096:
        return False, "not a list or > 4096 instructions"
    R, lim = p["R"], p["limit"]
    reg = [None] * R
    for k, v in enumerate(p["start"]):
        reg[k] = v
    need = set(p["targets"]) - set(p["start"])
    for s, ins in enumerate(prog):
        if not isinstance(ins, list) or len(ins) != 4 or ins[0] not in OPS:
            return False, f"step {s}: malformed {ins}"
        op, i, j, d = ins
        if any(type(x) is not int or not 0 <= x < R for x in (i, j, d)):
            return False, f"step {s}: bad register {ins}"
        a, b = reg[i], reg[j]
        if a is None or b is None:
            return False, f"step {s}: undefined source"
        if op == "+":
            r = a + b
        elif op == "-":
            r = a - b
        elif op == "*":
            r = a * b
        else:
            if a % b:
                return False, f"step {s}: inexact division {a}/{b}"
            r = a // b
        if r < 1 or r > lim:
            return False, f"step {s}: result {r} out of range"
        reg[d] = r
        need.discard(r)
    if need:
        return False, f"{len(need)} targets not covered"
    return True, "ok"


def load_submission(path):
    """Return {id: program} from a CSV with header id,program (rows that fail to parse are skipped)."""
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.reader(f)
        if next(rd, None) != ["id", "program"]:
            raise ValueError("not a submission file")
        for row in rd:
            if len(row) != 2:
                continue
            try:
                out[row[0]] = json.loads(row[1])
            except Exception:
                pass
    return out


def write_progs_txt(progs, path):
    with open(path, "w") as f:
        for pid, prog in progs.items():
            f.write(" ".join([pid, str(len(prog))] + [f"{o} {i} {j} {d}" for o, i, j, d in prog]) + "\n")


def read_progs_txt(path):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for line in f:
            t = line.split()
            if not t:
                continue
            n = int(t[1])
            out[t[0]] = [[t[2 + 4 * k], int(t[3 + 4 * k]), int(t[4 + 4 * k]), int(t[5 + 4 * k])] for k in range(n)]
    return out


def merge_best(P, *sources):
    """Per puzzle, keep the shortest program that passes check_program."""
    best = {}
    for src in sources:
        for pid, prog in src.items():
            if pid in P and (pid not in best or len(prog) < len(best[pid])) and check_program(P[pid], prog)[0]:
                best[pid] = prog
    return best


def collect_submissions(root):
    """All valid id,program CSVs found under root (sample submission, earlier outputs ...)."""
    found = []
    for path in glob.glob(os.path.join(root, "**", "*.csv"), recursive=True):
        try:
            found.append((path, load_submission(path)))
        except Exception:
            pass
    return found


def write_submission(P, best, path):
    missing = [pid for pid in P if pid not in best]
    if missing:
        raise RuntimeError(f"{len(missing)} puzzles have no valid program, e.g. {missing[:3]}")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "program"])
        for pid in P:
            w.writerow([pid, json.dumps(best[pid], separators=(",", ":"))])
    return sum(len(best[pid]) for pid in P)


def lower_bound(p):
    return len(set(p["targets"]) - set(p["start"]))
