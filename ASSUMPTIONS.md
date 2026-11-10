STATE STAMP: SEED-v0.1 cdc788b1996bd923d48a034b28f58ee728ce10d82924724c722b2b7be7e719f5

# ASSUMPTIONS: swarm_r0.py v0.2.0, arm A

## Spec sources
* **Primary:** the SEED-v0.1 Round 1 builder brief. The worker-side attachment path was unavailable, so the parent agent relayed the original text; Parts 2–3 are in `source/BRIEF_RELAYED_BY_PARENT.md`.
* **Secondary:** arXiv:2611.03975v1 (Zakir, Pacheco, Reina, Dorigo, Strobel). Title and authors were checked against the arXiv API, and the PDF and text are kept in `source/`.
* **Not used as a source:** values from the author-adjacent repo (`rainazakir/size_regulation`, a different paper with no license) are not used as sourced defaults. Where brief and paper are silent and a number was still needed, it is written below as an ASSUMPTION.

## ASSUMPTION-n (same list as `ASSUMPTIONS` in swarm_r0.py; `python3 swarm_r0.py assumptions` prints it)

* ASSUMPTION-1 Arena: square, side sqrt(3.55) m; 20x20 tiles; 100 white tiles in two opposite corners (50 each, nearest-corner fill).
* ASSUMPTION-2 Kinematics: 0.10 m/s; straight runs ~Exp(mean 10 s) then uniform random heading; specular walls; no robot-robot collision, no occupancy cap.
* ASSUMPTION-3 Scheduled arrivals (Exp2/3): 2 robots per scheduled time (count unstated); each Byzantine w.p. P(added Byzantine).
* ASSUMPTION-4 Sealing: per connected component containing >=1 active sealer, at most one block when tick >= parent.ts+15; the in-turn (preferred, round-robin over active sealers by height) sealer seals with difficulty 2 if present, else the lowest-id present sealer with difficulty 1; Clique recents rule (paper: wait floor(N/2)+1 blocks) applied by default, --no-recents disables.
* ASSUMPTION-5 k = 2.0 (unstated in paper and brief); chosen before any run, never tuned; flag --k.
* ASSUMPTION-6 Smart Byzantine noise: U(-0.01, 0.01); if no on-chain mean yet, uses its own sensed estimate as the mean.
* ASSUMPTION-7 Robots attempt an estimate every 15 ticks when local balance allows and they have none in the open round.
* ASSUMPTION-8 Final 15 min: Byzantine draws are skipped; honest arrivals continue (--final-window-policy skip_all alternative).
* ASSUMPTION-9 Tokens: stake 40 per estimate, refunded when the round closes (arm A has no on-chain filter); issuance 20 tokens at block heights 0,2,4,8,...; a collection round closes when entries >= active/2 and active > 4. Values from the author-adjacent repo were reused here only because brief and paper are silent; they are ASSUMPTIONS, not sourced rules.
* ASSUMPTION-10 '>=50% of swarm proposed' uses active registered robots as the denominator (--propose-denominator eligible alternative).
* ASSUMPTION-11 An eligible robot with an empty suspect list still submits it (counts toward the 50% list rule); --no-empty-votes alternative.
* ASSUMPTION-12 Detector input: each robot's latest estimate over the last 2 closed rounds plus the open round, excluding self and removed robots.
* ASSUMPTION-13 Byzantine detector: flags robots with |e-mean| <= k*std (the inverse of the outlier test), i.e. near-mean robots, with no knowledge of who is honest.
* ASSUMPTION-14 Physical removal and influx happen at the tick the removal appears in the reference chain (best fork-choice head among active robots = 'robot with longest blockchain').
* ASSUMPTION-15 Network: each tick, every connected component floods: all members adopt the best head (higher total difficulty, tie -> lower hash) and merge tx pools.
* ASSUMPTION-16 R0 'comparable or higher TPR' operationalised as mean TPR(alpha10) >= mean TPR(alpha1) - 0.05; 'lower FPR' as mean FPR(alpha10) < mean FPR(alpha1); required in all 6 exp x byz pairs, each condition >= 10 engineering-validated runs. Fixed before the corrected matrix was run.

## Conflicts between brief and paper (the brief wins by default; alternatives are flags)
* **CONFLICT-1: scheduled arrivals.** The brief and the paper body say *at* 2, 4, 8, 16 and 32 min. The paper's Table 1 also says 'exponentially increasing *intervals*'. Read as intervals, arrivals land at 2, 6, 14, 30 and 62 min; the 62-min one falls after the 3600-tick run. Read as absolute times, the 32-min arrival comes 13 min before the final-15-min (45 min) no-Byzantine window, so the two rules never collide. Default: `absolute`. Alternative: `--schedule-mode cumulative`.
* **CONFLICT-2: collusion rule.** The brief says '3+ robots within ±0.07 of the mean', and so does the paper's parenthetical. The author-adjacent repo uses a pairwise tolerance of 0.007. Default: brief mean-band 0.07. Alternatives `--collusion-mode pairwise --collusion-tol 0.007 [--collusion-linkage window|single]` are labeled non-default interpretations.
* **CONFLICT-3: sealing rule.** The brief says '<= 1 block/15 s per connected component containing a sealer'. The paper states Clique's rule that a sealer waits floor(N/2)+1 blocks before sealing again. The two are compatible, and both apply by default. `--no-recents` drops the paper's rule, and `--seal-mode per_node` is the obsolete v0.1 per-node sealing model.
* **CONFLICT-4: units of α.** The brief and paper Methods say 'α valid estimates'. The paper's Exp 2 text says 'α removal rounds'. Default follows the brief (valid estimates = estimates counted in a closed round).
* **CONFLICT-5: what the final 15 min forbids.** The brief and paper forbid new Byzantines. Whether honest arrivals continue is unstated (ASSUMPTION-8).

## Open decisions: deliberately left undecided
OD1 (external committee vs per-conductor vs all), OD2 (exact destination vs open-ended authorization), OD3 (does removal touch conductor standing?), OD4 (restoration now vs next round) and OD5 (bounty in future arms) are not implemented and not decided. Arm A has no code path that depends on them.
