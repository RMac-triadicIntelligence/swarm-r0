STATE STAMP: SEED-v0.1 cdc788b1996bd923d48a034b28f58ee728ce10d82924724c722b2b7be7e719f5

# swarm_r0.py v0.2.0: arm A DAO open-swarm harness

## R0 status: **R0 FAIL — paper direction NOT REPRODUCED**

At α = 10 the run should show lower FPR and comparable-or-higher TPR than at α = 1, per SEED §7. That holds in only 2 of 6 exp × byz pairs; see `RESULTS.md` and `outputs/matrix/r0_gate.json`. Per §7: stop and fix fidelity; make no downstream claims. Engineering validation passed: 120/120 runs replay, 35/35 selftest checks, 5/5 tamper cases detected. That is **engineering validation only**. It is not R0 and not evidence of paper fidelity. Wherever the word `pass` appears in `selftest.json` (`all_pass`), it refers to unit checks only.

Published 2026-11-10 by Rusty Williams McMurray / Soulshine. Work date 2026-11-07. Licensed under Apache-2.0 (see `LICENSE` and `NOTICE`).

## Provenance

- Paper: arXiv:2611.03975v1. The PDF, txt and API metadata are in `source/`, with public author attribution as published.
- Brief: the worker path to the original SEED-v0.1 Round 1 builder brief was unavailable, so the parent relayed the original text. Parts 2–3 are verbatim in `source/BRIEF_RELAYED_BY_PARENT.md`.
- Author-adjacent repo: notes only; no code was copied (`source/author_adjacent_repo_excerpt/`). Defaults follow the brief (for example the ±0.07 mean-band collusion rule), not that repo.

## CLI (stdlib + numpy)

```
python3 swarm_r0.py --exp {1,2,3} --alpha {1,10} --byz {naive,smart} --runs N --seed S --k K [--workers W] [--out DIR]
python3 swarm_r0.py run|replay [--full]|score|tamper-test|r0-gate|selftest|assumptions ...
```

Each run directory holds `ledger.jsonl` (hash-chained, replayable), `truth.json` (read only by the L5 scorer; its hash is bound in the ledger footer), `meta.json`, `engineering_validation.json` and `score.json`. Each condition directory holds `metrics.json`.

This git tree is the **core package**: code, docs, matrix summaries, and engineering-validation receipts. The raw ledgers and the rest of the 120-run output tree (about 374 MiB uncompressed) are on the [v0.2.0 GitHub Release](https://github.com/RMac-triadicIntelligence/swarm-r0/releases/tag/v0.2.0) as `swarm-r0-v0.2.0-full.zip` (sha256 `cece5ef357b02fd578b7b9ebfe5a47a9165f8b714fdc0b979e88dd9696dd890d`). `SHA256SUMS.FULL-TREE` lists every file in that full tree. `SHA256SUMS` lists the files in this repository.

## Bundle map

| path | content |
|---|---|
| `swarm_r0.py` | the harness (sha256 in `outputs/swarm_r0.py.sha256`) |
| `run_cmd.sh`, `run_matrix.sh` | command recorder and the exact matrix commands |
| `annotate_r0.py` | copies the computed R0 status into the output JSONs; changes no measured value |
| `ASSUMPTIONS.md` | ASSUMPTION-1..16, CONFLICT-1..5, OD1–OD5 (left undecided) |
| `CHANGELOG.md` | CHANGE-1..10 (v0.1.0 is withdrawn and obsolete) |
| `COMPLIANCE.md` | checklist against the brief, with honest ❌/⚠️ gaps |
| `RESULTS.md` | corrected-run results and the R0 FAIL |
| `outputs/COMMANDS.log` | every command, with start/end times (America/Chicago) and exit code |
| `outputs/matrix/` | per-condition `metrics.json` and `r0_gate.json` (raw run ledgers are in the release zip) |
| `outputs/selftest.json`, `tamper_test_*.json`, `xproc_replay_*.json` | engineering validation |
| `SECRET_SCAN.md`, `SHA256SUMS`, `SHA256SUMS.FULL-TREE`, `ZIP_SHA256SUMS` | scan report and checksums |

## Caveats

- The isolation is Python class discipline only. It is **not** security or process isolation.
- This is a kinematic approximation, not ARGoS. There is no occupancy cap. I1/I4 were not in the relayed text.
- OD1–OD5 are not settled. Arms B–D, NULL and amendments are not implemented.
- Obsolete v0.1.0 material was withdrawn and is not in this repository. No claims rest on it.
