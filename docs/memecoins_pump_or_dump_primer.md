# Memecoins: Pump or Dump? A Primer for Winning

Competition: *Memecoins: Pump or Dump? Predict Pump.fun Launches on Solana* (Kaggle community competition, about 300 teams, $5,000 prize pool).
Written 2026-11-24. **The freeze is 30 Nov 2026 23:59 UTC, six days from now.**

> **Source caveat.** Kaggle's pages render with JavaScript and I could not load them. The facts below come from search snippets of the Overview page and from a public solution repo (`satyam-257/Memecoing_pump_or_dump`), which copies the host's starter notebooks and three public notebooks. Items marked **[verify]** are second-hand or inferred. Read the Overview, Evaluation, Rules and Data tabs yourself on day 1, and use the checklist in §11.

---

## 0. The one-paragraph version

Every day several hundred pump.fun tokens "graduate" from the bonding curve into a PumpSwap AMM pool. Sixty seconds after each graduation you either skip the token (PnL exactly 0) or buy 1 SOL of it with a take-profit multiple `tp` between 3 and 100. You then hold for one hour. Buying everything loses about 0.53 SOL per token, and only about 6% of tokens ever reach 5x. **You win by refusing almost everything.** On the handful of tokens you do buy, you need calibrated probabilities that the price holds above each multiple. The official ranking comes from a league bot. It re-runs your frozen notebook in a sealed sandbox on future, unseen days. So the job is to build a robust forward-trading system, not to overfit one Kaggle day. Three things decide this competition: leakage discipline, calibration and EV-based tp selection, and an engineering design that never crashes.

---

## 1. The rules as best reconstructed

### 1.1 The decision
- Event: token `mint` migrates (pump.fun bonding curve to PumpSwap AMM) at Unix time `mt`.
- Decision time: `mt + 60s`. You see the creation record, the full bonding-curve tape and the first 60 s of the AMM tape.
- Entry price `S_entry` is the last executed AMM pool trade at or before t = 60 s. `X_t = S_t / S_entry`.
- Output: one row per test token, `mint,tp`. `tp` must be 0 (skip) or a value in [3.0, 100.0]. Rows follow the order of `sample_submission.csv`.

### 1.2 The payoff (1 SOL stake, cost c = 0.30 round trip)
```
M = TrimMax_{t in (60, 3660]} X_t     # "sustained" peak: the top max(1%, 1) prints in the window are discarded  [verify]
F = S_3660 / S_entry                  # terminal multiple after one hour

payoff(tp) = 0                          if tp == 0
           = tp - 1.3                   if M >= tp         (take-profit filled)
           = max(F - 1.3, -1.0)         otherwise          (forced exit at 1 h; loss capped at the stake)
```
```python
def payoff(tp, mx, fx):
    return np.where(tp > 0, np.where(mx >= tp, tp - 1.3, np.maximum(fx - 1.3, -1.0)), 0.0)
```
Consequences:
- The 0.30 cost is large. At tp = 3 a winning trade nets only 1.7.
- The trimmed max means a single spike print does not fill you. Thin tokens with few prints after entry get trimmed hard.
- A miss is not always a loss. A token can peak at 4.8 and close at 3.0, which pays +1.7 at tp = 5. Most misses, though, lose close to the full −1.
- No stop-loss exists. The payoff is a **triple-barrier label** (López de Prado, AFML ch. 3) with an upper barrier and a time barrier and no lower barrier.

### 1.3 Data (as read by public notebooks) [verify exact files on the Data tab]
| File | Key columns | Notes |
|---|---|---|
| `train.csv` | `mint, mt, max_x, final_x` | About 30 rolling days, about 16–19k tokens. Older files use `finalx`, so rename it. |
| `test.csv` | `mint, mt` | **One day**, about 300–700 tokens. |
| `sample_submission.csv` | `mint, tp` | Row order is authoritative. |
| `pumpfun_token_creation.csv` | `mint, creator, name, symbol, url, token_program, created_ts, bundle_structure, bundle_size, bundled_buys, bundled_buys_count, dev_balance, gas_used, amount_of_instructions, amount_of_lookup_reads/writes, creation_ix_index, pf_program_index, direct_pf_invocation, is_cashback_enabled` | One row per mint. Deduplicate it. |
| `pfamm_migrations.csv` | `mint, mt, user, mint_amount (1e6), sol_amount (1e9), pool_migration_fee (1e9), tx_idx` | Liquidity at migration. |
| `trades/day=YYYY-MM-DD/pumpfun_all_swaps.parquet` (or `day_{d}_pumpfun_all_swaps.parquet`) | `mint, ts_rel, tx_idx, slot, direction, failed, sol, tok, new_price, wallet, signing_wallet, fee_payer, fee, provided_gas_fee, consumed_gas, min_amount_out, max_amount_in` | Bonding-curve tape. `failed=1` marks reverted attempts. `direction` is text such as "buy"/"sell". |
| `trades/day=.../pumpswap_all_swaps.parquet` | `mint, ts_rel, tx_idx, slot, direction, base_token, sol, tok, new_price, signing_wallet, fee_payer, fee, pool_base_token_reserves_after, pool_quote_token_reserves_after, coin_creator, lp_fee, protocol_fee, coin_creator_fees` | AMM tape. `direction` is "B"/"S" **relative to `base_token`**. |

Data rules and gotchas the notebook authors call out:
- **Tape order is on-chain order** `(slot, tx_idx, intra-tx index)`. Never re-sort by timestamp, because many swaps share one second.
- **WSOL-base inversion:** when `base_token == So11111111111111111111111111111111111111112`, "B" means buying SOL, which is *selling* the memecoin. Flip the flag. Two of the three public pipelines skip this, so their buy-share and flow features are wrong on a subset of pools. This is a cheap fix that gives you an edge.
  ```python
  raw_b = d.direction.str.upper().str.startswith("B")
  d["is_buy"] = np.where(d.base_token.eq(WSOL), ~raw_b, raw_b)
  ```
- Take prices from `new_price`, which is derived from pool reserves, not from `sol/tok`.
- Qualifying universe for scored tokens: ≥ 60 SOL pool liquidity, ≥ 100 pre-snapshot trades, age ≤ 30 days, `mayhem_mode = 0` (removes about 52% of raw migrations). [verify] Apply the same filter wherever you build extra training rows.

### 1.4 Kaggle vs the league (this is the part that matters)
- **Kaggle is a sandbox that scores one day.** Public LB top scores (~60–80 SOL) come from one or two lucky high-tp hits on a single day. Do not chase them.
- **The official league runs through the Telegram bot `@pumpfun_competition_bot`.** You register (`/link`) a notebook. The bot re-runs it **from scratch** on each new day ("rotation") in a sealed sandbox: no network, about 4 cores and 31 GB RAM, Kaggle Python image `v170`, mounted rolling 30-day window, tight runtime (one secondary source says "within 3 minutes"). It then re-scores it. Standings come from these runs. [verify everything here]
- **Only versions uploaded to the bot before 1 Dec 00:00 UTC count.** The league therefore scores your *frozen* notebook on days **after** you can no longer touch it. It is a true out-of-sample forward test.

Strategic implications:
1. Optimise expected PnL per day over many future days under regime drift, not the public LB.
2. The notebook must retrain on whatever 30-day window it is given and must never crash. A crash on a scoring day costs you that day or worse. The fallback of all `tp = 0` scores exactly 0, which beats roughly 40% of the field.
3. Anything that needs internet, cached artefacts from your own runs, or hard-coded dates will break.

---

## 2. Domain knowledge: crypto mechanics you must understand

### 2.1 Solana in five facts
- **Slots** last about 400 ms. Several transactions per slot are ordered by `tx_idx`, which is why the data notes stress order.
- **Lamports:** 1 SOL = 1e9 lamports. pump.fun tokens use 6 decimals, so amounts are divided by 1e6.
- **Signer vs fee payer:** `signing_wallet` authorises the swap and `fee_payer` pays the fees. When they differ, a relayer, trading terminal or bot infrastructure is usually involved. Many signers sharing one fee payer means one entity is operating many wallets (a sybil cluster).
- **Priority fees and Jito bundles:** bots pay compute-unit prices and tips to be first. A *bundle* is an atomic group of transactions. At token creation, a bundle lets the developer and insiders buy in the same block as the create instruction (`bundle_size`, `bundled_buys`, `bundle_structure`). Heavy bundling means insiders hold the supply cheaply, which means dump risk.
- **Failed transactions** (`failed=1`) are mostly snipers losing races or hitting slippage limits. They measure contention and demand, and public notebooks rank them highly.

### 2.2 pump.fun lifecycle
1. **Create:** 1B supply token minted. Fields: `token_program` (legacy SPL vs **Token-2022**, which newer pump.fun creates use), metadata `url`, and dev buy.
2. **Bonding curve:** a constant-product curve on *virtual* reserves, roughly 30 virtual SOL against about 1.073B virtual tokens at launch. Price = virtual SOL / virtual tokens, and it rises deterministically with net buys. [verify current parameters] The curve "completes" after about 800M tokens are sold (on the order of 80–90 SOL raised).
3. **Graduation and migration:** the remaining tokens plus raised SOL seed a **PumpSwap** pool (pump.fun's own AMM, which replaced Raydium in 2025), minus a migration fee. `pfamm_migrations.csv` records this. Your clock starts at the migration time `mt`.
4. **AMM phase:** constant product `x·y = k`. A trade of size Δ against quote reserve R moves price by about `2Δ/R`. Fees are split into LP, protocol and **coin-creator** fees (creator revenue share). `pool_quote_token_reserves_after` gives you depth at every trade.

### 2.3 Who trades a fresh memecoin (and what their footprints look like)
| Actor | Footprint in the data | Effect on M |
|---|---|---|
| Dev / creator | creator wallet, `dev_balance`, dev buy at creation, dev selling post-migration | Dev retention, then a dev dump is the classic rug. Serial creators have track records. |
| Bundlers / insiders | same-block buys at creation, shared fee payers | Supply overhang, which pushes toward dump |
| Snipers | first-slot buys, high priority fees, failed txs | Fast flippers who sell into migration |
| Curve holders exiting | wallets that bought on the curve and sell into the pool in the first 60 s | Distribution pressure |
| **New** AMM buyers | wallets absent from the curve tape and buying post-migration | Genuine fresh demand, the bullish signal |
| Volume / wash bots | round-trip buy and sell by the same wallet, tiny uniform sizes | Fake activity that inflates counts |
| Cabals / KOL groups | the same wallet set appears early across many tokens | Can be bullish (coordinated pumps) or bearish (exit liquidity), so learn it from history |

Graduation is a **liquidity event**. Curve buyers finally have depth to exit into, and many do. The minority of tokens that keep running show *fresh-buyer inflow exceeding curve-holder exit*. Most informative features try to measure that balance.

---

## 3. Domain knowledge: the finance you need

### 3.1 Barrier hitting and volatility
For a driftless log-price with volatility σ over horizon T, the reflection principle gives
`P(max ≥ k) = 2·(1 − Φ(ln k / (σ√T)))`.
Hit probability depends on **volatility** as much as on direction. A token that is merely very volatile can fill a 3x target even if it ends near zero. Realised volatility and activity in the first 60 s are therefore direct predictors of M, separately from "is it good".

### 3.2 The empirical tail
Train base rates: P(M≥2) ≈ 30.4%, P(M≥3) ≈ 14.8%, P(M≥5) ≈ 6.07%, P(M≥10) ≈ 1.80%.
Between 3 and 10 these fit a **Pareto tail with α ≈ 1.75** (`ln(.148/.0607)/ln(5/3) ≈ ln(.0607/.018)/ln 2 ≈ 1.75`).
So `k·S(k) ∝ k^(−0.75)`. *Unconditionally*, the expected gross value of the take-profit falls as tp rises, which favours low tp. Conditionally, for the best tokens the tail can be fatter (α < 1), and then high tp is optimal. This is why **tp should be chosen per token from a predicted survival curve**, not fixed at 5.

### 3.3 Break-even precision
Let `L` be the average payoff of a miss (empirically about −0.8 at tp = 5, implied by the −0.531 buy-everything number). Break-even hit rate is `p* = −L / (tp − 1.3 − L)`:

| tp | 3 | 4 | 5 | 7 | 10 | 20 | 50 | 100 |
|---|---|---|---|---|---|---|---|---|
| p* (L = −0.8) | 32% | 23% | 17.8% | 12.3% | 8.4% | 4.1% | 1.6% | 0.8% |
| base rate | 14.8% | ~9% | 6.1% | ~3.3% | 1.8% | ~0.5% | — | — |
| lift needed | 2.2× | ~2.5× | 2.9× | ~3.7× | 4.7× | ~8× | | |

The required lift rises with tp, but so does the payoff per hit. Reported walk-forward results for public pipelines: top 1% of tokens by P(M≥5) gives about 25–31% precision, which is roughly +2 SOL/day. That is the bar to beat.

### 3.4 Expected value of a decision
```
EV(tp | x) = S(tp|x)·(tp − 1.3) + (1 − S(tp|x))·L(tp|x)
L(tp|x)    = E[max(F − 1.3, −1) | M < tp, x]
decision   : tp* = argmax_tp EV(tp|x);  buy iff EV(tp*|x) > margin, else tp = 0
```
- **Optimizer's curse:** you take the max over about 8 tp levels and over hundreds of tokens, so the selected EV is biased upward. The margin (about 0.3–0.6 SOL) is a shrinkage correction. Tune it by walk-forward and pick a flat region, not a peak.
- **Calibration matters more than ranking.** AUC tells you nothing about whether 0.22 really means 22%. The EV threshold and the tp choice both depend on absolute probabilities.

### 3.5 Microstructure toolbox
- **Order-flow imbalance:** (buy vol − sell vol)/total, computed per 15 s window.
- **Kyle's λ** (price impact per unit signed flow): `Σ Δln P · signed_vol / Σ signed_vol²`. High λ means a thin pool or one-sided flow.
- **Amihud illiquidity:** |return| / volume.
- **Concentration:** HHI or top-1 share of volume and of *holdings*. You can reconstruct holdings by netting `tok` per wallet across the curve and AMM tapes.
- **Path shape:** return, max drawdown, time-of-high vs time-of-low, path efficiency (|net move| / Σ|moves|), and the **last-print problem** (is the entry a local spike? compare entry with VWAP over 45–60 s and with the max over 0–60 s).

### 3.6 Tournament theory (how to *win*, not just profit)
The prize goes to rank 1 of about 300, scored on a sum of noisy daily PnLs. Maximising P(rank 1) ≠ maximising E[PnL]. When your edge is similar to rivals', **extra variance helps**: a few well-chosen high-tp (15–50x) bets on tokens whose predicted tail is genuinely fat. Variance only helps once mean PnL is positive and robust, so never accept negative-EV bets for it. A concrete rule: among tokens that already pass the EV margin, let tp* go high when the model supports it (do not cap at 5–7). Also keep a slightly *looser* margin than the pure-EV optimum. More trades means more shots at the tail, as long as the walk-forward mean stays positive. If the bot allows several registered notebooks [verify], register de-correlated variants (conservative EV vs tail-seeking).

---

## 4. Leakage and train/serve skew (the deciding factor)

The host's own starter text says: *"Build it without that lag and you have a leak that scores brilliantly here and dies in the league."*

1. **Label availability.** A token's outcome is known only at `mt_j + 3660`. Any history feature (wallet or creator reputation, base rates) for token *i* may use token *j* only if `mt_j + 3660 ≤ cutoff_i`.
2. **What is the cutoff at serve time?** In the league, the test day's labels are all unknown, and the training labels stop at the end of the 30-day window. So for **every** test token, reputation is effectively as-of start of the test day, minus whatever lag the window ends with. **Mirror this in training.** For a training token on day d, compute reputation as of `start_of_day(d) − LAG` (public code uses LAG = 7200 s), not as of `mt_i`. Computing it per token (`mt_i − 3600`) makes training features fresher than serving features. That is a train/serve skew the model will over-trust.
3. **No same-day cross-sectional selection.** "Buy the top 1% of today's test tokens" uses tokens that migrate *later* in the day. The host calls it "not a real-time rule". It also fails on days with unusual counts, which is why one public author's two-stage model lost −12 SOL over 16 days. Use **absolute EV thresholds**.
4. **Post-decision data.** Use only AMM rows with `ts_rel ≤ 60` (inclusive per the entry definition) and curve rows before migration. Check whether train-day tapes extend beyond 60 s. If they do, filter them out, or your training features differ from test features.
5. **Walk-forward with embargo.** Validate as the league does: for each day d, train only on the 30 days before d (with at least a 1 h gap), predict d, and repeat for the last 16–20 days. Never use random K-fold.
6. **Threshold and margin tuning is fitting too.** Tune them on validation days, and if possible confirm on a separate later block of days. Few hits means huge noise (see §7).

---

## 5. Feature engineering blueprint

Build features at the token level in four families. ★ marks the ones public notebooks report as strongest.

**A. Launch and creation** (`pumpfun_token_creation` + migrations)
- `age_s = mt − created_ts` (very fast fills have the *lowest* 5x rate; very slow ones lack interest), curve fill duration.
- Dev: `dev_balance`, dev buy size, whether the dev sells on the curve or in the first 60 s of AMM, and the dev's share of holdings at migration.
- Bundles: `bundle_size`, `bundled_buys(_count)`, opcode stats parsed from `bundle_structure`.
- Tooling: `token2022`, `direct_pf_invocation`, instruction and lookup-table counts, `gas_used`, `is_cashback_enabled`, presence and type of `url`.
- Name: length, uppercase share, name == symbol. These are weak, so let the model decide.
- Migration: `sol_amount`, `mint_amount`, fee, and migration price relative to final curve price ("migration pop").

**B. Bonding-curve tape (pre-migration)**
- Trade count, unique wallets, buy share, ★failed-tx count and ratio, priority-fee distribution.
- Holder structure at migration: number of holders, HHI, top-1/top-10 share, share held by the first 5/10/20 buyers and how much of their position they kept.
- Wash and round-trip fraction, unique signers per fee payer (sybil clusters).
- Activity in the final N minutes before migration (acceleration).

**C. AMM first 60 s** (with WSOL inversion)
- Per 15 s window: volume, buy share, trade count, unique wallets, return.
- ★Late-window buy volume (45–60 s), late/early volume ratio, ★whale buys (≥ 5 SOL), max single buy.
- ★**New-buyer inflow vs curve-holder exit:** SOL bought by wallets never seen on the curve, versus SOL sold by curve holders.
- Price path: return to 60 s, max drawdown, time of high, realised volatility, efficiency, entry/VWAP(45–60 s), entry/max(0–60 s).
- Kyle's λ, depth (quote reserves) growth, idle gaps, last-trade recency.

**D. History and reputation** (point-in-time per §4.2)
- ★Wallet reputation: for each early buyer of token *i*, their historical rate of being an early buyer in tokens that hit 3x/5x/10x. Aggregate mean, max and weight-by-SOL over the token's early buyers. Use **empirical-Bayes shrinkage**: `(hits + m·p0) / (n + m)`, with prior p0 = base rate and m ≈ 5–15.
- Creator reputation: past launches, past graduations, past hit rate, shrunk the same way.
- Co-buyer graph: overlap of today's early buyers with buyer sets of past winners and losers (detects cabals). Keep it to the top-K buyers per token for speed.
- Regime: trailing 1–3-day base rate of 5x, migrations in the last hour (computable in real time), hour of day (UTC).

Engineering: compute everything with vectorised pandas/polars `groupby` on the daily parquet files. Load only the needed columns. Cache nothing across runs (the sandbox is fresh each time).

---

## 6. Modelling and policy

### 6.1 Targets
Use a level grid `K = {3, 4, 5, 7, 10, 15, 25, 50}` (add 100 only if your tail is reliable).
- **Option A, survival curve (recommended core):** model `S(k|x) = P(M ≥ k)` as a *chain of conditional classifiers* (a discrete hazard): `P(M≥3)`, `P(M≥5 | M≥3)`, `P(M≥10 | M≥5)`, and so on. Multiplying them gives a monotone curve, and the high levels borrow strength from the low ones. Interpolate in log k for intermediate tp.
- **Miss payoff L(k|x):** a regression of `max(F−1.3, −1)` on rows with M < k. A pooled model with k as a feature is fine. Alternatively, use a constant per k from the training data as a first version.
- **Option B, direct payoff regression:** predict the vector `min(payoff(k, M, F), 20)` for all k at once (CatBoost `MultiRMSE`, as one public pipeline does). Clipping at about 20 controls variance. Blend the EV estimates from A and B.

### 6.2 Models
- LightGBM or CatBoost with moderate capacity (`num_leaves` 15–31, `min_child_samples` 40–100, strong subsampling), 3–5 seeds averaged.
- **Time-decay sample weights** (half-life about 10–20 days), because the memecoin meta rotates quickly.
- Train only on the 30-day window the sandbox will give you. Check that your validation does the same.
- **Calibrate** each level with isotonic or Platt on walk-forward out-of-fold predictions, then re-enforce monotonicity across k.

### 6.3 Policy
```python
ev = S[:, K] * (K - 1.3) + (1 - S[:, K]) * L[:, K]   # shape (n_tokens, n_levels)
j  = ev.argmax(1); best = ev.max(1)
tp = np.where(best > MARGIN, K[j], 0.0)
tp = np.where(tp > 0, np.clip(tp, 3.0, 100.0), 0.0)
```
- Expected activity: about 1–3% of tokens bought, around 3–15 trades per day.
- Add a **per-day cap** on trades (top N by EV among those passing the margin). It is a real-time-safe risk control if N is fixed, and it protects you on days when the model misfires broadly. Strictly, choosing the top N among all of today's tokens also uses later tokens, so prefer a margin and keep the cap only as a safety valve.
- Optionally shade tp **down by one level** when the predicted volatility is low (barrier logic in §3.1) and **up** when the hazard chain predicts a fat tail.

---

## 7. Validation and statistics

- Walk-forward over at least 16 days, each day trained on its own prior 30-day window with a gap of at least 1 h.
- Report total PnL, PnL per trade, trades per day, hit rate per level, number of positive days, worst day, and a **day-level bootstrap** 90% CI of mean daily PnL.
- Noise scale: at tp = 5 with p ≈ 0.25, one trade has an SD of about 2 SOL. With 5 trades/day over 16 days (80 trades), the SE of total PnL is about 18 SOL. **Differences smaller than roughly ±15 SOL between variants are noise.** Compare variants on proper scoring rules (log loss and Brier per level on out-of-fold predictions), which are far less noisy, and use PnL only to set the margin and confirm.
- Count your experiments. If you try 40 policies, the best walk-forward PnL is inflated (see the deflated Sharpe ratio, Bailey & López de Prado 2014). Prefer simple, flat-region choices.
- Sanity-check against the published references: an un-calibrated "buy 40/day" baseline lost about −7.8 SOL/week, and good top-1% P(M≥5) policies made about +2 SOL/day.

---

## 8. Sandbox-proof engineering (non-negotiable)

1. **Global try/except → all-zero fallback.** Always write `submission.csv` in `sample_submission` order, even if everything fails.
2. **Path discovery:** look in `/kaggle/input/competitions/memecoins-pump-or-dump`, `/kaggle/input/memecoins-pump-or-dump`, `./data`, and both tape layouts. Never hard-code dates. Derive the test day from `test.csv` (`mt` → UTC date).
3. **Schema tolerance:** rename `finalx` to `final_x`, treat missing optional columns as NaN features, deduplicate creation rows, and handle missing tape days (training rows without tapes still get creation features).
4. **Runtime budget:** time each stage. Stay far under the sandbox limit by reading only the needed columns, using `float32`, a few hundred trees, and no hyperparameter search at run time. Keep a time guard: if past X seconds, skip the ensemble extras and fall back to a single model.
5. **No network, no `pip install`.** Use only packages in the Kaggle `v170` image (lightgbm, catboost, xgboost, sklearn and polars should be present [verify]).
6. **Determinism:** fixed seeds and fixed thread counts (`n_jobs=4`).
7. **Validate the output:** check row count, finite values, `tp ∈ {0} ∪ [3, 100]`, and that the number of buys is within an expected range. If it buys more than about 10% of tokens, something is broken, so fall back to the conservative policy.
8. Register with the bot well before the freeze, and confirm that a bot run actually succeeded.

---

## 9. Six-day plan to the freeze

| Day | Goal | Done when |
|---|---|---|
| **Tue 24** | Read the official Overview/Eval/Rules/Data and answer the §11 checklist. Download data. Reproduce `payoff` and the −0.531 buy-everything number. Fork the host's minimal notebook and register it with the bot. | Baseline registered as a safety net. Walk-forward harness that mirrors the sandbox (30-day train, 1 h gap, one day predicted, 16+ days) is running. |
| **Wed 25** | Feature families A–C, WSOL inversion, a strict `ts_rel ≤ 60` filter. Single-level P(M≥5) LightGBM. | Walk-forward log loss and PnL beat the minimal baseline. |
| **Thu 26** | Point-in-time reputation (wallet, creator, graph) using the start-of-day cutoff. Time-decay weights. | Measured gain from family D with no train/serve skew. |
| **Fri 27** | Hazard-chain survival curve, L(k), calibration, EV policy, margin sweep. Optional MultiRMSE blend. | Flat-region margin chosen. Positive bootstrap CI or best available. |
| **Sat 28** | Sandbox hardening (§8), runtime profiling, tail and tournament posture (§3.6). Register the final candidate(s). | Bot run succeeds on its latest day. Kaggle run succeeds. |
| **Sun 29 – Mon 30** | Buffer only: bug fixes and re-registering. **No new features after Sunday.** Confirm the registered version before 23:59 UTC Nov 30 (bot cutoff 1 Dec 00:00 UTC). | Frozen. |

Priority order if time runs short: robust baseline registered → WSOL fix and tape features → calibrated EV threshold → reputation → multi-level tp → tail posture.

---

## 10. Concept checklist (to study, in order)

1. Triple-barrier labelling, purged/embargoed walk-forward CV, sample weighting by recency: López de Prado, *Advances in Financial Machine Learning*, ch. 3, 4, 7.
2. Probability calibration: isotonic and Platt, reliability diagrams, Brier score and log loss.
3. Decision theory under uncertainty: EV thresholds, the optimizer's / winner's curse, and shrinkage (empirical Bayes; Efron, *Large-Scale Inference*, ch. 1–2).
4. Barrier options and the reflection principle (any stochastic-calculus text, "first passage time of Brownian motion").
5. Heavy tails: Pareto/power-law fitting, why the mean of a heavy-tailed payoff is unstable.
6. Market microstructure: Kyle (1985) λ, Amihud illiquidity, order-flow imbalance. O'Hara, *Market Microstructure Theory* (selected chapters), is the classic reference.
7. AMM math: constant product, price impact, LP and protocol fees (Uniswap v2 whitepaper).
8. Solana execution: slots, transaction ordering, priority fees, Jito bundles and MEV, lamports and decimals, Token-2022, address lookup tables.
9. pump.fun specifics: bonding-curve parameters, graduation, PumpSwap migration, creator fees, Mayhem mode (pump.fun docs).
10. Memecoin manipulation research: *A Midsummer Meme's Dream* (arXiv 2507.01963), *MemeTrans* (arXiv 2602.13480, Solana high-risk launch detection), *The Memecoin Phenomenon* (arXiv 2512.11850).
11. Tournament and contest theory: why maximising P(win) rewards variance (Lazear & Rosen 1981; "Kelly vs winner-take-all").
12. Backtest overfitting: deflated Sharpe ratio, probability of backtest overfitting (Bailey & López de Prado).

---

## 11. Open questions to verify on the official pages (day 1)

- [ ] How is the league standing aggregated: sum of daily PnL? From which start date? For how many days after the freeze?
- [ ] Can you register more than one notebook? Which version counts?
- [ ] What are the exact sandbox time limit and hardware? Is it CPU only? Exactly which files are mounted, and do they include train-day tapes beyond 60 s?
- [ ] What is the exact trimming rule for M ("top max(1%, 1) prints")? Is the entry the last trade at or before 60 s, inclusive?
- [ ] Are same-day cross-sectional rules explicitly prohibited, or only discouraged?
- [ ] Is external data allowed? It is moot in the sandbox because there is no network, but check for pre-computed artefacts bundled with the notebook (e.g. a wallet-reputation table). If allowed, they would let you carry a much longer history than the 30-day window. **This could be a big edge, so check the rules.**
- [ ] Prize split and eligibility (Kaggle team vs bot account linkage).

---

Sources: [Kaggle competition page](https://www.kaggle.com/competitions/memecoins-pump-or-dump) (search snippets only), [AI-assisted start page](https://www.kaggle.com/competitions/memecoins-pump-or-dump/overview/ai-assisted-start) (search snippet), [satyam-257/Memecoing_pump_or_dump](https://github.com/satyam-257/Memecoing_pump_or_dump) (third-party repo with copies of host and public notebooks; numbers are self-reported), [arXiv 2507.01963](https://arxiv.org/abs/2507.01963v2), [arXiv 2602.13480](https://arxiv.org/html/2602.13480), [arXiv 2512.11850](https://arxiv.org/html/2512.11850v3).
