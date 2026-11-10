STATE STAMP: SEED-v0.1 cdc788b1996bd923d48a034b28f58ee728ce10d82924724c722b2b7be7e719f5

# COMPLIANCE: SEED-v0.1 brief (Parts 2–3 as relayed) vs swarm_r0.py v0.2.0

Legend: ✅ implemented as specified · ⚠️ implemented with an ASSUMPTION or a logged conflict · ❌ not implemented or not met

| # | Brief requirement | Status | Where / note |
|---|---|---|---|
| 1 | One Python file `swarm_r0.py`, stdlib + numpy, arm A only | ✅ | Single file; no B–D, NULL or amendments |
| 2 | L0: 3.55 m² square arena | ✅ | side = √3.55 m |
| 3 | L0: two clustered white corners totalling 25 % | ⚠️ | 20×20 tiles, 50 + 50 white tiles in opposite corners (ASSUMPTION-1) |
| 4 | L0: kinematic random walk, straight runs plus random turns | ⚠️ | speed and run length are ASSUMPTION-2 |
| 5 | L0: 13 cm disc comms | ✅ | unit-disk graph; connected components computed every tick |
| 6 | L0: 3600 ticks of 1 s | ✅ | `timesteps=3600` |
| 7 | L1: only base-swarm robots seal | ✅ | late joiners are non-sealers |
| 8 | L1: ≤ 1 block per 15 s per connected component containing a sealer | ✅ | `seal_mode=component`; checked in validation (no robot in two sealing components in one tick; ts ≥ parent + 15) |
| 9 | L1: hash chained | ✅ | header hash + txroot; I5 ledger hash chain |
| 10 | L1: fork choice, preferred sealer difficulty 2 else 1 | ✅ | round-robin preferred sealer; heaviest total difficulty wins; tie → lower hash (ASSUMPTION-15). Paper's Clique recents rule also on (CONFLICT-3) |
| 11 | L2: estimates averaged per collection round | ⚠️ | per-round arithmetic mean; round-close size is ASSUMPTION-9 |
| 12 | L2: propose when ≥ 50 % of the swarm proposed AND ≥ 5 proposals | ⚠️ | denominator = active robots (ASSUMPTION-10) |
| 13 | L2: eligibility = active AND (base OR valid estimates ≥ α) | ✅ | `Contract.eligible`; I3 checked |
| 14 | L2: each eligible robot submits a suspect list | ⚠️ | empty lists also submitted (ASSUMPTION-11) |
| 15 | L2: execute after 5 blocks; remove anyone on ≥ 50 % of lists with ≥ 5 votes | ✅ | `_execute_vote`; I2 recomputed independently in validation |
| 16 | L2: estimates stake tokens; a removed robot's tokens are split among its voters | ⚠️ | stake and issuance sizes are ASSUMPTION-9; integer split, remainder burned and logged |
| 17 | Detector: 3+ robots within ±0.07 of the mean = collusion; otherwise outliers beyond k·std | ✅ | default `collusion_mode=mean_band`, tol 0.07 (CHANGE-2) |
| 18 | Byzantine voters invert this and target honest robots nearest the mean | ⚠️ | flags \|e−mean\| ≤ k·std without knowing who is honest (ASSUMPTION-13); selftest checks for no truth or kind access |
| 19 | k: choose it, log it as an ASSUMPTION, expose a flag | ✅ | ASSUMPTION-5, k = 2.0, `--k` |
| 20 | Naive Byzantine always 0; smart = mean − 0.09 + small noise | ⚠️ | noise U(±0.01) (ASSUMPTION-6) |
| 21 | Part 3 table: sizes 12/12/12; initial Byzantine 4/0/0; added per removal 3/2/2; P(added Byzantine) .5/1/.5 | ✅ | `EXPERIMENTS` |
| 22 | Scheduled arrivals: none / at 2, 4, 8, 16, 32 min / same | ⚠️ | absolute times (CONFLICT-1); count of 2 is ASSUMPTION-3 |
| 23 | No new Byzantines in the final 15 min | ⚠️ | Byzantine draws skipped, honest continue (ASSUMPTION-8) |
| 24 | eval_interval_ticks = 500 | ✅ | plus the contract prompt when a vote opens |
| 25 | Default follows the supplied 0.07 mean rule; adjacent interpretations only as separate flags | ✅ | pairwise 0.007 only via `--collusion-mode pairwise` |
| 26 | Don't silently derive defaults from the unlicensed adjacent repo | ⚠️ | detector defaults now come from the brief. Token numbers that brief and paper leave unstated are written as ASSUMPTION-9 and openly note where they came from |
| 27 | Malicious strategies can't use truth to identify honest robots | ✅ | Observation has only own sensor and own chain view; source-level check (selftest `adversary_cannot_identify_honest_kind`) |
| 28 | L5: separate class the swarm never reads | ⚠️ | `L5Scorer` class reads ledger + truth JSON after the run and uses no swarm classes (selftest). Same file, so not a separate module. Python discipline only, not process isolation |
| 29 | Six metrics | ✅ | m1 mean abs error, m2 TPR, m3 FPR, m4 mean size, m5 mean Byzantine count, m6 removals |
| 30 | Byzantine share of ELIGIBLE > 0.5 at ANY tick | ✅ | `byz_share_eligible_gt_half_any_tick`, plus max, tick count and first tick |
| 31 | Scorer ticks capture must not miss between blocks | ✅ | `ref` event on every reference-head change; per-tick reconstruction of all 3600 ticks |
| 32 | Direct CLI `python swarm_r0.py --exp --alpha --byz --runs --seed --k` | ✅ | `main_direct`; `--out` and `--workers` optional |
| 33 | Metrics JSON + independent replayable ledger JSONL | ✅ | `metrics.json`; per-run `ledger.jsonl` (re-executable, byte-identical re-simulation) |
| 34 | I2: decision reproducible from votes + active constitution | ✅ | `verify_ledger` I2 check |
| 35 | I3: only eligible robots counted | ✅ | `verify_ledger` I3 check |
| 36 | I5: hash chain | ✅ | ledger line chain + block chain |
| 37 | I6: no truth reads, structurally | ⚠️ | source-token check over swarm classes plus no truth objects passed. Static and in-process only, not a security boundary |
| 38 | OD1–OD5 left undecided | ✅ | none implemented |
| 39 | Complete file, ASSUMPTION-n and CHANGE-n logs, exact commands, seeds, raw JSON | ✅ | `swarm_r0.py`, ASSUMPTIONS.md, CHANGELOG.md, outputs/COMMANDS.log, outputs/matrix/** |
| 40 | SEED §7 R0: α = 10 shows lower FPR and comparable-or-higher TPR | ❌ **R0 FAIL - paper direction NOT REPRODUCED** (only 2 of 6 exp×byz pairs match; see RESULTS.md) | evaluated by `r0-gate` on 12 conditions × 10 engineering-validated runs; "comparable" tolerance is ASSUMPTION-16; seeds/k not tuned |

## Not implemented or known gaps
* **The full original .txt is not in this bundle.** Only Parts 2–3 as relayed are included. Brief sections I didn't receive (for example the exact §7 wording, and any I1/I4 invariants) could not be checked. I1 and I4 were not relayed and are not claimed.
* **No ARGoS or Toychain fidelity.** There is no occupancy cap and no collisions, so swarms can exceed physical density.
* **Byzantines only misbehave at the application layer.** No invalid blocks and no equivocation.
