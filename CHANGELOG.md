STATE STAMP: SEED-v0.1 cdc788b1996bd923d48a034b28f58ee728ce10d82924724c722b2b7be7e719f5

# CHANGE-n log: swarm_r0.py (local only; nothing published)

Times are America/Chicago (CST), 2026-11-07.

* **CHANGE-1 (v0.1.0, ~08:50–09:10).** First build, made while the worker could not reach the brief file. It used per-node Clique sealing, a pairwise 0.007 collusion tolerance taken from the author-adjacent repo, and 15-s snapshot scoring.
  - Its 12×10 matrix and its "R0 gate PASS" label are **obsolete and withdrawn**. That PASS only meant replay integrity. It was not the SEED §7 gate, and it conflicted with the paper-direction requirement.
  - The v0.1 bundle is outside this bundle at `/workspace/swarm-r0-2026-11-07_OBSOLETE_v0.1.0/`. No number from it is reused here.
* **CHANGE-2.** The collusion default now follows the brief: 3+ robots within ±0.07 of the on-chain mean, otherwise outliers beyond k·std. Pairwise 0.007 stays only as an optional, labeled non-default flag (CONFLICT-2).
* **CHANGE-3.** Sealing now follows brief L1. Each tick, every connected component that holds an active base sealer seals at most one block when tick >= parent.ts + 15. The preferred (in-turn) sealer is used if present (difficulty 2), otherwise the lowest-id sealer (difficulty 1). The paper's Clique recents rule is kept (CONFLICT-3). Per-node sealing is only available as `--seal-mode per_node`.
* **CHANGE-4.** k is now an explicit ASSUMPTION-5 (2.0, chosen before any v0.2 run) and is exposed as `--k`. It is no longer attributed to the adjacent repo.
* **CHANGE-5.** Added the direct CLI the brief requires: `python3 swarm_r0.py --exp E --alpha A --byz B --runs N --seed S --k K [--out DIR --workers W]`. Run i uses seed S+i. It writes DIR/metrics.json plus a ledger, truth, score and engineering-validation file per run. Subcommands remain.
* **CHANGE-6.** The L5 scorer now works per tick. A `ref` ledger event is written at every tick where the reference head changes, carrying the mean and the active and eligible sets, so every tick from 1 to 3600 is reconstructed exactly. It reports the six paper metrics (m1–m6) plus the eligible-Byzantine share: maximum, any tick > 0.5, number of ticks, and first tick.
* **CHANGE-7.** Engineering validation (formerly "replay") gained two invariant checks:
  - I2: every removal decision is recomputed from the logged votes on that fork plus the constitution (≥ 50 % of lists and ≥ 5 votes).
  - I3: every counted propose or vote came from an eligible robot.
  - It also checks component-sealing rules (one block per component per tick, preferred sealer chosen) and that `ref` events match re-executed state.
  - The selftest adds I6 structural checks: swarm and strategy source code contains no truth access, and adversaries cannot identify honest robots.
* **CHANGE-8.** Added the SEED §7 R0 gate (`r0-gate`). α = 10 must show lower mean FPR and comparable-or-higher mean TPR (≥ α1 − 0.05, ASSUMPTION-16) in all 6 exp × byz pairs, with ≥ 10 engineering-validated runs per condition. Otherwise the status is "R0 FAIL - paper direction NOT REPRODUCED". The tolerance and the gate were fixed before the corrected matrix ran.
* **CHANGE-9.** Token and issuance values that came from the adjacent repo (stake 40, UBI 20 at heights 0, 2, 4, 8, …, round close at active/2) are now labeled ASSUMPTION-9 rather than sourced.
* **CHANGE-10 (v0.2.0 frozen, sha256 in outputs/swarm_r0.py.sha256).** Selftest passes 35/35. The corrected 12×10 matrix was run once with seed 20261107 and k = 2. Nothing was tuned after seeing results.
