STATE STAMP: SEED-v0.1 cdc788b1996bd923d48a034b28f58ee728ce10d82924724c722b2b7be7e719f5

# RESULTS: swarm_r0.py v0.2.0, arm A (corrected runs only)

## R0 status: **R0 FAIL - paper direction NOT REPRODUCED**

SEED §7 (as relayed) requires that, against α = 1, α = 10 shows **lower mean FPR** and **comparable-or-higher mean TPR**. "Comparable" means ≥ α1 − 0.05; that tolerance is ASSUMPTION-16. The direction has to hold in every exp × byz pair, over ≥ 10 engineering-validated runs per condition.

That direction holds in **2 of 6 pairs** (exp2_naive and exp3_smart). It fails on FPR in exp1_naive, exp1_smart, exp2_smart and exp3_naive. Source: `outputs/matrix/r0_gate.json`, written by `python3 swarm_r0.py r0-gate --root outputs/matrix`, which exits 3 on FAIL.

**Consequence (SEED §7):** stop. Fix fidelity first. Do not make any downstream claims (arms B–D, amendments, OD1–OD5) on this harness. I did not tune anything to make the direction pass: seeds, k and tolerances were fixed before the runs.

## Protocol
- Code: `swarm_r0.py`, sha256 in `outputs/swarm_r0.py.sha256`. The code is frozen; the version used for the matrix is the version in this bundle.
- Matrix: exp {1,2,3} × byz {naive,smart} × α {1,10}. Each condition has 10 runs; run i uses seed 20261107 + i. The same seeds are used at both α values, so the runs pair up. k = 2 (ASSUMPTION-5). Exact commands are in `run_matrix.sh` and `outputs/COMMANDS.log`.
- All 120 runs passed engineering validation, with full byte-identical re-simulation (`runs_validated` 10/10 in every `metrics.json`).

## R0 gate (means over 10 runs per condition)
| pair | FPR α1 | FPR α10 | lower FPR α10? | TPR α1 | TPR α10 | TPR comparable/higher? | direction matches paper? |
|---|---|---|---|---|---|---|---|
| exp1_naive | 0.293 | 0.351 | NO | 0.362 | 0.388 | yes | NO |
| exp1_smart | 0.313 | 0.329 | NO | 0.300 | 0.352 | yes | NO |
| exp2_naive | 0.800 | 0.767 | yes | 0.737 | 0.823 | yes | yes |
| exp2_smart | 0.733 | 0.742 | NO | 0.811 | 0.963 | yes | NO |
| exp3_naive | 0.447 | 0.450 | NO | 0.149 | 0.212 | yes | NO |
| exp3_smart | 0.490 | 0.458 | yes | 0.200 | 0.414 | yes | yes |

Paired-by-seed sign tests (descriptive only, in `r0_gate.json`): no pair reaches p < 0.05 on FPR or TPR. Among the FPR differences, the α=10 FPR is higher in 8 of 10 seeds for exp1_naive (p = 0.11).

## Per-condition L5 metrics (mean ± sd over 10 validated runs)
| condition | valid runs | M1 MAE | M2 TPR | M3 FPR | M4 mean size | M5 mean byz | M6 removed | runs with byz>0.5 of eligible at any tick |
|---|---|---|---|---|---|---|---|---|
| exp1_naive_a1 | 10/10 | 0.121 ± 0.024 | 0.362 ± 0.288 | 0.293 ± 0.057 | 57.4 | 27.1 | 57.9 | 8/10 |
| exp1_naive_a10 | 10/10 | 0.124 ± 0.023 | 0.388 ± 0.314 | 0.351 ± 0.093 | 35.6 | 16.6 | 42.4 | 10/10 |
| exp1_smart_a1 | 10/10 | 0.098 ± 0.024 | 0.300 ± 0.074 | 0.313 ± 0.037 | 103.5 | 50.8 | 88.1 | 9/10 |
| exp1_smart_a10 | 10/10 | 0.093 ± 0.012 | 0.352 ± 0.224 | 0.329 ± 0.041 | 66.9 | 32.8 | 71.8 | 10/10 |
| exp2_naive_a1 | 10/10 | 0.182 ± 0.039 | 0.737 ± 0.398 | 0.800 ± 0.105 | 72.4 | 67.7 | 401.5 | 9/10 |
| exp2_naive_a10 | 10/10 | 0.187 ± 0.026 | 0.823 ± 0.279 | 0.767 ± 0.086 | 42.6 | 37.3 | 173.1 | 10/10 |
| exp2_smart_a1 | 10/10 | 0.161 ± 0.079 | 0.811 ± 0.382 | 0.733 ± 0.086 | 91.0 | 86.3 | 562.7 | 8/10 |
| exp2_smart_a10 | 10/10 | 0.190 ± 0.012 | 0.963 ± 0.026 | 0.742 ± 0.092 | 57.6 | 52.9 | 310.7 | 10/10 |
| exp3_naive_a1 | 10/10 | 0.098 ± 0.038 | 0.149 ± 0.194 | 0.447 ± 0.099 | 38.6 | 18.6 | 27.0 | 7/10 |
| exp3_naive_a10 | 10/10 | 0.107 ± 0.013 | 0.212 ± 0.308 | 0.450 ± 0.105 | 35.3 | 16.7 | 33.5 | 8/10 |
| exp3_smart_a1 | 10/10 | 0.073 ± 0.024 | 0.200 ± 0.179 | 0.490 ± 0.077 | 47.1 | 24.4 | 44.0 | 7/10 |
| exp3_smart_a10 | 10/10 | 0.074 ± 0.034 | 0.414 ± 0.329 | 0.458 ± 0.048 | 42.8 | 20.0 | 57.5 | 8/10 |

The last column counts runs where the Byzantine share of ELIGIBLE robots went above 0.5 at any tick. The L5 scorer reconstructs that per tick.

## Observations relevant to fixing fidelity (not fixed here, not tuned)
1. **The swarm grows without bound.** M4 is 35–104 and the final size reaches 392 in exp1. Each removal adds 3 or 2 robots, and v0.2.0 has no occupancy cap (see COMPLIANCE gaps). A paper-faithful arena probably limits this.
2. **The Byzantine share of eligible robots goes above 0.5 in 70–100% of runs.** Once that happens, the inverted Byzantine suspect lists decide removals, which drives FPR up in every condition, worst in exp2 (all-Byzantine arrivals). The paper's results imply honest control is mostly kept, so this points to a mismatch in the arrival, replacement or eligibility dynamics.
3. **The exp2 FPR of about 0.75–0.80 at both α values** suggests the α eligibility filter is not doing the work the paper attributes to it in this implementation. Possible reasons: the α units (CONFLICT-4), estimate staking and token flow, or collection-round averaging.
4. Seal/reorg behaviour: the n_reorgs mean is about 1300 per run in exp1_naive_a1, from component sealing (CONFLICT-3). Its effect on the vote timeline has not been checked against the paper.

These are hypotheses only. Each fix needs a CHANGE-n entry, a new frozen code hash, and a full matrix rerun before any R0 re-evaluation.

## Engineering validation (separate from R0; says nothing about paper fidelity)
- `outputs/selftest.json`: 35/35 checks, including tamper detection 5/5.
- `outputs/tamper_test_exp2_smart_a10_run00.json`: every tamper case was detected on a corrected matrix run.
- `outputs/xproc_replay_*.json`: 3 runs re-verified in a fresh process with `PYTHONHASHSEED=987 ... replay --full`; ok = true, resim identical.
- `outputs/single_run_check/`: running the `run` subcommand by itself for exp3/smart/α10/seed 20261116 reproduces the matrix run's `ledger.jsonl` and `truth.json` byte for byte (`cmp`).
- `outputs/post_annotate_replay*.json`: replay still passes after the R0 annotation step.

## Annotation step
`annotate_r0.py` copied the computed `R0_status` from `r0_gate.json` into every output JSON except `truth.json`, whose hash is bound in the ledger. It changed no measured value. Ledgers (.jsonl) are untouched.

## Obsolete material
v0.1.0 and its withdrawn "PASS" were replay integrity only, never R0. They are kept separately at `/workspace/swarm-r0-2026-11-07_OBSOLETE_v0.1.0/` and are **not** part of this bundle. I make no claims from them.

## Caveats
- The isolation between swarm, adversary and scorer is Python class discipline only. It is not security or process isolation.
- This is a stdlib + numpy kinematic approximation, not ARGoS. I1/I4 were not in the relayed text.
