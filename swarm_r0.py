#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
swarm_r0.py -- Round 0 harness, ARM A ONLY (stdlib + numpy).
STATE STAMP: SEED-v0.1 cdc788b1996bd923d48a034b28f58ee728ce10d82924724c722b2b7be7e719f5

Spec sources: (1) the SEED-v0.1 Round 1 builder brief (Parts 2-3, relayed verbatim
by the parent agent after the worker-side attachment path was unavailable), which
is the PRIMARY spec and wins on conflict; (2) arXiv:2611.03975v1 (verified).
Where they disagree the brief's rule is the default and the conflict is logged
(ASSUMPTIONS.md / COMPLIANCE.md). Values from an author-adjacent repo are NOT
used as defaults.

Faithful-minimal, from-text re-implementation of the DAO access-control protocol
described in arXiv:2611.03975v1, "Self-governed access control in open robot swarms
using a blockchain-based DAO" (Zakir, Pacheco, Reina, Dorigo, Strobel).
The paper's own code (https://github.com/rainazakir/dao) was HTTP 404 when this was
written, so NOTHING here is the authors' code. ARGoS physics, Pi-puck kinematics and
Toychain networking are replaced by a simple 2-D kinematic model; see LIMITATIONS.md.

Isolation note: the "swarm" classes (Robot, Contract, chain) never receive ground
truth (who is Byzantine, the true tile fraction). The Environment keeps truth in a
private TruthVault and writes it only to truth.json; L5Scorer reads ledger+truth
after the run. This is *Python class/module discipline only* -- it is NOT security
or process isolation: any code in this process could read any object.

Arms B-D, NULL and amendments are NOT implemented. Open decisions OD1-OD5 are left
undecided (no code path depends on them). Unspecified rules are ASSUMPTION-n
entries (see ASSUMPTIONS list below and ASSUMPTIONS.md).
"""
import argparse
import copy
import hashlib
import json
import math
import multiprocessing as mp
import os
import shutil
import sys
import time

import numpy as np

STAMP = "SEED-v0.1 cdc788b1996bd923d48a034b28f58ee728ce10d82924724c722b2b7be7e719f5"
HARNESS = "swarm_r0.py arm=A version=0.2.0"
TICKET = 40          # ASSUMPTION-9 (stake size unstated in brief/paper)
UBI_VALUE = 20       # ASSUMPTION-9 (token issuance unstated in brief/paper)
UBI_SCHEDULE = [0, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384]

# ----------------------------------------------------------------------------
# canonical encoding / hashing
# ----------------------------------------------------------------------------

def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def sha(obj):
    if isinstance(obj, (bytes, bytearray)):
        return hashlib.sha256(obj).hexdigest()
    if isinstance(obj, str):
        return hashlib.sha256(obj.encode()).hexdigest()
    return hashlib.sha256(canon(obj).encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ----------------------------------------------------------------------------
# configuration (every value: source or "HARNESS DEFAULT (unspecified)")
# ----------------------------------------------------------------------------

EXPERIMENTS = {
    # Table 1 of the paper
    1: {"n_init": 12, "n_byz_init": 4, "influx_per_removal": 3, "p_byz_added": 0.5, "scheduled": False},
    2: {"n_init": 12, "n_byz_init": 0, "influx_per_removal": 2, "p_byz_added": 1.0, "scheduled": True},
    3: {"n_init": 12, "n_byz_init": 0, "influx_per_removal": 2, "p_byz_added": 0.5, "scheduled": True},
}

DEFAULTS = {
    "experiment": 1,
    "byz": "naive",                 # brief/paper: naive | smart
    "alpha": 10,                    # brief/paper: {1, 10}
    "seed": 1,
    "timesteps": 3600,              # brief L0: 3600 1-s ticks
    "arena_area_m2": 3.55,          # brief L0
    "tiles_per_side": 20,           # ASSUMPTION-1
    "white_fraction": 0.25,         # brief L0: two clustered white corners totalling 25 %
    "comm_range_m": 0.13,           # brief L0: 13 cm disc
    "speed_mps": 0.10,              # ASSUMPTION-2
    "straight_mean_s": 10.0,        # ASSUMPTION-2
    "block_period_s": 15,           # brief L1: <= 1 block / 15 s per component containing a sealer
    "seal_mode": "component",       # brief L1 (default) | per_node (obsolete v0.1 model, for comparison only)
    "clique_recents": True,         # paper (Clique wait floor(N/2)+1); ASSUMPTION-4 / CONFLICT-3
    "clique_limit_mode": "clique",  # ASSUMPTION-4
    "eval_interval": 500,           # brief Part3: eval_interval_ticks 500
    "estimate_interval": 15,        # ASSUMPTION-7
    "propose_fraction": 0.5,        # brief L2: >= 50 % of swarm proposed
    "propose_min": 5,               # brief L2: and >= 5 proposals
    "propose_denominator": "active",  # ASSUMPTION-10 ("swarm" = active registered robots)
    "voting_period_blocks": 5,      # brief L2: execute after 5 blocks
    "remove_list_fraction": 0.5,    # brief L2: >= 50 % of lists
    "remove_min_votes": 5,          # brief L2: with >= 5 votes
    "submit_empty_votes": True,     # ASSUMPTION-11
    "recent_rounds": 2,             # ASSUMPTION-12
    "history_rounds": 5,            # ASSUMPTION-12
    "collusion_mode": "mean_band",  # brief detector (default): 3+ robots within +/-0.07 of the mean
    "collusion_tol": 0.07,          # brief detector: 0.07
    "collusion_linkage": "window",  # only used by the optional non-default collusion_mode=pairwise
    "collusion_min": 3,             # brief: 3+
    "k_std": 2.0,                   # ASSUMPTION-5: k unstated; chosen a priori = 2, flag --k
    "smart_offset": 0.09,           # brief: mean - 0.09
    "smart_noise": 0.01,            # ASSUMPTION-6: "small noise" = U(-0.01, 0.01)
    "naive_value": 0.0,             # brief: always 0
    "schedule_mode": "absolute",    # brief Part3: at 2,4,8,16,32 min (absolute); CONFLICT-1
    "scheduled_minutes": [2, 4, 8, 16, 32],
    "scheduled_count": 2,           # ASSUMPTION-3 (brief: count unspecified)
    "final_window_s": 900,          # brief: no new Byzantines in the final 15 min
    "final_window_policy": "skip_byzantine",  # ASSUMPTION-8
    "mean_mode": "round",           # brief L2: estimates averaged per collection round
    "snapshot_every": 15,           # coarse ledger snapshots; per-tick scoring uses 'ref' events
}

ASSUMPTIONS = [
    "ASSUMPTION-1 Arena: square, side sqrt(3.55) m; 20x20 tiles; 100 white tiles in two opposite corners (50 each, nearest-corner fill).",
    "ASSUMPTION-2 Kinematics: 0.10 m/s; straight runs ~Exp(mean 10 s) then uniform random heading; specular walls; no robot-robot collision, no occupancy cap.",
    "ASSUMPTION-3 Scheduled arrivals (Exp2/3): 2 robots per scheduled time (count unstated); each Byzantine w.p. P(added Byzantine).",
    "ASSUMPTION-4 Sealing: per connected component containing >=1 active sealer, at most one block when tick >= parent.ts+15; the in-turn (preferred, round-robin over active sealers by height) sealer seals with difficulty 2 if present, else the lowest-id present sealer with difficulty 1; Clique recents rule (paper: wait floor(N/2)+1 blocks) applied by default, --no-recents disables.",
    "ASSUMPTION-5 k = 2.0 (unstated in paper and brief); chosen before any run, never tuned; flag --k.",
    "ASSUMPTION-6 Smart Byzantine noise: U(-0.01, 0.01); if no on-chain mean yet, uses its own sensed estimate as the mean.",
    "ASSUMPTION-7 Robots attempt an estimate every 15 ticks when local balance allows and they have none in the open round.",
    "ASSUMPTION-8 Final 15 min: Byzantine draws are skipped; honest arrivals continue (--final-window-policy skip_all alternative).",
    "ASSUMPTION-9 Tokens: stake 40 per estimate, refunded when the round closes (arm A has no on-chain filter); issuance 20 tokens at block heights 0,2,4,8,...; a collection round closes when entries >= active/2 and active > 4. Values from the author-adjacent repo were reused here only because brief and paper are silent; they are ASSUMPTIONS, not sourced rules.",
    "ASSUMPTION-10 '>=50% of swarm proposed' uses active registered robots as the denominator (--propose-denominator eligible alternative).",
    "ASSUMPTION-11 An eligible robot with an empty suspect list still submits it (counts toward the 50% list rule); --no-empty-votes alternative.",
    "ASSUMPTION-12 Detector input: each robot's latest estimate over the last 2 closed rounds plus the open round, excluding self and removed robots.",
    "ASSUMPTION-13 Byzantine detector: flags robots with |e-mean| <= k*std (the inverse of the outlier test), i.e. near-mean robots, with no knowledge of who is honest.",
    "ASSUMPTION-14 Physical removal and influx happen at the tick the removal appears in the reference chain (best fork-choice head among active robots = 'robot with longest blockchain').",
    "ASSUMPTION-15 Network: each tick, every connected component floods: all members adopt the best head (higher total difficulty, tie -> lower hash) and merge tx pools.",
    "ASSUMPTION-16 R0 'comparable or higher TPR' operationalised as mean TPR(alpha10) >= mean TPR(alpha1) - 0.05; 'lower FPR' as mean FPR(alpha10) < mean FPR(alpha1); required in all 6 exp x byz pairs, each condition >= 10 engineering-validated runs. Fixed before the corrected matrix was run.",
]


def make_config(**kw):
    cfg = copy.deepcopy(DEFAULTS)
    for k, v in kw.items():
        if v is None:
            continue
        if k not in cfg:
            raise KeyError("unknown config key %s" % k)
        cfg[k] = v
    cfg["exp"] = copy.deepcopy(EXPERIMENTS[int(cfg["experiment"])])
    cfg["stamp"] = STAMP
    cfg["harness"] = HARNESS
    cfg["arm"] = "A"
    return cfg


# ----------------------------------------------------------------------------
# hash-chained JSONL ledger
# ----------------------------------------------------------------------------

class Ledger:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "w", encoding="ascii")
        self.prev = "0" * 64
        self.seq = 0

    def write(self, obj):
        obj = dict(obj)
        obj["seq"] = self.seq
        obj["prev"] = self.prev
        h = sha(obj)
        obj["h"] = h
        self.f.write(canon(obj) + "\n")
        self.prev = h
        self.seq += 1

    def close(self):
        self.f.close()


# ----------------------------------------------------------------------------
# chain primitives
# ----------------------------------------------------------------------------

def make_tx(kind, sender, t, nonce, data):
    tx = {"type": kind, "sender": int(sender), "t": int(t), "nonce": int(nonce), "data": data}
    tx["id"] = sha({k: tx[k] for k in ("type", "sender", "t", "nonce", "data")})
    return tx


def tx_id_ok(tx):
    return tx["id"] == sha({k: tx[k] for k in ("type", "sender", "t", "nonce", "data")})


def txroot(txs):
    return sha("".join(tx["id"] for tx in txs))


def block_header(b):
    return {"height": b["height"], "parent": b["parent"], "sealer": b["sealer"], "ts": b["ts"],
            "diff": b["diff"], "txroot": b["txroot"]}


def tx_sort_key(tx):
    return (tx["t"], tx["sender"], tx["nonce"], tx["id"])


# ----------------------------------------------------------------------------
# CONTRACT (deterministic state machine; pure function of the chain)
# ----------------------------------------------------------------------------

class Contract:
    """On-chain rules. apply_block(parent_state, block) -> (state, receipt).
    Never reads ground truth."""

    def __init__(self, cfg):
        self.alpha = int(cfg["alpha"])
        self.vp = int(cfg["voting_period_blocks"])
        self.pf = float(cfg["propose_fraction"])
        self.pmin = int(cfg["propose_min"])
        self.pden = cfg["propose_denominator"]
        self.rlf = float(cfg["remove_list_fraction"])
        self.rmin = int(cfg["remove_min_votes"])
        self.hist_n = int(cfg["history_rounds"])
        self.mean_mode = cfg["mean_mode"]

    # --- state helpers
    @staticmethod
    def genesis_state(base_ids, sealer_ids):
        return {"h": 0,
                "reg": {i: [True, i in sealer_ids] for i in base_ids},
                "removed": {}, "bal": {i: 0 for i in base_ids}, "ubi": {i: 0 for i in base_ids},
                "valid": {i: 0 for i in base_ids}, "round": 0, "cur": [], "hist": [],
                "mean": None, "cum": [0.0, 0], "props": [], "vote": None, "vseq": 0}

    @staticmethod
    def copy_state(s):
        v = s["vote"]
        return {"h": s["h"], "reg": dict(s["reg"]), "removed": dict(s["removed"]), "bal": dict(s["bal"]),
                "ubi": dict(s["ubi"]), "valid": dict(s["valid"]), "round": s["round"], "cur": list(s["cur"]),
                "hist": list(s["hist"]), "mean": s["mean"], "cum": list(s["cum"]), "props": list(s["props"]),
                "vote": None if v is None else {"id": v["id"], "open": v["open"], "lists": dict(v["lists"])},
                "vseq": s["vseq"]}

    @staticmethod
    def state_hash(s):
        return sha(s)

    @staticmethod
    def active(s, rid):
        return rid in s["reg"] and rid not in s["removed"]

    @staticmethod
    def n_active(s):
        return len(s["reg"]) - len(s["removed"])

    def eligible(self, s, rid):
        if not self.active(s, rid):
            return False
        return bool(s["reg"][rid][0]) or s["valid"].get(rid, 0) >= self.alpha

    def n_eligible(self, s):
        return sum(1 for r in s["reg"] if self.eligible(s, r))

    @staticmethod
    def active_sealers(s):
        return sorted(r for r, v in s["reg"].items() if v[1] and r not in s["removed"])

    @staticmethod
    def ubi_due(s, rid, height):
        last = s["ubi"].get(rid, 0)
        for i, hb in enumerate(UBI_SCHEDULE):
            if height < hb:
                return max(0, (i - last)) * UBI_VALUE, i
        return 0, last

    # --- block application
    def apply_block(self, parent_state, block):
        s = self.copy_state(parent_state)
        s["h"] = block["height"]
        ev = []
        bal_before = dict(s["bal"])
        for tx in block["txs"]:
            self._apply_tx(s, tx, block["height"], ev)
        # end-of-block: execute vote if voting period elapsed
        v = s["vote"]
        if v is not None and block["height"] >= v["open"] + self.vp:
            self._execute_vote(s, block["height"], ev)
        diff = {}
        for rid in sorted(set(bal_before) | set(s["bal"])):
            a, b = bal_before.get(rid, 0), s["bal"].get(rid, 0)
            if a != b:
                diff[str(rid)] = [a, b]
        receipt = {"events": ev, "bal_diff": diff, "state_hash": self.state_hash(s)}
        return s, receipt

    def _apply_tx(self, s, tx, height, ev):
        kind, snd = tx["type"], tx["sender"]
        if kind == "register":
            if snd in s["reg"]:
                ev.append(["reject", tx["id"][:16], "already_registered"])
                return
            s["reg"][snd] = [False, False]
            s["bal"][snd] = 0
            s["ubi"][snd] = 0
            s["valid"][snd] = 0
            ev.append(["register", snd])
            return
        if not self.active(s, snd):
            ev.append(["reject", tx["id"][:16], "not_active"])
            return
        due, idx = self.ubi_due(s, snd, height)
        if due > 0:
            s["bal"][snd] += due
            s["ubi"][snd] = idx
            ev.append(["ubi", snd, due])
        if kind == "estimate":
            if s["bal"][snd] < TICKET:
                ev.append(["reject", tx["id"][:16], "balance"])
                return
            if any(e[0] == snd for e in s["cur"]):
                ev.append(["reject", tx["id"][:16], "dup_round"])
                return
            est = float(tx["data"]["est"])
            if not (0.0 <= est <= 1.0) or round(est, 3) != est:
                ev.append(["reject", tx["id"][:16], "bad_estimate"])
                return
            s["bal"][snd] -= TICKET
            s["cur"].append([snd, est])
            ev.append(["estimate", snd, est, s["round"]])
            act = self.n_active(s)
            if len(s["cur"]) >= act / 2.0 and act > 4:   # author-adjacent Block.py:376
                self._close_round(s, ev)
        elif kind == "propose":
            if s["vote"] is not None:
                ev.append(["reject", tx["id"][:16], "vote_open"])
                return
            if not self.eligible(s, snd):
                ev.append(["reject", tx["id"][:16], "not_eligible"])
                return
            if snd not in s["props"]:
                s["props"] = sorted(s["props"] + [snd])
                ev.append(["propose", snd, len(s["props"])])
            den = self.n_active(s) if self.pden == "active" else self.n_eligible(s)
            if len(s["props"]) >= self.pf * den and len(s["props"]) >= self.pmin:
                s["vseq"] += 1
                s["vote"] = {"id": s["vseq"], "open": height, "lists": {}}
                ev.append(["vote_open", s["vseq"], height, list(s["props"]), den])
                s["props"] = []
        elif kind == "vote":
            v = s["vote"]
            if v is None or int(tx["data"]["vote_id"]) != v["id"] or height > v["open"] + self.vp:
                ev.append(["reject", tx["id"][:16], "no_such_vote"])
                return
            if not self.eligible(s, snd):
                ev.append(["reject", tx["id"][:16], "not_eligible"])
                return
            if snd in v["lists"]:
                ev.append(["reject", tx["id"][:16], "dup_vote"])
                return
            lst = sorted(set(int(x) for x in tx["data"]["list"] if int(x) != snd and self.active(s, int(x))))
            v["lists"][snd] = lst
            ev.append(["vote", snd, v["id"], lst])
        else:
            ev.append(["reject", tx["id"][:16], "unknown_type"])

    def _close_round(self, s, ev):
        entries = [e for e in s["cur"] if e[0] not in s["removed"]]
        if self.mean_mode == "cumulative":
            tot, n = s["cum"]
            tot += sum(e[1] for e in entries)
            n += len(entries)
            s["cum"] = [tot, n]
            mean = tot / n if n else None
        else:
            mean = (sum(e[1] for e in entries) / len(entries)) if entries else s["mean"]
        for rid, _ in entries:
            s["bal"][rid] += TICKET           # refund stake (no on-chain outlier filter in arm A)
            s["valid"][rid] = s["valid"].get(rid, 0) + 1
        s["hist"] = (s["hist"] + [{"r": s["round"], "entries": entries, "mean": mean}])[-self.hist_n:]
        s["mean"] = mean
        ev.append(["round_close", s["round"], len(entries), mean])
        s["round"] += 1
        s["cur"] = []

    def _execute_vote(self, s, height, ev):
        v = s["vote"]
        n_lists = len(v["lists"])
        counts = {}
        for voter in sorted(v["lists"]):
            for t in v["lists"][voter]:
                counts.setdefault(t, []).append(voter)
        removed = sorted(t for t, vs in counts.items()
                         if self.active(s, t) and len(vs) >= self.rlf * n_lists and len(vs) >= self.rmin)
        ev.append(["vote_exec", v["id"], n_lists, {str(t): len(vs) for t, vs in sorted(counts.items())}, removed])
        for t in removed:
            s["removed"][t] = height
        for t in removed:
            voters = [vr for vr in sorted(counts[t]) if self.active(s, vr)]
            amount = s["bal"].get(t, 0)
            s["bal"][t] = 0
            share = amount // len(voters) if voters else 0
            for vr in voters:
                s["bal"][vr] += share
            burned = amount - share * len(voters)
            s["cur"] = [e for e in s["cur"] if e[0] != t]
            ev.append(["remove", t, height, voters, amount, share, burned])
        s["vote"] = None


# ----------------------------------------------------------------------------
# Block store + PoA (Clique-like) rules
# ----------------------------------------------------------------------------

class Chain:
    """Content-addressed block store used as a cache by all nodes (blocks are
    immutable; each node holds only its own head pointer + height index). State
    per block is a deterministic function of the chain, memoised by block hash.
    Rollback/replay = moving a head pointer; state is never mutated in place."""

    def __init__(self, cfg, contract, genesis, genesis_state):
        self.cfg = cfg
        self.contract = contract
        self.blocks = {genesis["hash"]: genesis}
        self.state = {genesis["hash"]: genesis_state}
        self.receipt = {genesis["hash"]: {"events": [], "bal_diff": {}, "state_hash": Contract.state_hash(genesis_state)}}
        self.tx_blocks = {}
        self.genesis = genesis
        self.period = int(cfg["block_period_s"])
        self.limit_mode = cfg["clique_limit_mode"]
        self.seal_mode = cfg.get("seal_mode", "component")
        self.recents = bool(cfg.get("clique_recents", True))

    def limit(self, n):
        return n // 2 + 1 if self.limit_mode == "clique" else n // 2 + 2

    def can_seal(self, parent, sealer, t):
        """Returns (ok, diff, earliest_t) according to Clique-like rules."""
        ps = self.state[parent["hash"]]
        sealers = Contract.active_sealers(ps)
        n = len(sealers)
        if n == 0 or sealer not in sealers:
            return False, 0, None
        number = parent["height"] + 1
        lim = self.limit(n)
        # recents: sealer may not have signed a block with height s where s > number - lim
        if self.recents:
            b = parent
            while b["height"] >= 1 and b["height"] > number - lim:
                if b["sealer"] == sealer:
                    return False, 0, None
                b = self.blocks[b["parent"]]
        inturn = sealers[number % n] == sealer
        diff = 2 if inturn else 1
        earliest = parent["ts"] + self.period
        if not inturn and self.seal_mode == "per_node":
            earliest += 1 + int(sha("%d|%s" % (sealer, parent["hash"]))[:8], 16) % lim
        return t >= earliest, diff, earliest

    def component_sealer(self, parent, present, t):
        """brief L1: choose at most one sealer for a component (preferred/in-turn first)."""
        cands = []
        for r in sorted(present):
            ok, diff, _ = self.can_seal(parent, r, t)
            if ok:
                cands.append((-diff, r))
        if not cands:
            return None
        return min(cands)[1]

    def seal(self, parent, sealer, t, txs):
        ok, diff, _ = self.can_seal(parent, sealer, t)
        assert ok
        txs = sorted(txs, key=tx_sort_key)
        b = {"height": parent["height"] + 1, "parent": parent["hash"], "sealer": sealer, "ts": int(t),
             "diff": diff, "txroot": txroot(txs)}
        b["hash"] = sha(block_header(b))
        b["td"] = parent["td"] + diff
        b["txs"] = txs
        return self.add_block(b)

    def add_block(self, b):
        if b["hash"] in self.blocks:
            return self.blocks[b["hash"]], False
        st, rc = self.contract.apply_block(self.state[b["parent"]], b)
        self.blocks[b["hash"]] = b
        self.state[b["hash"]] = st
        self.receipt[b["hash"]] = rc
        for tx in b["txs"]:
            self.tx_blocks.setdefault(tx["id"], []).append((b["height"], b["hash"]))
        return b, True

    @staticmethod
    def better(a, b):
        """fork choice: higher total difficulty, tie -> lexicographically lower hash"""
        return a["td"] > b["td"] or (a["td"] == b["td"] and a["hash"] < b["hash"])


# ----------------------------------------------------------------------------
# Strategies (injected callbacks; see only an Observation -- no truth access)
# ----------------------------------------------------------------------------

class Observation:
    """Read-only view handed to strategies: own id, own sensor counts, own local
    chain view (contract mean, recent estimates of others), own rng. No truth."""

    def __init__(self, rid, white, black, state, recent_rounds, rng):
        self.id = rid
        self.white = white
        self.black = black
        self.mean = state["mean"]
        self.removed = frozenset(state["removed"])
        latest = {}
        for rnd in state["hist"][-recent_rounds:]:
            for r, e in rnd["entries"]:
                latest[r] = e
        for r, e in state["cur"]:
            latest[r] = e
        self.recent = {r: e for r, e in latest.items() if r != rid and r not in self.removed}
        self.rng = rng

    def sensed(self):
        return (0.5 + self.white) / (self.white + self.black + 1.0)


def _clusters_window(ids, vals, tol, cmin):
    """complete-linkage reading of "within a tolerance of each other": every sorted
    window whose max-min <= tol and that holds >= cmin robots is flagged (union)."""
    order = np.argsort(vals, kind="stable")
    sv = vals[order]
    flagged = set()
    j = 0
    for i in range(len(sv)):
        if j < i:
            j = i
        while j + 1 < len(sv) and sv[j + 1] - sv[i] <= tol + 1e-12:
            j += 1
        if j - i + 1 >= cmin:
            flagged.update(ids[order[k]] for k in range(i, j + 1))
    return sorted(flagged)


def _clusters_pairwise(ids, vals, tol):
    """single-linkage groups on sorted values: consecutive gaps <= tol"""
    order = np.argsort(vals, kind="stable")
    groups, cur = [], [order[0]]
    for a, b in zip(order[:-1], order[1:]):
        if vals[b] - vals[a] <= tol + 1e-12:
            cur.append(b)
        else:
            groups.append(cur)
            cur = [b]
    groups.append(cur)
    return [[ids[i] for i in g] for g in groups]


class HonestStrategy:
    name = "honest"

    def __init__(self, cfg):
        self.mode = cfg["collusion_mode"]
        self.linkage = cfg["collusion_linkage"]
        self.tol = float(cfg["collusion_tol"])
        self.cmin = int(cfg["collusion_min"])
        self.k = float(cfg["k_std"])

    def estimate(self, obs):
        return obs.sensed()

    def detect(self, obs):
        if len(obs.recent) < 3:
            return []
        ids = sorted(obs.recent)
        vals = np.array([obs.recent[i] for i in ids], dtype=float)
        mean = obs.mean if obs.mean is not None else float(vals.mean())
        flagged = []
        if self.mode == "pairwise" and self.linkage == "window":
            flagged = _clusters_window(ids, vals, self.tol, self.cmin)
        elif self.mode == "pairwise":
            for g in _clusters_pairwise(ids, vals, self.tol):
                if len(g) >= self.cmin:
                    flagged.extend(g)
        elif self.mode == "mean_band":
            band = [i for i, v in zip(ids, vals) if abs(v - mean) <= self.tol]
            if len(band) >= self.cmin:
                flagged = band
        if flagged:
            return sorted(flagged)
        thr = self.k * float(vals.std())
        return [i for i, v in zip(ids, vals) if abs(v - mean) > thr]


class ByzantineBase:
    """Adversary detector: inverted adaptive threshold (flags robots whose
    estimates sit within k*std of the mean, i.e. closest to the mean)."""

    def __init__(self, cfg):
        self.k = float(cfg["k_std"])

    def detect(self, obs):
        if len(obs.recent) < 3:
            return []
        ids = sorted(obs.recent)
        vals = np.array([obs.recent[i] for i in ids], dtype=float)
        mean = obs.mean if obs.mean is not None else float(vals.mean())
        thr = self.k * float(vals.std())
        return [i for i, v in zip(ids, vals) if abs(v - mean) <= thr]


class NaiveByzantine(ByzantineBase):
    name = "naive"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.value = float(cfg["naive_value"])

    def estimate(self, obs):
        return self.value


class SmartByzantine(ByzantineBase):
    name = "smart"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.off = float(cfg["smart_offset"])
        self.noise = float(cfg["smart_noise"])

    def estimate(self, obs):
        m = obs.mean if obs.mean is not None else obs.sensed()
        return min(1.0, max(0.0, m - self.off + float(obs.rng.uniform(-self.noise, self.noise))))


# ----------------------------------------------------------------------------
# Robot (swarm node). Holds NO truth label: only an opaque strategy callback.
# ----------------------------------------------------------------------------

class Robot:
    def __init__(self, rid, strategy, chain, contract, cfg, rng, base, sealer, t0):
        self.id = rid
        self._strategy = strategy
        self.chain = chain
        self.contract = contract
        self.cfg = cfg
        self.rng = rng
        self.base = base
        self.sealer = sealer
        self.head = chain.genesis
        self.index = {0: chain.genesis["hash"]}
        self.pool = {}
        self.white = 0
        self.black = 0
        self.nonce = 0
        self.est_round_sent = -1
        self.proposed_at = -1
        self.voted = set()
        self.registered_sent = base
        self.t0 = t0

    def state(self):
        return self.chain.state[self.head["hash"]]

    def included(self, txid):
        for h, bh in self.chain.tx_blocks.get(txid, ()):
            if self.index.get(h) == bh:
                return True
        return False

    def set_head(self, new):
        """Switch head (rollback to common ancestor + replay new branch).
        Returns reorg info if the old head is not an ancestor of the new one."""
        old = self.head
        if new["hash"] == old["hash"]:
            return None
        blocks = self.chain.blocks
        new_branch = []
        b = new
        while self.index.get(b["height"]) != b["hash"]:
            new_branch.append(b)
            b = blocks[b["parent"]]
        anc = b
        old_branch = []
        o = old
        while o["hash"] != anc["hash"]:
            old_branch.append(o)
            o = blocks[o["parent"]]
        for h in [h for h in self.index if h > anc["height"]]:
            del self.index[h]
        for nb in new_branch:
            self.index[nb["height"]] = nb["hash"]
        self.head = new
        for ob in old_branch:
            for tx in ob["txs"]:
                if not self.included(tx["id"]):
                    self.pool[tx["id"]] = tx
        for nb in new_branch:
            for tx in nb["txs"]:
                self.pool.pop(tx["id"], None)
        if old_branch:
            return {"robot": self.id, "old": old["hash"], "new": new["hash"], "ancestor": anc["hash"],
                    "anc_h": anc["height"], "depth_old": len(old_branch), "depth_new": len(new_branch)}
        return None

    def _tx(self, kind, t, data):
        tx = make_tx(kind, self.id, t, self.nonce, data)
        self.nonce += 1
        self.pool[tx["id"]] = tx
        return tx

    def sense(self, tile_white):
        if tile_white:
            self.white += 1
        else:
            self.black += 1

    def _obs(self, s):
        return Observation(self.id, self.white, self.black, s, int(self.cfg["recent_rounds"]), self.rng)

    def act(self, t):
        out = []
        s = self.state()
        if not self.registered_sent:
            out.append(self._tx("register", t, {}))
            self.registered_sent = True
        if not Contract.active(s, self.id):
            return out
        obs = None
        if (t - self.t0) % int(self.cfg["estimate_interval"]) == 0 and t > self.t0:
            due, _ = Contract.ubi_due(s, self.id, s["h"] + 1)
            if s["bal"].get(self.id, 0) + due >= TICKET and self.est_round_sent != s["round"] \
                    and not any(e[0] == self.id for e in s["cur"]):
                obs = self._obs(s)
                est = round(min(1.0, max(0.0, float(self._strategy.estimate(obs)))), 3)
                out.append(self._tx("estimate", t, {"est": est}))
                self.est_round_sent = s["round"]
        if not self.contract.eligible(s, self.id):
            return out
        # periodic detection ("when to remove") -> propose
        if t > 0 and t % int(self.cfg["eval_interval"]) == 0 and s["vote"] is None and self.proposed_at != t:
            obs = obs or self._obs(s)
            if self._strategy.detect(obs):
                out.append(self._tx("propose", t, {}))
                self.proposed_at = t
        # prompted by contract: open vote -> recompile list and vote
        v = s["vote"]
        if v is not None and (v["id"], v["open"]) not in self.voted and self.id not in v["lists"]:
            obs = obs or self._obs(s)
            lst = sorted(int(x) for x in self._strategy.detect(obs))
            if lst or self.cfg["submit_empty_votes"]:
                out.append(self._tx("vote", t, {"vote_id": v["id"], "list": lst}))
            self.voted.add((v["id"], v["open"]))
        return out

    def try_seal(self, t):
        if not self.sealer:
            return None
        ok, _, _ = self.chain.can_seal(self.head, self.id, t)
        if not ok:
            return None
        txs = [tx for tx in self.pool.values() if not self.included(tx["id"])]
        b, _ = self.chain.seal(self.head, self.id, t, txs)
        self.set_head(b)
        return b


# ----------------------------------------------------------------------------
# Environment (holds truth; drives admission/removal from the reference chain)
# ----------------------------------------------------------------------------

class TruthVault:
    def __init__(self):
        self._labels = {}
        self.skipped = []

    def set(self, rid, label):
        self._labels[rid] = label

    def dump(self):
        return {str(k): v for k, v in sorted(self._labels.items())}


class World:
    def __init__(self, cfg, out_dir):
        self.cfg = cfg
        self.out = out_dir
        os.makedirs(out_dir, exist_ok=True)
        seed = int(cfg["seed"])
        self.env_rng = np.random.default_rng(np.random.SeedSequence([seed, 0]))
        self.move_rng = np.random.default_rng(np.random.SeedSequence([seed, 1]))
        self.L = math.sqrt(float(cfg["arena_area_m2"]))
        self.T = int(cfg["timesteps"])
        self._truth = TruthVault()
        self.tiles = self._make_tiles()
        self.true_fraction = float(self.tiles.mean())
        self.contract = Contract(cfg)
        e = cfg["exp"]
        base = list(range(e["n_init"]))
        g = {"height": 0, "parent": "0" * 64, "sealer": -1, "ts": 0, "diff": 0,
             "txroot": txroot([]), "cfg": sha(cfg), "base": base, "sealers": base}
        g["hash"] = sha(g)
        g["td"] = 0
        g["txs"] = []
        self.genesis = g
        gs = Contract.genesis_state(base, set(base))
        self.chain = Chain(cfg, self.contract, g, gs)
        self.robots = {}
        self.pos = {}
        self.heading = {}
        self.straight = {}
        self.next_id = 0
        self.phys_removed = {}
        self.ledger = Ledger(os.path.join(out_dir, "ledger.jsonl"))
        self.ledger.write({"ev": "header", "stamp": STAMP, "harness": HARNESS, "arm": "A",
                           "config": cfg, "code_sha256": file_sha(os.path.abspath(__file__)),
                           "genesis": g, "genesis_state_hash": Contract.state_hash(gs),
                           "note": "swarm-observable + environment events only; truth labels are in truth.json"})
        byz_init = set(int(x) for x in self.env_rng.choice(base, size=e["n_byz_init"], replace=False)) \
            if e["n_byz_init"] else set()
        for rid in base:
            self._spawn(rid in byz_init, base=True, sealer=True, t=0, reason="initial")
        self.sched = self._schedule()

    def _make_tiles(self):
        n = int(self.cfg["tiles_per_side"])
        tiles = np.zeros((n, n), dtype=np.int8)
        n_white = int(round(self.cfg["white_fraction"] * n * n))
        # two corner clusters (bottom-left, top-right), filled nearest-corner first
        half = [n_white // 2, n_white - n_white // 2]
        for (cx, cy), k in zip(((0, 0), (n - 1, n - 1)), half):
            order = sorted((max(abs(x - cx), abs(y - cy)), abs(x - cx) + abs(y - cy), x, y)
                           for x in range(n) for y in range(n))
            placed = 0
            for _, _, x, y in order:
                if placed >= k:
                    break
                if tiles[x, y] == 0:
                    tiles[x, y] = 1
                    placed += 1
        return tiles

    def _tile_white(self, p):
        n = self.tiles.shape[0]
        ix = min(n - 1, max(0, int(p[0] / self.L * n)))
        iy = min(n - 1, max(0, int(p[1] / self.L * n)))
        return bool(self.tiles[ix, iy])

    def _schedule(self):
        e = self.cfg["exp"]
        if not e["scheduled"]:
            return []
        mins = list(self.cfg["scheduled_minutes"])
        if self.cfg["schedule_mode"] == "cumulative":
            acc, times = 0, []
            for m in mins:
                acc += m
                times.append(acc * 60)
        else:
            times = [m * 60 for m in mins]
        return [t for t in times if t <= self.T]

    def _strategy_for(self, byz):
        if not byz:
            return HonestStrategy(self.cfg)
        return NaiveByzantine(self.cfg) if self.cfg["byz"] == "naive" else SmartByzantine(self.cfg)

    def _spawn(self, byz, base, sealer, t, reason):
        rid = self.next_id
        self.next_id += 1
        rng = np.random.default_rng(np.random.SeedSequence([int(self.cfg["seed"]), 2, rid]))
        r = Robot(rid, self._strategy_for(byz), self.chain, self.contract, self.cfg, rng, base, sealer, t)
        self.robots[rid] = r
        self.pos[rid] = self.env_rng.uniform(0.04, self.L - 0.04, size=2)
        self.heading[rid] = float(self.env_rng.uniform(0, 2 * math.pi))
        self.straight[rid] = float(self.move_rng.exponential(self.cfg["straight_mean_s"]))
        self._truth.set(rid, {"label": "byzantine" if byz else "honest",
                              "strategy": self.cfg["byz"] if byz else "honest", "admitted_t": t})
        self.ledger.write({"ev": "env_admit", "t": t, "robot": rid, "base": base, "sealer": sealer, "reason": reason})
        return rid

    def admit_new(self, t, n, p_byz, reason):
        for _ in range(n):
            byz = float(self.env_rng.random()) < p_byz
            in_final = t > self.T - int(self.cfg["final_window_s"])
            if in_final and (byz or self.cfg["final_window_policy"] == "skip_all"):
                # recorded in the truth vault only (a ledger line would leak that the draw was Byzantine)
                self._truth.skipped.append({"t": t, "reason": reason, "draw": "byzantine" if byz else "honest",
                                            "policy": self.cfg["final_window_policy"]})
                continue
            self._spawn(byz, base=False, sealer=False, t=t, reason=reason)

    def active_ids(self):
        return sorted(r for r in self.robots if r not in self.phys_removed)

    def move(self, ids):
        v = float(self.cfg["speed_mps"])
        lo, hi = 0.04, self.L - 0.04
        for rid in ids:
            self.straight[rid] -= 1.0
            if self.straight[rid] <= 0:
                self.heading[rid] = float(self.move_rng.uniform(0, 2 * math.pi))
                self.straight[rid] = float(self.move_rng.exponential(self.cfg["straight_mean_s"]))
            h = self.heading[rid]
            p = self.pos[rid] + v * np.array([math.cos(h), math.sin(h)])
            if p[0] < lo or p[0] > hi:
                h = math.pi - h
                p[0] = min(hi, max(lo, p[0]))
            if p[1] < lo or p[1] > hi:
                h = -h
                p[1] = min(hi, max(lo, p[1]))
            self.heading[rid] = h
            self.pos[rid] = p

    def components(self, ids):
        """connected components of the unit-disk communication graph (range comm_range_m)"""
        if not ids:
            return []
        P = np.array([self.pos[i] for i in ids])
        d2 = ((P[:, None, :] - P[None, :, :]) ** 2).sum(-1)
        rr = float(self.cfg["comm_range_m"]) ** 2
        parent = list(range(len(ids)))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        ii, jj = np.nonzero(np.triu(d2 <= rr, 1))
        for a, b in zip(ii.tolist(), jj.tolist()):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
        comps = {}
        for k, rid in enumerate(ids):
            comps.setdefault(find(k), []).append(rid)
        return sorted((sorted(c) for c in comps.values()), key=lambda c: c[0])

    def sync(self, comp, t):
        """gossip within one connected component: adopt best head, merge tx pools"""
        robots = [self.robots[r] for r in comp]
        best = robots[0].head
        for r in robots[1:]:
            if Chain.better(r.head, best):
                best = r.head
        for r in robots:
            if r.head["hash"] != best["hash"]:
                info = r.set_head(best)
                if info:
                    info["t"] = t
                    self.ledger.write(dict({"ev": "reorg"}, **info))
        union = {}
        for r in robots:
            union.update(r.pool)
        ref = robots[0]
        pending = {k: v for k, v in union.items() if not ref.included(k)}
        for r in robots:
            r.pool = dict(pending)

    def reference_head(self):
        """'robot with the longest blockchain' (paper metric (i)) = best fork-choice head"""
        best = None
        for rid in self.active_ids():
            h = self.robots[rid].head
            if best is None or Chain.better(h, best):
                best = h
        return best

    def run(self):
        e = self.cfg["exp"]
        snap = int(self.cfg["snapshot_every"])
        sched = list(self.sched)
        t_start = time.time()
        comps = []
        last_ref = None
        for t in range(1, self.T + 1):
            ids = self.active_ids()
            self.move(ids)
            for rid in ids:
                self.robots[rid].sense(self._tile_white(self.pos[rid]))
            for rid in ids:
                self.robots[rid].act(t)
            if self.cfg["seal_mode"] == "per_node":
                for rid in ids:
                    b = self.robots[rid].try_seal(t)
                    if b is not None:
                        self.ledger.write({"ev": "block", "t": t, "block": b, "receipt": self.chain.receipt[b["hash"]]})
            comps = self.components(ids)
            for c in comps:
                if len(c) > 1:
                    self.sync(c, t)
            if self.cfg["seal_mode"] == "component":
                for c in comps:
                    head = self.robots[c[0]].head
                    present = [r for r in c if self.robots[r].sealer]
                    if not present:
                        continue
                    sealer = self.chain.component_sealer(head, present, t)
                    if sealer is None:
                        continue
                    sr = self.robots[sealer]
                    txs = [tx for tx in sr.pool.values() if not sr.included(tx["id"])]
                    b, _ = self.chain.seal(head, sealer, t, txs)
                    self.ledger.write({"ev": "block", "t": t, "block": b, "receipt": self.chain.receipt[b["hash"]],
                                       "component": c})
                    for r in c:
                        self.robots[r].set_head(b)
            # environment: physical removal driven by the reference chain's contract state
            ref = self.reference_head()
            rs = self.chain.state[ref["hash"]]
            for rid in sorted(rs["removed"]):
                if rid in self.robots and rid not in self.phys_removed:
                    self.phys_removed[rid] = t
                    self.ledger.write({"ev": "env_remove", "t": t, "robot": rid, "ref_head": ref["hash"],
                                       "ref_height": ref["height"], "onchain_height": rs["removed"][rid]})
                    self.admit_new(t, e["influx_per_removal"], e["p_byz_added"], "influx_after_removal_of_%d" % rid)
            while sched and sched[0] == t:
                sched.pop(0)
                self.admit_new(t, int(self.cfg["scheduled_count"]), e["p_byz_added"], "scheduled")
            # per-tick reference capture (written only when it changes -> exact for every tick)
            ref = self.reference_head()
            rs = self.chain.state[ref["hash"]]
            if ref["hash"] != last_ref:
                last_ref = ref["hash"]
                self.ledger.write({"ev": "ref", "t": t, "ref_head": ref["hash"], "ref_height": ref["height"],
                                   "ref_mean": rs["mean"],
                                   "active": sorted(r for r in rs["reg"] if r not in rs["removed"]),
                                   "eligible": sorted(r for r in rs["reg"] if self.contract.eligible(rs, r))})
            if t % snap == 0 or t == self.T:
                ref = self.reference_head()
                rs = self.chain.state[ref["hash"]]
                act = self.active_ids()
                self.ledger.write({"ev": "snapshot", "t": t, "ref_head": ref["hash"], "ref_height": ref["height"],
                                   "ref_mean": rs["mean"], "ref_round": rs["round"],
                                   "onchain_active": Contract.n_active(rs), "phys_active": len(act),
                                   "n_components": len(comps),
                                   "components_gt1": [c for c in comps if len(c) > 1],
                                   "heads": {str(r): self.robots[r].head["height"] for r in act},
                                   "ref_state_hash": Contract.state_hash(rs)})
        ref = self.reference_head()
        truth = {"stamp": STAMP, "true_white_fraction": self.true_fraction, "labels": self._truth.dump(),
                 "skipped_admissions_final_window": self._truth.skipped,
                 "note": "ground truth; written by Environment only; never read by swarm code"}
        tpath = os.path.join(self.out, "truth.json")
        with open(tpath, "w") as f:
            f.write(canon(truth))
        self.ledger.write({"ev": "footer", "t": self.T, "stamp": STAMP, "ref_head": ref["hash"],
                           "ref_height": ref["height"], "n_blocks": len(self.chain.blocks),
                           "n_robots": len(self.robots), "truth_sha256": file_sha(tpath)})
        self.ledger.close()
        return {"ledger_head": self.ledger.prev, "wall_s": round(time.time() - t_start, 2)}


def run_one(cfg, out_dir):
    w = World(cfg, out_dir)
    res = w.run()
    meta = {"stamp": STAMP, "config": cfg, "ledger_head": res["ledger_head"], "wall_s": res["wall_s"],
            "ledger_sha256": file_sha(os.path.join(out_dir, "ledger.jsonl")),
            "truth_sha256": file_sha(os.path.join(out_dir, "truth.json"))}
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1, sort_keys=True)
    return meta


# ----------------------------------------------------------------------------
# REPLAY / VERIFY: hash chain, block/tx hashes, PoA rules, contract re-execution
# from genesis for every logged block (all forks), env events vs chain state;
# optional full deterministic re-simulation (byte-identical ledger).
# ----------------------------------------------------------------------------

def verify_ledger(run_dir, full_resim=False):
    path = os.path.join(run_dir, "ledger.jsonl")
    errors = []
    prev = "0" * 64
    lines = []
    with open(path) as f:
        for n, line in enumerate(f):
            try:
                obj = json.loads(line)
            except Exception as ex:
                errors.append("line %d: json %s" % (n, ex))
                break
            h = obj.pop("h", None)
            if obj.get("prev") != prev or obj.get("seq") != n or sha(obj) != h:
                errors.append("line %d: hash chain broken" % n)
            prev = h
            lines.append(obj)
    if not lines or lines[0].get("ev") != "header":
        return {"ok": False, "errors": errors + ["no header"], "n_errors": len(errors) + 1}
    hdr = lines[0]
    cfg = hdr["config"]
    if hdr.get("stamp") != STAMP or cfg.get("stamp") != STAMP:
        errors.append("stamp mismatch")
    contract = Contract(cfg)
    g = hdr["genesis"]
    gchk = {k: g[k] for k in g if k not in ("hash", "td", "txs")}
    if sha(gchk) != g["hash"] or g["cfg"] != sha(cfg):
        errors.append("genesis hash / config binding mismatch")
    gs = Contract.genesis_state(g["base"], set(g["sealers"]))
    if Contract.state_hash(gs) != hdr["genesis_state_hash"]:
        errors.append("genesis state mismatch")
    chain = Chain(cfg, contract, g, gs)
    n_blocks = 0
    removals_onchain = {}
    tick_sealed = {}
    exec_checks = []
    for obj in lines[1:]:
        if obj["ev"] != "block":
            continue
        b = obj["block"]
        n_blocks += 1
        tag = b.get("hash", "?")[:12]
        for tx in b["txs"]:
            if not tx_id_ok(tx):
                errors.append("block %s: tx id mismatch" % tag)
        if txroot(b["txs"]) != b["txroot"]:
            errors.append("block %s: txroot mismatch" % tag)
        if sha(block_header(b)) != b["hash"]:
            errors.append("block %s: header hash mismatch" % tag)
        if b["parent"] not in chain.blocks:
            errors.append("block %s: unknown parent" % tag)
            continue
        if b["hash"] in chain.blocks:
            errors.append("block %s: duplicate" % tag)
            continue
        parent = chain.blocks[b["parent"]]
        if b["height"] != parent["height"] + 1:
            errors.append("block %s: bad height" % tag)
        ok, diff, _ = chain.can_seal(parent, b["sealer"], b["ts"])
        if not ok or diff != b["diff"]:
            errors.append("block %s: PoA rule violated (ok=%s diff=%s/%s)" % (tag, ok, diff, b["diff"]))
        if b["td"] != parent["td"] + b["diff"]:
            errors.append("block %s: td mismatch" % tag)
        if sorted(b["txs"], key=tx_sort_key) != b["txs"]:
            errors.append("block %s: tx order not canonical" % tag)
        if b["ts"] != obj["t"]:
            errors.append("block %s: ts != ledger t" % tag)
        if cfg.get("seal_mode", "component") == "component":
            comp = obj.get("component") or []
            if b["sealer"] not in comp:
                errors.append("block %s: sealer not in logged component" % tag)
            for other in comp:
                if other in tick_sealed.setdefault(obj["t"], set()):
                    errors.append("block %s: robot %d in two sealing components at t=%d" % (tag, other, obj["t"]))
            tick_sealed[obj["t"]].update(comp)
            if b["diff"] == 1:
                ps_ = chain.state[parent["hash"]]
                sl = Contract.active_sealers(ps_)
                pref = sl[(parent["height"] + 1) % len(sl)] if sl else None
                if pref in comp and chain.can_seal(parent, pref, b["ts"])[0]:
                    errors.append("block %s: preferred sealer present but not chosen" % tag)
        chain.add_block(b)
        rc = chain.receipt[b["hash"]]
        rec = obj["receipt"]
        # I3: every accepted vote/propose came from a robot eligible under the constitution
        post = chain.state[b["hash"]]
        pre = chain.state[parent["hash"]]
        for e in rc["events"]:
            if e[0] in ("vote", "propose"):
                r_ = e[1]
                if not (Contract.active(pre, r_) and (post["reg"][r_][0] or post["valid"].get(r_, 0) >= int(cfg["alpha"]))):
                    errors.append("I3: block %s counted %s from ineligible robot %d" % (tag, e[0], r_))
            if e[0] == "vote_exec":
                exec_checks.append((b["hash"], e))
        if rc["state_hash"] != rec["state_hash"]:
            errors.append("block %s: state hash mismatch on re-execution" % tag)
        if canon(rc["events"]) != canon(rec["events"]) or canon(rc["bal_diff"]) != canon(rec["bal_diff"]):
            errors.append("block %s: receipt mismatch on re-execution" % tag)
        for e in rc["events"]:
            if e[0] == "remove":
                removals_onchain.setdefault(e[1], []).append(b["hash"])
    # I2: each removal decision recomputed from the logged votes on that fork + the constitution
    rlf, rmin = float(cfg["remove_list_fraction"]), int(cfg["remove_min_votes"])
    for bh, e in exec_checks:
        vid = e[1]
        lists = {}
        cur = chain.blocks[bh]
        found_open = False
        while cur["height"] > 0 and not found_open:
            for ev_ in reversed(chain.receipt[cur["hash"]]["events"]):
                if ev_[0] == "vote" and ev_[2] == vid:
                    lists.setdefault(ev_[1], ev_[3])
                if ev_[0] == "vote_open" and ev_[1] == vid:
                    found_open = True
            cur = chain.blocks[cur["parent"]]
        pre = chain.state[chain.blocks[bh]["parent"]]
        cnt = {}
        for lst in lists.values():
            for x in lst:
                cnt[x] = cnt.get(x, 0) + 1
        expect = sorted(x for x, c in cnt.items() if Contract.active(pre, x) and c >= rlf * len(lists) and c >= rmin)
        if not found_open or expect != e[4] or len(lists) != e[2]:
            errors.append("I2: vote %d decision not reproducible from logged votes (%s vs %s)" % (vid, expect, e[4]))
    for obj in lines[1:]:
        if obj["ev"] == "ref":
            st_ = chain.state.get(obj["ref_head"])
            if st_ is None or obj["active"] != sorted(r for r in st_["reg"] if r not in st_["removed"]) or \
                    obj["eligible"] != sorted(r for r in st_["reg"] if contract.eligible(st_, r)) or obj["ref_mean"] != st_["mean"]:
                errors.append("ref t=%d: does not match re-executed state" % obj["t"])
        if obj["ev"] == "env_remove":
            if obj["robot"] not in removals_onchain:
                errors.append("env_remove %d without on-chain removal" % obj["robot"])
            elif obj["ref_head"] not in chain.blocks or obj["robot"] not in chain.state[obj["ref_head"]]["removed"]:
                errors.append("env_remove %d not in referenced head state" % obj["robot"])
        elif obj["ev"] == "snapshot":
            if obj["ref_head"] not in chain.blocks or \
                    Contract.state_hash(chain.state[obj["ref_head"]]) != obj["ref_state_hash"]:
                errors.append("snapshot t=%d: ref state mismatch" % obj["t"])
        elif obj["ev"] == "reorg":
            for k in ("old", "new", "ancestor"):
                if obj[k] not in chain.blocks:
                    errors.append("reorg t=%d: unknown block" % obj["t"])
    footer = lines[-1]
    if footer.get("ev") != "footer":
        errors.append("missing footer")
    else:
        if footer.get("stamp") != STAMP:
            errors.append("footer stamp mismatch")
        tp = os.path.join(run_dir, "truth.json")
        if not os.path.exists(tp) or file_sha(tp) != footer["truth_sha256"]:
            errors.append("truth.json hash does not match footer")
        if footer["ref_head"] not in chain.blocks:
            errors.append("footer ref head unknown")
    out = {"ok": not errors, "errors": errors[:50], "n_errors": len(errors), "n_lines": len(lines),
           "n_blocks": n_blocks, "ledger_head": prev, "stamp": STAMP,
           "what": "ENGINEERING VALIDATION ONLY (I2 removal decisions reproducible, I3 eligible-only counting, "
                   "I5 hash chain, block/tx hashes, PoA rules, contract re-execution of all forks, per-tick ref "
                   "capture, truth hash); says nothing about paper fidelity or R0",
           "n_vote_exec_checked_I2": len(exec_checks),
           "code_sha256_in_header": hdr.get("code_sha256"),
           "code_sha256_now": file_sha(os.path.abspath(__file__))}
    if full_resim:
        tmp = run_dir.rstrip("/") + ".resim_tmp"
        if os.path.exists(tmp):
            shutil.rmtree(tmp)
        meta = run_one(copy.deepcopy(hdr["config"]), tmp)
        same = meta["ledger_head"] == prev and file_sha(os.path.join(tmp, "ledger.jsonl")) == file_sha(path) \
            and file_sha(os.path.join(tmp, "truth.json")) == file_sha(os.path.join(run_dir, "truth.json"))
        out["resim_ledger_head"] = meta["ledger_head"]
        out["resim_identical"] = bool(same)
        if not same:
            out["ok"] = False
            out["errors"].append("full re-simulation is not byte-identical")
        shutil.rmtree(tmp)
    return out


# ----------------------------------------------------------------------------
# L5 SCORER -- independent observer. Reads ledger.jsonl + truth.json (JSON only),
# uses no swarm class, and its output (score.json) never feeds back into a run.
# ----------------------------------------------------------------------------

class L5Scorer:
    def __init__(self, run_dir):
        self.run_dir = run_dir

    def _read(self):
        with open(os.path.join(self.run_dir, "ledger.jsonl")) as f:
            lines = [json.loads(l) for l in f]
        with open(os.path.join(self.run_dir, "truth.json")) as f:
            truth = json.load(f)
        return lines, truth

    def score(self):
        lines, truth = self._read()
        hdr = lines[0]
        T = int(hdr["config"]["timesteps"])
        fw = int(hdr["config"]["final_window_s"])
        labels = {int(k): v["label"] for k, v in truth["labels"].items()}
        tv = float(truth["true_white_fraction"])
        admit = {o["robot"]: o["t"] for o in lines if o["ev"] == "env_admit"}
        remove = {o["robot"]: o["t"] for o in lines if o["ev"] == "env_remove"}
        byz = [r for r in admit if labels[r] == "byzantine"]
        hon = [r for r in admit if labels[r] == "honest"]
        rb = [r for r in byz if r in remove]
        rh = [r for r in hon if r in remove]
        # per-tick reconstruction (every tick 1..T; nothing sampled between blocks)
        refs = sorted((o for o in lines if o["ev"] == "ref"), key=lambda o: o["seq"])
        adm_at, rem_at = {}, {}
        for r, t in admit.items():
            adm_at.setdefault(t, []).append(r)
        for r, t in remove.items():
            rem_at.setdefault(t, []).append(r)
        alive = set(adm_at.get(0, []))
        ri, cur_ref = 0, None
        sizes, byzs, errs, fin_errs, el_share = [], [], [], [], []
        ticks_over = []
        for t in range(1, T + 1):
            for r in adm_at.get(t, []):
                alive.add(r)
            for r in rem_at.get(t, []):
                alive.discard(r)
            while ri < len(refs) and refs[ri]["t"] <= t:
                cur_ref = refs[ri]
                ri += 1
            sizes.append(len(alive))
            byzs.append(sum(1 for r in alive if labels[r] == "byzantine"))
            if cur_ref is not None and cur_ref["ref_mean"] is not None:
                e = abs(cur_ref["ref_mean"] - tv)
                errs.append(e)
                if t > T - fw:
                    fin_errs.append(e)
            if cur_ref is not None and cur_ref["eligible"]:
                el = cur_ref["eligible"]
                sh = sum(1 for r in el if labels[r] == "byzantine") / len(el)
                el_share.append(sh)
                if sh > 0.5:
                    ticks_over.append(t)
            else:
                el_share.append(0.0)
        n_reorg = sum(1 for o in lines if o["ev"] == "reorg")
        footer = lines[-1]
        return {
            "stamp": STAMP, "scorer": "L5Scorer v0.2 (observational; per-tick; excluded from swarm)",
            "run_dir": os.path.basename(os.path.abspath(self.run_dir)),
            "experiment": hdr["config"]["experiment"], "byz": hdr["config"]["byz"], "alpha": hdr["config"]["alpha"],
            "k": hdr["config"]["k_std"], "seed": hdr["config"]["seed"], "true_white_fraction": tv,
            # six paper metrics
            "m1_mean_abs_error": (sum(errs) / len(errs)) if errs else None,
            "m2_tpr": (len(rb) / len(byz)) if byz else None,
            "m3_fpr": (len(rh) / len(hon)) if hon else None,
            "m4_mean_swarm_size": sum(sizes) / len(sizes),
            "m5_mean_byzantine_count": sum(byzs) / len(byzs),
            "m6_robots_removed": len(remove),
            # brief extra metric
            "byz_share_eligible_max": max(el_share) if el_share else 0.0,
            "byz_share_eligible_gt_half_any_tick": bool(ticks_over),
            "byz_share_eligible_gt_half_ticks": len(ticks_over),
            "byz_share_eligible_gt_half_first_tick": ticks_over[0] if ticks_over else None,
            # extras
            "final15_mean_abs_error": (sum(fin_errs) / len(fin_errs)) if fin_errs else None,
            "n_byz_total": len(byz), "n_honest_total": len(hon), "removed_byz": len(rb), "removed_honest": len(rh),
            "final_size": sizes[-1], "final_byz": byzs[-1], "max_size": max(sizes),
            "final_ref_height": footer.get("ref_height"),
            "n_blocks_logged": sum(1 for o in lines if o["ev"] == "block"), "n_reorgs": n_reorg,
            "ticks_scored": T,
        }


# ----------------------------------------------------------------------------
# direct condition runner (brief CLI), metrics JSON, R0 gate
# ----------------------------------------------------------------------------

METRICS = ("m1_mean_abs_error", "m2_tpr", "m3_fpr", "m4_mean_swarm_size", "m5_mean_byzantine_count",
           "m6_robots_removed", "byz_share_eligible_max", "byz_share_eligible_gt_half_ticks",
           "final15_mean_abs_error", "final_size", "max_size", "n_reorgs", "final_ref_height")


def _stats(xs):
    xs = [float(x) for x in xs if x is not None]
    if not xs:
        return {"n": 0}
    a = np.array(xs, dtype=float)
    return {"n": len(xs), "mean": float(a.mean()), "sd": float(a.std(ddof=1)) if len(xs) > 1 else 0.0,
            "median": float(np.median(a)), "min": float(a.min()), "max": float(a.max())}


def _condition_job(args):
    cfg, d, full_resim = args
    if os.path.exists(d):
        shutil.rmtree(d)
    meta = run_one(cfg, d)
    rp = verify_ledger(d, full_resim=full_resim)
    with open(os.path.join(d, "engineering_validation.json"), "w") as f:
        json.dump(rp, f, indent=1, sort_keys=True)
    sc = L5Scorer(d).score()
    with open(os.path.join(d, "score.json"), "w") as f:
        json.dump(sc, f, indent=1, sort_keys=True)
    return {"run": os.path.basename(d), "seed": cfg["seed"], "engineering_ok": rp["ok"],
            "resim_identical": rp.get("resim_identical"), "wall_s": meta["wall_s"], "score": sc}


def run_condition(exp, alpha, byz, runs, seed, k, out, workers=1, full_resim=True, overrides=None):
    """Brief CLI: python swarm_r0.py --exp E --alpha A --byz B --runs N --seed S --k K.
    Run i uses seed S+i (alpha excluded -> alpha=1/10 runs are paired)."""
    out = os.path.abspath(out)
    os.makedirs(out, exist_ok=True)
    jobs = []
    for i in range(runs):
        cfg = make_config(experiment=exp, alpha=alpha, byz=byz, seed=seed + i, k_std=k, **(overrides or {}))
        jobs.append((cfg, os.path.join(out, "run_%02d_seed%d" % (i, seed + i)), full_resim))
    if workers > 1:
        with mp.Pool(workers) as pool:
            res = pool.map(_condition_job, jobs)
    else:
        res = [_condition_job(j) for j in jobs]
    ok_runs = [r for r in res if r["engineering_ok"] and (not full_resim or r["resim_identical"])]
    metrics = {
        "stamp": STAMP, "harness": HARNESS, "arm": "A", "code_sha256": file_sha(os.path.abspath(__file__)),
        "command": {"exp": exp, "alpha": alpha, "byz": byz, "runs": runs, "seed": seed, "k": k,
                    "overrides": overrides or {}},
        "config_run0": jobs[0][0] if jobs else None,
        "assumptions": ASSUMPTIONS,
        "engineering_validation": {"runs_validated": len(ok_runs), "runs_total": len(res),
                                   "full_resim_required": full_resim,
                                   "note": "engineering validation only; not evidence of paper fidelity or R0"},
        "aggregate_over_validated_runs": {m: _stats([r["score"][m] for r in ok_runs]) for m in METRICS},
        "byz_share_eligible_gt_half_any_tick_runs": sum(1 for r in ok_runs if r["score"]["byz_share_eligible_gt_half_any_tick"]),
        "runs": [{"run": r["run"], "seed": r["seed"], "engineering_ok": r["engineering_ok"],
                  "resim_identical": r["resim_identical"], "wall_s": r["wall_s"],
                  "metrics": {k2: v for k2, v in r["score"].items() if k2 not in ("stamp", "scorer", "run_dir")}}
                 for r in res],
    }
    with open(os.path.join(out, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=1, sort_keys=True)
    return metrics


def sign_test_p(pos, neg):
    """two-sided exact binomial sign test, ties dropped"""
    n = pos + neg
    if n == 0:
        return None
    k = min(pos, neg)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n)


R0_TPR_TOLERANCE = 0.05   # ASSUMPTION-16


def r0_gate(root):
    """SEED section 7 (as relayed): R0 requires the paper direction for alpha=10 vs 1:
    lower FPR AND comparable-or-higher TPR, in every exp x byz pair, with >=10
    engineering-validated runs per condition. Otherwise R0 FAIL (not reproduced)."""
    conds, pairs = {}, {}
    for e in (1, 2, 3):
        for b in ("naive", "smart"):
            for a in (1, 10):
                p = os.path.join(root, "exp%d_%s_a%d" % (e, b, a), "metrics.json")
                conds[(e, b, a)] = json.load(open(p)) if os.path.exists(p) else None
    eng_ok = all(c is not None and c["engineering_validation"]["runs_validated"] >= 10 for c in conds.values())
    all_dir = True
    for e in (1, 2, 3):
        for b in ("naive", "smart"):
            c1, c10 = conds[(e, b, 1)], conds[(e, b, 10)]
            if c1 is None or c10 is None:
                pairs["exp%d_%s" % (e, b)] = {"status": "MISSING"}
                all_dir = False
                continue
            g = lambda c, m: c["aggregate_over_validated_runs"][m].get("mean")
            f1, f10, t1, t10 = g(c1, "m3_fpr"), g(c10, "m3_fpr"), g(c1, "m2_tpr"), g(c10, "m2_tpr")
            fpr_ok = f1 is not None and f10 is not None and f10 < f1
            tpr_ok = t1 is not None and t10 is not None and t10 >= t1 - R0_TPR_TOLERANCE
            r1 = {r["seed"]: r for r in c1["runs"] if r["engineering_ok"]}
            r10 = {r["seed"]: r for r in c10["runs"] if r["engineering_ok"]}
            paired = {}
            for m in ("m3_fpr", "m2_tpr", "m1_mean_abs_error"):
                ds = [r10[sd]["metrics"][m] - r1[sd]["metrics"][m] for sd in sorted(set(r1) & set(r10))
                      if r1[sd]["metrics"][m] is not None and r10[sd]["metrics"][m] is not None]
                pos, neg = sum(1 for d in ds if d > 0), sum(1 for d in ds if d < 0)
                paired[m] = {"n_pairs": len(ds), "mean_diff_a10_minus_a1": (sum(ds) / len(ds)) if ds else None,
                             "a10_lower": neg, "a10_higher": pos, "ties": len(ds) - pos - neg,
                             "sign_test_p_two_sided": sign_test_p(pos, neg)}
            ok = fpr_ok and tpr_ok
            all_dir = all_dir and ok
            pairs["exp%d_%s" % (e, b)] = {
                "fpr_a1": f1, "fpr_a10": f10, "tpr_a1": t1, "tpr_a10": t10,
                "lower_fpr_a10": fpr_ok, "tpr_a10_comparable_or_higher": tpr_ok,
                "direction_matches_paper": ok, "paired_by_seed_descriptive": paired}
    status = "R0 PASS" if (eng_ok and all_dir) else "R0 FAIL - paper direction NOT REPRODUCED"
    if not eng_ok:
        status = "R0 FAIL - insufficient engineering-validated runs"
    return {"stamp": STAMP, "harness": HARNESS, "arm": "A",
            "rule": "SEED s7 (relayed): alpha=10 must show lower mean FPR and comparable-or-higher mean TPR "
                    "(>= alpha1 - %.2f, ASSUMPTION-16) vs alpha=1 in all 6 exp x byz pairs; >=10 "
                    "engineering-validated runs per condition" % R0_TPR_TOLERANCE,
            "engineering_validation_all_conditions_ge10": eng_ok,
            "R0_status": status, "pairs": pairs,
            "consequence": "R0 not established; no downstream (arm B-D) claims may rely on this harness"
                           if not status == "R0 PASS" else "R0 direction observed in this harness only"}


# ----------------------------------------------------------------------------
# tamper test + self-test
# ----------------------------------------------------------------------------

def _rehash(objs):
    prev = "0" * 64
    out = []
    for n, o in enumerate(objs):
        o = {k: v for k, v in o.items() if k != "h"}
        o["seq"], o["prev"] = n, prev
        o["h"] = sha(o)
        prev = o["h"]
        out.append(canon(o))
    return out


def tamper_test(run_dir, scratch):
    """Applies tamperings to copies of a run; each must be detected by verify_ledger."""
    results = []
    with open(os.path.join(run_dir, "ledger.jsonl")) as f:
        lines = f.read().splitlines()
    blk_idx = next(i for i, l in enumerate(lines) if '"ev":"block"' in l and '"type":"estimate"' in l)
    vote_idx = next((i for i, l in enumerate(lines) if '"ev":"block"' in l and '"type":"vote"' in l), None)

    def check(name, new_lines, truth_patch=None):
        d = os.path.join(scratch, name)
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)
        with open(os.path.join(d, "ledger.jsonl"), "w") as f:
            f.write("\n".join(new_lines) + "\n")
        shutil.copy(os.path.join(run_dir, "truth.json"), os.path.join(d, "truth.json"))
        if truth_patch:
            truth_patch(os.path.join(d, "truth.json"))
        r = verify_ledger(d)
        results.append({"tamper": name, "detected": not r["ok"], "first_errors": r["errors"][:3]})
        shutil.rmtree(d)

    def bump_estimate(block, fix_ids):
        for tx in block["txs"]:
            if tx["type"] == "estimate":
                tx["data"]["est"] = round(min(1.0, tx["data"]["est"] + 0.111), 3)
                if fix_ids:
                    tx["id"] = sha({k: tx[k] for k in ("type", "sender", "t", "nonce", "data")})
                break
        if fix_ids:
            block["txs"] = sorted(block["txs"], key=tx_sort_key)
            block["txroot"] = txroot(block["txs"])
            block["hash"] = sha(block_header(block))

    # 1 naive edit of an estimate value (no rehash)
    o = json.loads(lines[blk_idx])
    bump_estimate(o["block"], False)
    l2 = list(lines)
    l2[blk_idx] = canon(o)
    check("edit_estimate_no_rehash", l2)
    # 2 same edit with the ledger hash chain recomputed
    objs = [json.loads(l) for l in lines]
    bump_estimate(objs[blk_idx]["block"], False)
    check("edit_estimate_rehash_chain", _rehash(objs))
    # 3 deep forgery: recompute tx id, txroot, block hash and the ledger chain
    objs = [json.loads(l) for l in lines]
    bump_estimate(objs[blk_idx]["block"], True)
    check("deep_forgery_estimate_rehash_all", _rehash(objs))
    # 4 erase one vote list (deep forgery) or delete a block if no vote occurred
    objs = [json.loads(l) for l in lines]
    if vote_idx is not None:
        blk = objs[vote_idx]["block"]
        for tx in blk["txs"]:
            if tx["type"] == "vote":
                tx["data"]["list"] = [] if tx["data"]["list"] else [0]
                tx["id"] = sha({k: tx[k] for k in ("type", "sender", "t", "nonce", "data")})
                break
        blk["txs"] = sorted(blk["txs"], key=tx_sort_key)
        blk["txroot"] = txroot(blk["txs"])
        blk["hash"] = sha(block_header(blk))
        check("deep_forgery_vote_list", _rehash(objs))
    else:
        del objs[blk_idx]
        check("delete_block_rehash_chain", _rehash(objs))

    # 5 truth relabel
    def flip(p):
        with open(p) as f:
            t = json.load(f)
        k = sorted(t["labels"])[0]
        t["labels"][k]["label"] = "honest" if t["labels"][k]["label"] == "byzantine" else "byzantine"
        with open(p, "w") as f:
            f.write(canon(t))
    check("truth_relabel", list(lines), truth_patch=flip)
    return {"stamp": STAMP, "run": os.path.basename(os.path.abspath(run_dir)), "results": results,
            "all_detected": all(r["detected"] for r in results)}


def selftest(scratch):
    os.makedirs(scratch, exist_ok=True)
    out = []

    def ok(name, cond, detail=""):
        out.append({"test": name, "pass": bool(cond), "detail": detail})

    cfg = make_config(experiment=1, byz="naive", alpha=2)
    c = Contract(cfg)
    s = Contract.genesis_state(list(range(6)), set(range(6)))

    def blk(h, txs):
        return {"height": h, "txs": txs}
    s1, rc1 = c.apply_block(s, blk(3, [make_tx("estimate", 0, 1, 0, {"est": 0.2})]))
    # height 3 < UBI_SCHEDULE[2]=4 -> UBI index 2 -> 2*20 = 40 credited, then 40 staked
    ok("ubi_and_stake", s1["bal"][0] == 0 and rc1["events"][0] == ["ubi", 0, 40], canon(rc1["events"]))
    s2, _ = c.apply_block(s1, blk(3, [make_tx("estimate", 1, 1, 0, {"est": 0.3}),
                                      make_tx("estimate", 2, 1, 0, {"est": 0.4})]))
    ok("round_close_mean", s2["round"] == 1 and abs(s2["mean"] - 0.3) < 1e-12, str(s2["mean"]))
    ok("refund_and_valid_count", s2["bal"][1] == 40 and s2["bal"][0] == 40 and s2["valid"][2] == 1)
    s3, _ = c.apply_block(s2, blk(4, [make_tx("register", 9, 2, 0, {})]))
    ok("new_robot_not_eligible", not c.eligible(s3, 9) and c.eligible(s3, 0))
    s3b = Contract.copy_state(s3)
    s3b["valid"][9] = 2
    ok("alpha_eligible_after_alpha_valid_estimates", c.eligible(s3b, 9) and not c.eligible(s3, 9))
    st = s3
    for i in range(4):
        st, _ = c.apply_block(st, blk(5, [make_tx("propose", i, 3, 0, {})]))
    ok("no_vote_below_min5", st["vote"] is None and len(st["props"]) == 4)
    st, _ = c.apply_block(st, blk(5, [make_tx("propose", 4, 3, 0, {})]))
    ok("vote_opens_at_50pct_and_5", st["vote"] is not None and st["props"] == [])
    vid = st["vote"]["id"]
    st, _ = c.apply_block(st, blk(6, [make_tx("vote", i, 4, 0, {"vote_id": vid, "list": [5]}) for i in range(5)]
                                  + [make_tx("vote", 5, 4, 0, {"vote_id": vid, "list": [0]})]))
    ok("not_executed_before_5_blocks", st["vote"] is not None)
    bal5 = st["bal"].get(5, 0)
    before = sum(st["bal"].get(i, 0) for i in range(5))
    st, rc = c.apply_block(st, blk(10, []))
    ok("executed_after_5_blocks", st["vote"] is None and 5 in st["removed"] and 0 not in st["removed"],
       canon(rc["events"]))
    after = sum(st["bal"].get(i, 0) for i in range(5))
    ok("redistribution_to_voters", st["bal"][5] == 0 and after - before == (bal5 // 5) * 5, "%d->%d" % (before, after))
    _, rc2 = c.apply_block(st, blk(11, [make_tx("estimate", 5, 5, 1, {"est": 0.1})]))
    ok("removed_robot_rejected", rc2["events"][0][2] == "not_active")
    c2 = Contract(make_config(experiment=1, alpha=1))
    s = Contract.genesis_state(list(range(12)), set(range(12)))
    s["vote"] = {"id": 1, "open": 0, "lists": {i: ([11] if i < 5 else [10] if i < 9 else []) for i in range(10)}}
    s5, rc5 = c2.apply_block(s, blk(5, []))
    ok("removal_needs_50pct_lists_and_5_votes", 11 in s5["removed"] and 10 not in s5["removed"],
       canon(rc5["events"]))
    ids = [1, 2, 3, 4, 5]
    ok("collusion_window_flags_identical_triple",
       _clusters_window(ids, np.array([0.0, 0.0, 0.0, 0.25, 0.31]), 0.007, 3) == [1, 2, 3])
    ok("collusion_window_no_chaining",
       _clusters_window(ids, np.array([0.200, 0.205, 0.210, 0.215, 0.220]), 0.007, 3) == [])
    hs = HonestStrategy(make_config())
    fake = {"mean": 0.25, "removed": {}, "hist": [], "cur": [[1, 0.0], [2, 0.24], [3, 0.26], [4, 0.25],
                                                              [5, 0.27], [6, 0.23], [7, 0.255]]}
    ok("brief_mean_band_collusion_flags_3plus_within_0.07_of_mean",
       hs.detect(Observation(9, 0, 0, fake, 2, None)) == [2, 3, 4, 5, 6, 7])
    fake2 = {"mean": 0.25, "removed": {}, "hist": [], "cur": [[1, 0.0], [2, 0.12], [3, 0.40], [4, 0.25],
                                                               [5, 0.36], [6, 0.13], [7, 0.38], [8, 0.11]]}
    v2 = np.array([0.0, 0.12, 0.40, 0.25, 0.36, 0.13, 0.38, 0.11])
    exp2 = [i for i, v in zip(range(1, 9), v2) if abs(v - 0.25) > 2.0 * v2.std()]
    ok("adaptive_k_std_when_no_collusion", hs.detect(Observation(9, 0, 0, fake2, 2, None)) == exp2, str(exp2))
    ok("k_flag_changes_threshold", HonestStrategy(make_config(k_std=0.5)).detect(Observation(9, 0, 0, fake2, 2, None))
       != hs.detect(Observation(9, 0, 0, fake2, 2, None)))
    bz = NaiveByzantine(make_config())
    ok("byzantine_inverted_flags_near_mean", 1 not in bz.detect(Observation(9, 0, 0, fake, 2, None)))
    # PoA / clique rules
    w = World(make_config(experiment=1, timesteps=5, seed=7), os.path.join(scratch, "w_clique"))
    ch = w.chain
    g = ch.genesis
    _, d, _ = ch.can_seal(g, 1, 15)
    b1, _ = ch.seal(g, 1, 15, [])
    ok("inturn_sealer_difficulty_2", d == 2 and b1["diff"] == 2)
    ok("recents_rule_blocks_resign", not ch.can_seal(b1, 1, 100)[0])
    ok("out_of_turn_diff_1", ch.can_seal(g, 2, 15)[0] is True and ch.can_seal(g, 2, 15)[1] == 1)
    ok("period_15s_enforced", ch.can_seal(g, 2, 14)[0] is False)
    ok("component_prefers_inturn_sealer", ch.component_sealer(g, [0, 1, 2, 5], 15) == 1 and
       ch.component_sealer(g, [0, 2, 5], 15) == 0)
    w.ledger.close()
    r = w.robots[3]
    etx = make_tx("estimate", 2, 30, 0, {"est": 0.25})
    r.pool = {etx["id"]: etx}
    bA, _ = ch.seal(g, 2, 40, [etx])
    r.set_head(bA)
    ok("pending_tx_removed_from_pool_on_inclusion", etx["id"] not in r.pool and r.included(etx["id"]))
    bB, _ = ch.seal(b1, 2, 40, [])
    info = r.set_head(bB)
    ok("reorg_rollback_detected", info is not None and info["depth_old"] == 1 and info["depth_new"] == 2,
       canon(info))
    ok("orphaned_tx_returns_to_pool", etx["id"] in r.pool and not r.included(etx["id"]))
    cfresh = Contract(w.cfg)
    fresh = cfresh.apply_block(cfresh.apply_block(Contract.genesis_state(g["base"], set(g["sealers"])), b1)[0], bB)[0]
    ok("state_after_reorg_equals_fresh_replay", Contract.state_hash(ch.state[bB["hash"]]) == Contract.state_hash(fresh))
    # determinism + verify + tamper on a short real run
    cfgd = make_config(experiment=2, byz="smart", alpha=1, seed=12345, timesteps=1200)
    m1 = run_one(cfgd, os.path.join(scratch, "det1"))
    m2 = run_one(copy.deepcopy(cfgd), os.path.join(scratch, "det2"))
    ok("deterministic_byte_identical_ledger", m1["ledger_sha256"] == m2["ledger_sha256"], m1["ledger_sha256"][:16])
    vr = verify_ledger(os.path.join(scratch, "det1"))
    ok("verify_short_run", vr["ok"], canon(vr["errors"][:3]))
    tt = tamper_test(os.path.join(scratch, "det1"), os.path.join(scratch, "tamper"))
    ok("tamper_all_detected", tt["all_detected"], canon([(x["tamper"], x["detected"]) for x in tt["results"]]))
    rob = Robot(0, HonestStrategy(cfg), ch, c, cfg, np.random.default_rng(0), True, True, 0)
    attrs = [a for a in vars(rob) if any(k in a.lower() for k in ("byz", "truth", "label"))]
    ok("robot_has_no_truth_attrs", not attrs, str(attrs))
    names = set(L5Scorer.score.__code__.co_names) | set(L5Scorer._read.__code__.co_names)
    import inspect
    swarm_src = "".join(inspect.getsource(c_) for c_ in (Robot, Contract, Chain, Observation, HonestStrategy,
                                                           ByzantineBase, NaiveByzantine, SmartByzantine))
    ok("I6_structural_no_truth_reads_in_swarm_code",
       not any(tok in swarm_src for tok in ("_truth", "truth.json", "TruthVault", "labels", "isinstance")))
    byz_src = inspect.getsource(ByzantineBase) + inspect.getsource(SmartByzantine) + inspect.getsource(NaiveByzantine)
    ok("adversary_cannot_identify_honest_kind",
       not any(tok in byz_src for tok in ("_strategy", "honest", "Honest", "label")) and
       set(vars(Observation(9, 0, 0, fake, 2, None))) == {"id", "white", "black", "mean", "removed", "recent", "rng"})
    dsc = L5Scorer(os.path.join(scratch, "det1")).score()
    ok("scorer_scores_every_tick", dsc["ticks_scored"] == 1200 and "byz_share_eligible_gt_half_any_tick" in dsc)
    ok("scorer_uses_no_swarm_classes", not (names & {"Robot", "World", "Contract", "Chain", "TruthVault"}),
       str(sorted(names & {"Robot", "World", "Contract", "Chain"})))
    return {"stamp": STAMP, "harness": HARNESS, "tests": out, "n": len(out),
            "passed": sum(1 for t in out if t["pass"]), "all_pass": all(t["pass"] for t in out), "tamper": tt}


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

STR_OPTS = ("propose_denominator", "collusion_mode", "collusion_linkage", "schedule_mode", "final_window_policy",
            "mean_mode", "clique_limit_mode", "seal_mode")
FLOAT_OPTS = ("collusion_tol", "smart_noise", "speed_mps")
INT_OPTS = ("recent_rounds", "estimate_interval", "eval_interval", "timesteps")


def _add_fidelity_flags(p):
    for k in STR_OPTS:
        p.add_argument("--" + k.replace("_", "-"))
    for k in FLOAT_OPTS:
        p.add_argument("--" + k.replace("_", "-"), type=float)
    for k in INT_OPTS:
        p.add_argument("--" + k.replace("_", "-"), type=int)
    p.add_argument("--no-empty-votes", action="store_true")
    p.add_argument("--no-recents", action="store_true")


def _overrides(a):
    o = {k: getattr(a, k) for k in STR_OPTS + FLOAT_OPTS + INT_OPTS if getattr(a, k) is not None}
    if a.no_empty_votes:
        o["submit_empty_votes"] = False
    if a.no_recents:
        o["clique_recents"] = False
    return o


def main_direct(argv):
    p = argparse.ArgumentParser(prog="swarm_r0.py", description="Arm A condition runner (" + STAMP + ")")
    p.add_argument("--exp", type=int, choices=[1, 2, 3], required=True)
    p.add_argument("--alpha", type=int, choices=[1, 10], required=True)
    p.add_argument("--byz", choices=["naive", "smart"], required=True)
    p.add_argument("--runs", type=int, required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--k", type=float, default=DEFAULTS["k_std"], help="ASSUMPTION-5 (default 2.0)")
    p.add_argument("--out", help="default runs/exp{E}_{byz}_a{A}")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--no-resim", action="store_true", help="skip byte-identical re-simulation check")
    _add_fidelity_flags(p)
    a = p.parse_args(argv)
    out = a.out or os.path.join("runs", "exp%d_%s_a%d" % (a.exp, a.byz, a.alpha))
    m = run_condition(a.exp, a.alpha, a.byz, a.runs, a.seed, a.k, out, a.workers, not a.no_resim, _overrides(a))
    print(json.dumps({"stamp": STAMP, "out": os.path.abspath(out), "engineering_validation": m["engineering_validation"],
                      "aggregate_over_validated_runs": m["aggregate_over_validated_runs"],
                      "byz_share_eligible_gt_half_any_tick_runs": m["byz_share_eligible_gt_half_any_tick_runs"]},
                     indent=1, sort_keys=True))
    return 0 if m["engineering_validation"]["runs_validated"] == m["engineering_validation"]["runs_total"] else 1


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0].startswith("--") and argv[0] not in ("--help", "-h"):
        return main_direct(argv)
    p = argparse.ArgumentParser(prog="swarm_r0.py", description="Arm A DAO open-swarm harness (" + STAMP + "). "
                                "Direct form: swarm_r0.py --exp E --alpha A --byz B --runs N --seed S --k K")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run", help="single run -> OUT/{ledger.jsonl,truth.json,meta.json,score.json}")
    pr.add_argument("--exp", type=int, choices=[1, 2, 3], required=True)
    pr.add_argument("--byz", choices=["naive", "smart"], required=True)
    pr.add_argument("--alpha", type=int, required=True)
    pr.add_argument("--seed", type=int, required=True)
    pr.add_argument("--k", type=float, default=DEFAULTS["k_std"])
    pr.add_argument("--out", required=True)
    _add_fidelity_flags(pr)
    pv = sub.add_parser("replay", help="engineering validation (+ --full byte-identical re-simulation)")
    pv.add_argument("--run", required=True)
    pv.add_argument("--full", action="store_true")
    ps = sub.add_parser("score", help="L5 scorer")
    ps.add_argument("--run", required=True)
    pt = sub.add_parser("tamper-test")
    pt.add_argument("--run", required=True)
    pt.add_argument("--scratch", required=True)
    pg = sub.add_parser("r0-gate", help="evaluate R0 over ROOT/exp{E}_{byz}_a{A}/metrics.json")
    pg.add_argument("--root", required=True)
    pst = sub.add_parser("selftest")
    pst.add_argument("--scratch", required=True)
    sub.add_parser("assumptions")
    a = p.parse_args(argv)
    if a.cmd == "run":
        cfg = make_config(experiment=a.exp, byz=a.byz, alpha=a.alpha, seed=a.seed, k_std=a.k, **_overrides(a))
        run_one(cfg, a.out)
        sc = L5Scorer(a.out).score()
        with open(os.path.join(a.out, "score.json"), "w") as f:
            json.dump(sc, f, indent=1, sort_keys=True)
        print(json.dumps(sc, indent=1, sort_keys=True))
        return 0
    if a.cmd == "replay":
        r = verify_ledger(a.run, full_resim=a.full)
        print(json.dumps(r, indent=1, sort_keys=True))
        return 0 if r["ok"] else 1
    if a.cmd == "score":
        print(json.dumps(L5Scorer(a.run).score(), indent=1, sort_keys=True))
        return 0
    if a.cmd == "tamper-test":
        r = tamper_test(a.run, a.scratch)
        print(json.dumps(r, indent=1, sort_keys=True))
        return 0 if r["all_detected"] else 1
    if a.cmd == "r0-gate":
        g = r0_gate(os.path.abspath(a.root))
        with open(os.path.join(a.root, "r0_gate.json"), "w") as f:
            json.dump(g, f, indent=1, sort_keys=True)
        print(json.dumps(g, indent=1, sort_keys=True))
        return 0 if g["R0_status"] == "R0 PASS" else 3
    if a.cmd == "selftest":
        r = selftest(a.scratch)
        print(json.dumps(r, indent=1, sort_keys=True))
        return 0 if r["all_pass"] else 1
    if a.cmd == "assumptions":
        print("\n".join([STAMP] + ASSUMPTIONS))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
