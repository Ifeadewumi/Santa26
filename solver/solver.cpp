// Santa 2026 - The Elf Calculator : portfolio solver
//
// Pipeline per puzzle
//   1. Greedy target-by-target construction on an SSA value pool (<= R live values).
//      Each target is planned with a backward beam search over decompositions
//          m = q*a (+|-) r ,  m = x (+|-) q
//      where a, r, x come from cost tables built from the current pool:
//          cost 0: pool values, cost 1: pool op pool, cost 2: (pool op pool) op pool.
//      Leaves are closed by a meet-in-the-middle check  m = x op y  (x cost<=1, y cost<=2).
//   2. Portfolio of orderings (ascending / cheapest-first / random), gcd seeding for
//      multiplicative structure, randomized parameters, restarts until the time budget.
//   3. Exact iterative-deepening search for small-limit puzzles (provably optimal when it finishes).
//   4. Dead-code elimination + linear-scan register allocation, then every program is replayed
//      by a strict simulator before it is accepted. A guaranteed double-and-add fallback exists.
//
// I/O (plain text, converted from/to CSV by elf.py):
//   puzzles : id k s1..sk m t1..tm limit R
//   programs: id n op i j d op i j d ...
#include <bits/stdc++.h>
using namespace std;
typedef unsigned long long u64;
typedef __uint128_t u128;

static const int INF = 1000000;

static inline double nowSec() {
    return chrono::duration<double>(chrono::steady_clock::now().time_since_epoch()).count();
}
static inline u64 mix64(u64 x) {
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
}
static inline bool doOp(char op, u64 a, u64 b, u64 lim, u64 &r) {
    switch (op) {
    case '+': r = a + b; return r >= a && r <= lim;
    case '-': if (a <= b) return false; r = a - b; return r <= lim;
    case '*': { u128 p = (u128)a * b; if (p > lim) return false; r = (u64)p; return true; }
    case '/': if (b == 0 || a % b) return false; r = a / b; return r >= 1 && r <= lim;
    }
    return false;
}

struct Instr { char op; int i, j, d; };
struct Puzzle {
    string id;
    vector<u64> start, targets, tg;  // tg = sorted unique targets
    u64 limit = 0;
    int R = 48;
};

// ------------------------------------------------------------------ simulator (strict)
static bool simulate(const Puzzle &P, const vector<Instr> &prog) {
    if (prog.size() > 4096) return false;
    int R = P.R;
    if ((int)P.start.size() > R) return false;
    vector<u64> reg(R, 0);
    vector<char> def(R, 0), cov(P.tg.size(), 0);
    size_t nc = 0;
    auto mark = [&](u64 v) {
        auto it = lower_bound(P.tg.begin(), P.tg.end(), v);
        if (it != P.tg.end() && *it == v) { size_t i = it - P.tg.begin(); if (!cov[i]) { cov[i] = 1; nc++; } }
    };
    for (size_t k = 0; k < P.start.size(); k++) { reg[k] = P.start[k]; def[k] = 1; mark(P.start[k]); }
    for (auto &in : prog) {
        if (in.op != '+' && in.op != '-' && in.op != '*' && in.op != '/') return false;
        if (in.i < 0 || in.i >= R || in.j < 0 || in.j >= R || in.d < 0 || in.d >= R) return false;
        if (!def[in.i] || !def[in.j]) return false;
        u64 r;
        if (!doOp(in.op, reg[in.i], reg[in.j], P.limit, r)) return false;
        reg[in.d] = r; def[in.d] = 1; mark(r);
    }
    return nc == P.tg.size();
}

// ------------------------------------------------------------------ SSA -> registers
struct Node { u64 v; char op; int a, b; };

static int tIndex(const vector<u64> &tg, u64 v) {
    auto it = lower_bound(tg.begin(), tg.end(), v);
    return (it != tg.end() && *it == v) ? (int)(it - tg.begin()) : -1;
}

static bool finalizeSSA(const Puzzle &P, const vector<Node> &nodes, int nstart, vector<Instr> &out) {
    int N = nodes.size(), R = P.R;
    if (nstart > R) return false;
    vector<char> cov(P.tg.size(), 0), need(N, 0);
    for (int k = 0; k < nstart; k++) { int t = tIndex(P.tg, nodes[k].v); if (t >= 0) cov[t] = 1; }
    for (int k = nstart; k < N; k++) {
        int t = tIndex(P.tg, nodes[k].v);
        if (t >= 0 && !cov[t]) { cov[t] = 1; need[k] = 1; }
    }
    for (char c : cov) if (!c) return false;
    for (int k = N - 1; k >= nstart; k--) if (need[k]) { need[nodes[k].a] = 1; need[nodes[k].b] = 1; }
    vector<int> kept;
    for (int k = nstart; k < N; k++) if (need[k]) kept.push_back(k);
    vector<int> last(N, -1);
    for (int t = 0; t < (int)kept.size(); t++) { const Node &nd = nodes[kept[t]]; last[nd.a] = t; last[nd.b] = t; }
    vector<int> reg(N, -1), fr;
    for (int r = R - 1; r >= nstart; r--) fr.push_back(r);
    for (int k = 0; k < nstart; k++) { reg[k] = k; if (last[k] < 0) fr.push_back(k); }
    out.clear();
    for (int t = 0; t < (int)kept.size(); t++) {
        int n = kept[t];
        const Node &nd = nodes[n];
        int ri = reg[nd.a], rj = reg[nd.b];
        if (ri < 0 || rj < 0) return false;
        if (last[nd.a] == t) fr.push_back(ri);
        if (nd.b != nd.a && last[nd.b] == t) fr.push_back(rj);
        if (fr.empty()) return false;
        int d = fr.back(); fr.pop_back();
        reg[n] = d;
        out.push_back({nd.op, ri, rj, d});
        if (last[n] < 0) fr.push_back(d);
    }
    return true;
}

// ------------------------------------------------------------------ cost tables
struct Entry { u64 v; int a, b; char op; uint8_t c; };

struct Tables {
    u64 lim = 0;
    vector<Entry> E;
    int n0 = 0, n1 = 0;
    size_t maxE = 0;
    vector<u64> keys; vector<int> vals; u64 mask = 0;
    vector<u64> filt; int fshift = 0;
    vector<pair<u64, int>> srt; bool hasSrt = false;

    void reset(size_t est) {
        size_t cap = 1 << 12;
        while (cap < est * 2) cap <<= 1;
        if (keys.size() != cap) { keys.assign(cap, 0); vals.assign(cap, -1); }
        else memset(keys.data(), 0, cap * sizeof(u64));
        mask = cap - 1; maxE = cap / 2;
        size_t fbits = cap * 8;
        int lg = 63 - __builtin_clzll(fbits);
        fshift = 64 - lg;
        size_t words = fbits >> 6;
        if (filt.size() != words) filt.assign(words, 0);
        else memset(filt.data(), 0, words * sizeof(u64));
        E.clear(); E.reserve(min(est, maxE) + 16);
        hasSrt = false;
    }
    inline int find(u64 v) const {
        u64 h = mix64(v);
        u64 fb = h >> fshift;
        if (!((filt[fb >> 6] >> (fb & 63)) & 1)) return -1;
        u64 i = h & mask;
        while (true) {
            u64 k = keys[i];
            if (k == v) return vals[i];
            if (k == 0) return -1;
            i = (i + 1) & mask;
        }
    }
    inline void add(u64 v, uint8_t c, char op, int a, int b) {
        if (E.size() >= maxE) return;
        u64 h = mix64(v);
        u64 i = h & mask;
        while (true) {
            u64 k = keys[i];
            if (k == v) return;
            if (k == 0) break;
            i = (i + 1) & mask;
        }
        keys[i] = v; vals[i] = (int)E.size();
        E.push_back({v, a, b, op, c});
        u64 fb = h >> fshift;
        filt[fb >> 6] |= 1ULL << (fb & 63);
    }
    void build(const vector<u64> &pool, u64 L, bool L2, size_t l2cap) {
        lim = L;
        size_t P = pool.size();
        size_t est = P + 4 * P * P + 16 + (L2 ? l2cap : 0);
        reset(est);
        for (u64 v : pool) add(v, 0, 0, -1, -1);
        n0 = E.size();
        for (int i = 0; i < n0; i++)
            for (int j = 0; j < n0; j++) {
                u64 a = E[i].v, b = E[j].v, r;
                if (i <= j) {
                    if (doOp('+', a, b, lim, r)) add(r, 1, '+', i, j);
                    if (doOp('*', a, b, lim, r)) add(r, 1, '*', i, j);
                }
                if (a > b && doOp('-', a, b, lim, r)) add(r, 1, '-', i, j);
                if (b > 1 && doOp('/', a, b, lim, r)) add(r, 1, '/', i, j);
            }
        n1 = E.size();
        if (L2) {
            size_t stop = min(maxE, (size_t)n1 + l2cap);
            for (int e = n0; e < n1 && E.size() < stop; e++) {
                u64 x = E[e].v;
                for (int p = 0; p <= n0; p++) {
                    int pe = (p == n0) ? e : p;
                    u64 y = E[pe].v, r;
                    if (doOp('+', x, y, lim, r)) add(r, 2, '+', e, pe);
                    if (doOp('*', x, y, lim, r)) add(r, 2, '*', e, pe);
                    if (x > y && doOp('-', x, y, lim, r)) add(r, 2, '-', e, pe);
                    if (y > x && doOp('-', y, x, lim, r)) add(r, 2, '-', pe, e);
                    if (y > 1 && doOp('/', x, y, lim, r)) add(r, 2, '/', e, pe);
                    if (x > 1 && pe != e && doOp('/', y, x, lim, r)) add(r, 2, '/', pe, e);
                }
            }
        }
    }
    void buildSorted() {
        if (hasSrt) return;
        srt.resize(E.size());
        for (size_t i = 0; i < E.size(); i++) srt[i] = {E[i].v, (int)i};
        sort(srt.begin(), srt.end());
        hasSrt = true;
    }
};

// ------------------------------------------------------------------ parameters
struct Params {
    int mode = 1;          // 0 ascending, 1 cheapest-first, 2 random order
    bool gcd = false;      // build pairwise gcds first (multiplicative structure)
    double gcdDrop = 0.0;
    int beam = 24, termK = 6, maxDepth = 48, estBeam = 4;
    float w = 0.18f;       // heuristic weight: estimated ops per bit of the residual
    bool L2 = true;
    int l2cap = 1500000;
    bool rootWide = true;  // divisors from the whole table at the root
    bool additive = true;  // m = x +- q moves
    int addK = 3;
    u64 smallKeep = 64;    // pool values <= this are evicted last
    bool fallbackOnly = false;
};

struct Step { char op; u64 a, b; };

// ------------------------------------------------------------------ planner (backward beam)
struct BN { u64 m; int acc; int par; int ea, er; uint8_t type; };

struct Planner {
    Tables &T;
    vector<BN> nodes;
    unordered_map<u64, int> seen;  // m -> node index (best acc)
    int best, bNode, bKind, bE, bX, bY; char bOp;
    int depthStart;
    // reconstruction scratch
    unordered_set<u64> prod;
    bool err;
    explicit Planner(Tables &t) : T(t) {}

    int term(u64 m, int bound, char &op, int &ex, int &ey) {
        int bc = bound;
        const auto &E = T.E;
        const u64 lim = T.lim;
        for (int x = 0; x < T.n1; x++) {
            u64 xv = E[x].v; int cx = E[x].c;
            if (cx + 1 >= bc || xv > lim) continue;
            auto tryY = [&](u64 y, char o, bool xf) {
                int e = T.find(y);
                if (e < 0) return;
                int c = cx + E[e].c + 1;
                if (c < bc) { bc = c; op = o; if (xf) { ex = x; ey = e; } else { ex = e; ey = x; } }
            };
            if (m > xv) tryY(m - xv, '+', true);
            else if (xv > m) tryY(xv - m, '-', true);
            if (m <= lim - xv) tryY(m + xv, '-', false);
            if (m % xv == 0) tryY(m / xv, '*', true);
            if (xv > m && xv % m == 0) tryY(xv / m, '/', true);
            if ((u128)m * xv <= lim) tryY(m * xv, '/', false);
        }
        return bc;
    }

    void child(int par, u64 q, int acc, uint8_t type, int ea, int er, vector<int> &cand) {
        if (acc >= best || q == 0) return;
        int eq = T.find(q);
        if (eq >= 0) {
            int tot = acc + T.E[eq].c;
            if (tot < best) {
                nodes.push_back({q, acc, par, ea, er, type});
                best = tot; bNode = (int)nodes.size() - 1; bKind = 0; bE = eq;
            }
            return;
        }
        auto it = seen.find(q);
        if (it != seen.end()) {
            BN &o = nodes[it->second];
            if (o.acc <= acc) return;
            if (it->second >= depthStart) { o = {q, acc, par, ea, er, type}; return; }
        }
        nodes.push_back({q, acc, par, ea, er, type});
        seen[q] = (int)nodes.size() - 1;
        cand.push_back((int)nodes.size() - 1);
    }

    bool isAvail(u64 v) {
        int e = T.find(v);
        return (e >= 0 && T.E[e].c == 0) || prod.count(v);
    }
    void emit(int e, vector<Step> &steps) {
        const Entry &en = T.E[e];
        if (en.c == 0 || prod.count(en.v)) return;
        emit(en.a, steps); emit(en.b, steps);
        steps.push_back({en.op, T.E[en.a].v, T.E[en.b].v});
        prod.insert(en.v);
    }
    u64 addStep(char op, u64 a, u64 b, vector<Step> &steps) {
        u64 r;
        if (!doOp(op, a, b, T.lim, r)) { err = true; return 1; }
        if (isAvail(r)) return r;
        steps.push_back({op, a, b});
        prod.insert(r);
        return r;
    }

    bool plan(u64 n, const Params &p, int beamW, int termK, vector<Step> &steps, int &estCost) {
        const auto &E = T.E;
        const u64 lim = T.lim;
        steps.clear(); prod.clear(); err = false;
        int e0 = T.find(n);
        if (e0 >= 0) { emit(e0, steps); estCost = E[e0].c; return !err; }
        nodes.clear(); seen.clear();
        best = INF; bNode = -1;
        nodes.push_back({n, 0, -1, -1, -1, 0});
        {
            char op = '+'; int ex = -1, ey = -1;
            int c = term(n, INF, op, ex, ey);
            if (c < INF) { best = c; bNode = 0; bKind = 1; bOp = op; bX = ex; bY = ey; }
        }
        vector<int> beam{0}, cand;
        vector<pair<float, int>> sc;
        for (int depth = 0; depth < p.maxDepth && !beam.empty(); depth++) {
            cand.clear();
            depthStart = nodes.size();
            for (int s : beam) {
                u64 m = nodes[s].m; int acc = nodes[s].acc;
                if (acc + 2 >= best) continue;
                int dl = (depth == 0 && p.rootWide) ? (int)E.size() : T.n1;
                for (int e = 0; e < dl; e++) {
                    u64 a = E[e].v;
                    if (a < 2 || a > m) continue;
                    int base = acc + E[e].c;
                    if (base + 2 >= best) continue;
                    u64 q = m / a, r = m - q * a;
                    if (r == 0) child(s, q, base + 1, 1, e, -1, cand);
                    else {
                        int er = T.find(r);
                        if (er >= 0) child(s, q, base + E[er].c + 2, 2, e, er, cand);
                        u64 r2 = a - r;
                        if (m <= lim - r2) {
                            int e2 = T.find(r2);
                            if (e2 >= 0) child(s, q + 1, base + E[e2].c + 2, 3, e, e2, cand);
                        }
                    }
                }
                if (p.additive) {
                    T.buildSorted();
                    const auto &S = T.srt;
                    size_t pos = lower_bound(S.begin(), S.end(), make_pair(m, -1)) - S.begin();
                    for (int k = 1; k <= p.addK && (long)pos - k >= 0; k++) {
                        const auto &pr = S[pos - k];
                        if (pr.first >= m) continue;
                        child(s, m - pr.first, acc + E[pr.second].c + 1, 4, pr.second, -1, cand);
                    }
                    size_t st = pos;
                    while (st < S.size() && S[st].first == m) st++;
                    for (int k = 0; k < p.addK && st + k < S.size(); k++) {
                        const auto &pr = S[st + k];
                        child(s, pr.first - m, acc + E[pr.second].c + 1, 5, pr.second, -1, cand);
                    }
                }
            }
            sc.clear();
            for (int c : cand) {
                if (nodes[c].acc + 2 >= best) continue;
                sc.push_back({(float)nodes[c].acc + p.w * (float)log2((double)nodes[c].m), c});
            }
            int B = min((int)sc.size(), beamW);
            if (B == 0) break;
            partial_sort(sc.begin(), sc.begin() + B, sc.end());
            beam.clear();
            for (int i = 0; i < B; i++) {
                int c = sc[i].second;
                beam.push_back(c);
                if (i < termK) {
                    char op = '+'; int ex = -1, ey = -1;
                    int bound = best - nodes[c].acc;
                    if (bound <= 2) continue;
                    int tc = term(nodes[c].m, bound, op, ex, ey);
                    if (tc < bound) { best = nodes[c].acc + tc; bNode = c; bKind = 1; bOp = op; bX = ex; bY = ey; }
                }
            }
        }
        if (bNode < 0) return false;
        // reconstruct forward steps
        vector<int> chain;
        for (int i = bNode; i != -1; i = nodes[i].par) chain.push_back(i);
        u64 cur;
        if (bKind == 0) { emit(bE, steps); cur = E[bE].v; }
        else { emit(bX, steps); emit(bY, steps); cur = addStep(bOp, E[bX].v, E[bY].v, steps); }
        if (cur != nodes[chain[0]].m) return false;
        for (size_t k = 0; k + 1 < chain.size(); k++) {
            const BN &c = nodes[chain[k]];
            u64 m = c.m;
            switch (c.type) {
            case 1: emit(c.ea, steps); cur = addStep('*', m, E[c.ea].v, steps); break;
            case 2: { emit(c.ea, steps); emit(c.er, steps); u64 pr = addStep('*', m, E[c.ea].v, steps); cur = addStep('+', pr, E[c.er].v, steps); break; }
            case 3: { emit(c.ea, steps); emit(c.er, steps); u64 pr = addStep('*', m, E[c.ea].v, steps); cur = addStep('-', pr, E[c.er].v, steps); break; }
            case 4: emit(c.ea, steps); cur = addStep('+', E[c.ea].v, m, steps); break;
            case 5: emit(c.ea, steps); cur = addStep('-', E[c.ea].v, m, steps); break;
            default: return false;
            }
            if (err || cur != nodes[chain[k + 1]].m) return false;
        }
        estCost = best;
        return !err && cur == n;
    }
};

// ------------------------------------------------------------------ builder (pool with eviction)
struct Builder {
    const Puzzle &P; u64 lim; int R;
    vector<Node> nodes; int nstart;
    vector<int> pool;
    unordered_map<u64, int> where;
    vector<long long> stamp; long long clk = 0;
    vector<char> cov; int uncovered;
    u64 smallKeep;

    Builder(const Puzzle &p, u64 sk) : P(p), lim(p.limit), R(p.R), smallKeep(sk) {
        cov.assign(P.tg.size(), 0); uncovered = P.tg.size();
        for (size_t k = 0; k < P.start.size(); k++) {
            u64 v = P.start[k];
            nodes.push_back({v, 0, -1, -1}); stamp.push_back(0);
            if (!where.count(v)) { where[v] = k; pool.push_back(k); }
            markCov(v);
        }
        nstart = nodes.size();
    }
    void markCov(u64 v) { int i = tIndex(P.tg, v); if (i >= 0 && !cov[i]) { cov[i] = 1; uncovered--; } }
    bool has(u64 v) const { return where.count(v) > 0; }
    vector<u64> poolValues() const { vector<u64> r; for (int n : pool) r.push_back(nodes[n].v); return r; }

    bool exec(char op, u64 va, u64 vb, const vector<u64> &prot) {
        auto ia = where.find(va), ib = where.find(vb);
        if (ia == where.end() || ib == where.end()) return false;
        int na = ia->second, nb = ib->second;
        u64 r;
        if (!doOp(op, va, vb, lim, r)) return false;
        clk++; stamp[na] = clk; stamp[nb] = clk;
        auto ir = where.find(r);
        if (ir != where.end()) { stamp[ir->second] = clk; return true; }
        if ((int)pool.size() >= R) {
            int bi = -1; long long bk = LLONG_MAX;
            for (int idx = 0; idx < (int)pool.size(); idx++) {
                u64 v = nodes[pool[idx]].v;
                if (v == va || v == vb) continue;
                bool pr = false;
                for (u64 x : prot) if (x == v) { pr = true; break; }
                if (pr) continue;
                long long key = stamp[pool[idx]] + (v <= smallKeep ? (1LL << 40) : 0);
                if (key < bk) { bk = key; bi = idx; }
            }
            if (bi < 0) return false;
            where.erase(nodes[pool[bi]].v);
            pool[bi] = pool.back(); pool.pop_back();
        }
        int id = nodes.size();
        nodes.push_back({r, op, na, nb}); stamp.push_back(clk);
        pool.push_back(id); where[r] = id;
        markCov(r);
        return true;
    }
    bool runSteps(const vector<Step> &st) {
        vector<u64> prot;
        for (size_t s = 0; s < st.size(); s++) {
            prot.clear();
            for (size_t t = s + 1; t < st.size(); t++) { prot.push_back(st[t].a); prot.push_back(st[t].b); }
            if (!exec(st[s].op, st[s].a, st[s].b, prot)) return false;
        }
        return true;
    }
};

static vector<Step> fallbackSteps(const Builder &B, u64 n) {
    vector<Step> st;
    if (!B.has(1)) { u64 s = B.nodes[B.pool[0]].v; st.push_back({'/', s, s}); }
    if (n <= 1) return st;
    int hb = 63 - __builtin_clzll(n);
    u64 acc = 1;
    for (int b = hb - 1; b >= 0; b--) {
        st.push_back({'+', acc, acc}); acc *= 2;
        if ((n >> b) & 1) { st.push_back({'+', acc, 1}); acc += 1; }
    }
    return st;
}

static vector<u64> gcdCands(const vector<u64> &tg, const vector<char> &cov, mt19937_64 &rng, double drop) {
    vector<u64> rem;
    for (size_t i = 0; i < tg.size(); i++) if (!cov[i]) rem.push_back(tg[i]);
    set<u64> S;
    for (size_t i = 0; i < rem.size(); i++)
        for (size_t j = i + 1; j < rem.size(); j++) { u64 g = std::gcd(rem[i], rem[j]); if (g >= 8) S.insert(g); }
    vector<u64> G(S.begin(), S.end());
    if (G.size() > 200) { shuffle(G.begin(), G.end(), rng); G.resize(200); }
    for (size_t i = 0; i < G.size(); i++)
        for (size_t j = i + 1; j < G.size(); j++) { u64 g = std::gcd(G[i], G[j]); if (g >= 8) S.insert(g); }
    vector<u64> out;
    uniform_real_distribution<double> U(0, 1);
    for (u64 g : S) {
        int cnt = 0;
        for (u64 t : rem) if (t % g == 0) cnt++;
        if (cnt >= 2 && U(rng) >= drop) out.push_back(g);
    }
    sort(out.begin(), out.end());
    return out;
}

// ------------------------------------------------------------------ one greedy run
static bool runStrategy(const Puzzle &P, const Params &p, Tables &T, Planner &PL, mt19937_64 &rng,
                        vector<Instr> &out, double deadline, bool mustFinish) {
    Builder B(P, p.smallKeep);
    Params pe = p; pe.rootWide = false; pe.additive = false; pe.maxDepth = min(p.maxDepth, 24);
    bool fresh = false;  // tables match the current pool
    auto doTarget = [&](u64 t) -> bool {
        vector<Step> st; int est;
        bool ok = false;
        if (!p.fallbackOnly) {
            if (!fresh) T.build(B.poolValues(), P.limit, p.L2, p.l2cap);
            ok = PL.plan(t, p, p.beam, p.termK, st, est);
        }
        fresh = false;
        if (!ok) st = fallbackSteps(B, t);
        if (B.runSteps(st)) return true;
        st = fallbackSteps(B, t);
        return B.runSteps(st);
    };
    if (p.gcd && !p.fallbackOnly) {
        for (u64 g : gcdCands(P.tg, B.cov, rng, p.gcdDrop)) {
            if (!mustFinish && nowSec() > deadline) return false;
            if (!B.has(g) && !doTarget(g)) return false;
        }
    }
    vector<u64> order;
    for (size_t i = 0; i < P.tg.size(); i++) if (!B.cov[i]) order.push_back(P.tg[i]);
    if (p.mode == 2) shuffle(order.begin(), order.end(), rng);
    while (B.uncovered > 0) {
        if (!mustFinish && nowSec() > deadline) return false;
        vector<u64> rem;
        for (u64 t : order) if (!B.cov[tIndex(P.tg, t)]) rem.push_back(t);
        if (rem.empty()) break;
        u64 pick = 0;
        if (!p.fallbackOnly) {
            T.build(B.poolValues(), P.limit, p.L2, p.l2cap);
            fresh = true;
            int pc = INF;
            for (u64 t : rem) { int e = T.find(t); if (e >= 0 && T.E[e].c < pc) { pc = T.E[e].c; pick = t; } }
            if (pick == 0 && p.mode == 1) {
                for (u64 t : rem) {
                    char op; int ex, ey;
                    int c = PL.term(t, pc, op, ex, ey);
                    if (c < pc) { pc = c; pick = t; }
                }
                if (pick == 0 || pc > 4) {
                    for (u64 t : rem) {
                        vector<Step> st; int est;
                        if (PL.plan(t, pe, p.estBeam, 2, st, est) && est < pc) { pc = est; pick = t; }
                    }
                }
            }
        }
        if (pick == 0) pick = rem[0];
        if (!doTarget(pick)) return false;
    }
    if (!finalizeSSA(P, B.nodes, B.nstart, out)) return false;
    return simulate(P, out);
}

// ------------------------------------------------------------------ exact search for small limits
struct Exact {
    const Puzzle &P; u64 lim;
    vector<u64> vals; vector<int> ia, ib; vector<char> iop;
    vector<char> pres; vector<int> tIdx, stampA, posA; int stampCtr = 0;
    vector<char> cov; int unc = 0;
    long long cnt = 0; double deadline; bool aborted = false;
    struct C { u64 r; char op; int i, j; bool ul; bool isT; };

    Exact(const Puzzle &p, double dl) : P(p), lim(p.limit), deadline(dl) {
        pres.assign(lim + 1, 0); tIdx.assign(lim + 1, -1); stampA.assign(lim + 1, 0); posA.assign(lim + 1, 0);
        cov.assign(P.tg.size(), 0); unc = P.tg.size();
        for (size_t i = 0; i < P.tg.size(); i++) if (P.tg[i] <= lim) tIdx[P.tg[i]] = i;
        for (u64 v : P.start) {
            vals.push_back(v); ia.push_back(-1); ib.push_back(-1); iop.push_back(0);
            if (v <= lim) { pres[v] = 1; int t = tIdx[v]; if (t >= 0 && !cov[t]) { cov[t] = 1; unc--; } }
        }
    }
    bool dfs(int left, int last) {
        if (unc == 0) return true;
        if (unc > left || aborted) return false;
        if ((++cnt & 1023) == 0 && nowSec() > deadline) { aborted = true; return false; }
        int n = vals.size();
        vector<C> cs;
        int st = ++stampCtr;
        auto addC = [&](u64 r, char op, int i, int j) {
            if (r > lim || pres[r]) return;
            bool ul = (i == last || j == last);
            if (stampA[r] != st) {
                stampA[r] = st; posA[r] = cs.size();
                int t = tIdx[r];
                cs.push_back({r, op, i, j, ul, t >= 0 && !cov[t]});
            } else if (ul && !cs[posA[r]].ul) {
                C &c = cs[posA[r]]; c.op = op; c.i = i; c.j = j; c.ul = true;
            }
        };
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++) {
                u64 a = vals[i], b = vals[j], r;
                if (i <= j) {
                    if (doOp('+', a, b, lim, r)) addC(r, '+', i, j);
                    if (doOp('*', a, b, lim, r)) addC(r, '*', i, j);
                }
                if (a > b && doOp('-', a, b, lim, r)) addC(r, '-', i, j);
                if (b > 1 && doOp('/', a, b, lim, r)) addC(r, '/', i, j);
            }
        bool mustT = (unc == left);
        stable_sort(cs.begin(), cs.end(), [](const C &x, const C &y) { return x.isT > y.isT; });
        for (const C &c : cs) {
            if (mustT && !c.isT) continue;
            if (last >= 0 && !c.ul && c.r < vals[last]) continue;  // canonical order
            vals.push_back(c.r); ia.push_back(c.i); ib.push_back(c.j); iop.push_back(c.op);
            pres[c.r] = 1;
            int t = tIdx[c.r];
            bool wasT = c.isT;
            if (wasT) { cov[t] = 1; unc--; }
            if (dfs(left - 1, vals.size() - 1)) return true;
            if (wasT) { cov[t] = 0; unc++; }
            pres[c.r] = 0;
            vals.pop_back(); ia.pop_back(); ib.pop_back(); iop.pop_back();
            if (aborted) return false;
        }
        return false;
    }
    // returns: 1 found (optimal), 0 proven none up to maxD, -1 aborted
    int solve(int maxD, vector<Instr> &out) {
        if (unc == 0) { out.clear(); return 1; }
        for (int D = unc; D <= maxD; D++) {
            if (dfs(D, -1)) {
                vector<Node> nodes;
                for (size_t k = 0; k < vals.size(); k++) nodes.push_back({vals[k], iop[k], ia[k], ib[k]});
                if (!finalizeSSA(P, nodes, (int)P.start.size(), out)) return -1;
                return simulate(P, out) ? 1 : -1;
            }
            if (aborted) return -1;
        }
        return 0;
    }
};

// ------------------------------------------------------------------ portfolio per puzzle
static Params randomParams(mt19937_64 &rng) {
    uniform_real_distribution<double> U(0, 1);
    Params p;
    p.mode = rng() % 3;
    p.gcd = U(rng) < 0.35;
    p.gcdDrop = U(rng) < 0.5 ? 0.0 : 0.3 * U(rng);
    static const int beams[] = {8, 16, 24, 32, 48, 64, 96};
    p.beam = beams[rng() % 7];
    p.termK = 2 + rng() % 10;
    p.w = 0.08f + 0.27f * (float)U(rng);
    p.L2 = U(rng) < 0.8;
    p.rootWide = U(rng) < 0.6;
    p.additive = U(rng) < 0.6;
    p.addK = 1 + rng() % 5;
    static const u64 sk[] = {8, 64, 1024, 100000};
    p.smallKeep = sk[rng() % 4];
    return p;
}

struct Result { vector<Instr> prog; bool have = false; int runs = 0; bool optimal = false; string tag = "init"; };

static string tagOf(const Params &p) {
    char b[160];
    snprintf(b, sizeof b, "m%d%s b%d k%d w%.2f L%d rw%d ad%d/%d sk%llu%s", p.mode, p.gcd ? "g" : "", p.beam, p.termK, p.w, (int)p.L2,
             (int)p.rootWide, (int)p.additive, p.addK, (unsigned long long)p.smallKeep, p.fallbackOnly ? " FB" : "");
    return b;
}

static Result solvePuzzle(const Puzzle &P, const Result &init, double budget, u64 seed, Tables &T, Planner &PL) {
    double t0 = nowSec(), deadline = t0 + budget;
    mt19937_64 rng(seed ^ mix64(std::hash<string>()(P.id)));
    Result best = init;
    int lb = 0;
    {
        vector<char> c(P.tg.size(), 0);
        for (u64 v : P.start) { int t = tIndex(P.tg, v); if (t >= 0) c[t] = 1; }
        for (char x : c) lb += !x;
    }
    auto consider = [&](vector<Instr> &prog, const string &tag) {
        if (!simulate(P, prog)) return;
        if (!best.have || prog.size() < best.prog.size()) { best.prog = prog; best.have = true; best.tag = tag; }
    };
    if (best.have && (int)best.prog.size() <= lb) { best.optimal = true; return best; }

    vector<Params> fixed;
    { Params p; p.mode = 1; fixed.push_back(p); }
    { Params p; p.mode = 0; fixed.push_back(p); }
    { Params p; p.mode = 1; p.gcd = true; fixed.push_back(p); }
    { Params p; p.mode = 1; p.beam = 64; p.termK = 10; p.w = 0.14f; fixed.push_back(p); }
    { Params p; p.mode = 0; p.gcd = true; p.L2 = false; fixed.push_back(p); }

    for (size_t k = 0; k < fixed.size() || !best.have; k++) {
        if (best.have && nowSec() > deadline) break;
        vector<Instr> prog;
        Params p = k < fixed.size() ? fixed[k] : Params();
        if (k >= fixed.size()) p.fallbackOnly = true;
        if (runStrategy(P, p, T, PL, rng, prog, deadline, !best.have)) consider(prog, "F" + to_string(k) + " " + tagOf(p));
        best.runs++;
        if (k > fixed.size() + 2) break;
        if (k == 0 && P.limit <= (1u << 20) && best.have && (int)best.prog.size() > lb) {
            Exact ex(P, t0 + max(1.0, budget * 0.6));
            vector<Instr> eo;
            int r = ex.solve((int)best.prog.size() - 1, eo);
            if (r == 1) { consider(eo, "exact"); best.optimal = true; return best; }
            if (r == 0) { best.optimal = true; return best; }  // nothing shorter exists
        }
    }
    while (best.have && (int)best.prog.size() > lb && nowSec() < deadline) {
        Params p = randomParams(rng);
        vector<Instr> prog;
        if (runStrategy(P, p, T, PL, rng, prog, deadline, false)) consider(prog, "R " + tagOf(p));
        best.runs++;
    }
    if (best.have && (int)best.prog.size() <= lb) best.optimal = true;
    return best;
}

// ------------------------------------------------------------------ I/O
static vector<Puzzle> readPuzzles(const string &fn) {
    ifstream f(fn);
    vector<Puzzle> ps;
    string id;
    while (f >> id) {
        Puzzle P; P.id = id;
        size_t k; f >> k; P.start.resize(k); for (auto &x : P.start) f >> x;
        size_t m; f >> m; P.targets.resize(m); for (auto &x : P.targets) f >> x;
        f >> P.limit >> P.R;
        P.tg = P.targets; sort(P.tg.begin(), P.tg.end()); P.tg.erase(unique(P.tg.begin(), P.tg.end()), P.tg.end());
        ps.push_back(P);
    }
    return ps;
}
static unordered_map<string, vector<Instr>> readProgs(const string &fn) {
    unordered_map<string, vector<Instr>> r;
    ifstream f(fn);
    string id;
    while (f >> id) {
        size_t n; f >> n;
        vector<Instr> p(n);
        for (auto &in : p) { string op; f >> op >> in.i >> in.j >> in.d; in.op = op[0]; }
        r[id] = p;
    }
    return r;
}
static void writeProgs(const string &fn, const vector<Puzzle> &ps, const vector<Result> &res) {
    string tmp = fn + ".tmp";
    {
        ofstream f(tmp);
        for (size_t i = 0; i < ps.size(); i++) {
            if (!res[i].have) continue;
            f << ps[i].id << ' ' << res[i].prog.size();
            for (auto &in : res[i].prog) f << ' ' << in.op << ' ' << in.i << ' ' << in.j << ' ' << in.d;
            f << '\n';
        }
    }
    rename(tmp.c_str(), fn.c_str());
}

int main(int argc, char **argv) {
    string pf, of, inf, only;
    double total = 600, maxPer = 1e18;
    int threads = max(1u, thread::hardware_concurrency());
    u64 seed = 2026;
    for (int i = 1; i < argc; i++) {
        string a = argv[i];
        auto nx = [&]() { return string(argv[++i]); };
        if (a == "--puzzles") pf = nx();
        else if (a == "--out") of = nx();
        else if (a == "--init") inf = nx();
        else if (a == "--total") total = stod(nx());
        else if (a == "--max-per") maxPer = stod(nx());
        else if (a == "--threads") threads = stoi(nx());
        else if (a == "--seed") seed = stoull(nx());
        else if (a == "--only") only = nx();
    }
    if (pf.empty() || of.empty()) { fprintf(stderr, "usage: solver --puzzles f --out f [--init f] [--total sec] [--threads n]\n"); return 2; }
    vector<Puzzle> ps = readPuzzles(pf);
    if (!only.empty()) { vector<Puzzle> q; for (auto &p : ps) if (p.id == only) q.push_back(p); ps = q; }
    int N = ps.size();
    vector<Result> res(N);
    long long initScore = 0; int initCnt = 0;
    if (!inf.empty()) {
        auto ip = readProgs(inf);
        for (int i = 0; i < N; i++) {
            auto it = ip.find(ps[i].id);
            if (it != ip.end() && simulate(ps[i], it->second)) { res[i].prog = it->second; res[i].have = true; initScore += it->second.size(); initCnt++; }
        }
    }
    fprintf(stderr, "puzzles=%d init_valid=%d init_score=%lld threads=%d total=%.0fs\n", N, initCnt, initScore, threads, total);

    vector<double> wgt(N);
    double remW = 0;
    for (int i = 0; i < N; i++) { wgt[i] = 1.0 + ps[i].tg.size(); remW += wgt[i]; }
    vector<int> order(N);
    iota(order.begin(), order.end(), 0);
    sort(order.begin(), order.end(), [&](int a, int b) { return wgt[a] > wgt[b]; });

    double gStart = nowSec(), gEnd = gStart + total;
    atomic<int> next(0), done(0);
    mutex mu;
    long long improvedSum = 0;
    auto worker = [&]() {
        Tables T; Planner PL(T);
        while (true) {
            int k = next++;
            if (k >= N) break;
            int i = order[k];
            double budget;
            {
                lock_guard<mutex> lg(mu);
                double left = max(0.5, gEnd - nowSec());
                budget = min(maxPer, 0.95 * left * threads * wgt[i] / max(remW, 1e-9));
                remW -= wgt[i];
            }
            Result init;
            { lock_guard<mutex> lg(mu); init = res[i]; }
            double t0 = nowSec();
            Result r = solvePuzzle(ps[i], init, budget, seed, T, PL);
            lock_guard<mutex> lg(mu);
            int before = init.have ? (int)init.prog.size() : -1;
            res[i] = r;
            if (before >= 0) improvedSum += before - (int)r.prog.size();
            int d = ++done;
            fprintf(stderr, "[%d/%d] %s targets=%zu len=%d prev=%d runs=%d %s %.1fs/%.1fs | %s\n", d, N, ps[i].id.c_str(),
                    ps[i].tg.size(), r.have ? (int)r.prog.size() : -1, before, r.runs, r.optimal ? "OPT" : "", nowSec() - t0, budget, r.tag.c_str());
        }
    };
    vector<thread> th;
    for (int t = 0; t < threads; t++) th.emplace_back(worker);
    // periodic checkpoint
    atomic<bool> fin(false);
    thread ck([&]() {
        double lastW = nowSec();
        while (!fin) {
            this_thread::sleep_for(chrono::milliseconds(500));
            if (nowSec() - lastW > 120) { lock_guard<mutex> lg(mu); writeProgs(of, ps, res); lastW = nowSec(); }
        }
    });
    for (auto &t : th) t.join();
    fin = true; ck.join();
    writeProgs(of, ps, res);
    long long sc = 0; int have = 0;
    for (auto &r : res) if (r.have) { sc += r.prog.size(); have++; }
    fprintf(stderr, "DONE solved=%d/%d score=%lld improved_vs_init=%lld time=%.0fs\n", have, N, sc, improvedSum, nowSec() - gStart);
    return 0;
}
