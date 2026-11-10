#!/usr/bin/env python3
"""Post-gate annotation: copies the computed R0 status from outputs/matrix/r0_gate.json into every
JSON output (except truth.json, whose hash is bound in the ledger footer). Ledgers (.jsonl) are untouched.
Does not change any measured value."""
import json, os, sys
root = sys.argv[1] if len(sys.argv) > 1 else "outputs"
g = json.load(open(os.path.join(root, "matrix", "r0_gate.json")))
st = g["R0_status"]
note = {"R0_status": st, "R0_source": "outputs/matrix/r0_gate.json",
        "R0_note": "Engineering validation (replay/hash/invariant checks) is NOT R0. R0 = paper direction at alpha=10; computed result above."}
n = 0
for dp, dn, fn in os.walk(root):
    for f in fn:
        if not f.endswith(".json") or f in ("truth.json", "annotate_r0.stdout.json"):
            continue
        p = os.path.join(dp, f)
        d = json.load(open(p))
        if isinstance(d, dict):
            d.update(note)
        else:
            d = {"data": d, **note}
        with open(p, "w") as fh:
            json.dump(d, fh, indent=1, sort_keys=True)
        n += 1
print(json.dumps({"annotated_files": n, **note}))
