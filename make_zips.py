#!/usr/bin/env python3
"""Build core and full zips with stdlib zipfile (the zip CLI is not installed). Excludes *.zip and ZIP_SHA256SUMS."""
import glob, os, zipfile
core = ["swarm_r0.py","run_cmd.sh","run_matrix.sh","annotate_r0.py","make_zips.py","README.md","RESULTS.md","ASSUMPTIONS.md",
        "CHANGELOG.md","COMPLIANCE.md","SECRET_SCAN.md","SHA256SUMS","outputs/COMMANDS.log","outputs/swarm_r0.py.sha256",
        "outputs/selftest.json","outputs/tamper_test_exp2_smart_a10_run00.json","outputs/annotate_r0.stdout.json",
        "outputs/matrix/r0_gate.json"] + sorted(glob.glob("outputs/xproc_replay_*.json")) + sorted(glob.glob("outputs/post_annotate_replay*.json")) \
       + sorted(glob.glob("outputs/matrix/*.stdout.json")) + sorted(glob.glob("outputs/matrix/*/metrics.json"))
core += sorted(p for p in glob.glob("source/**", recursive=True) if os.path.isfile(p))
full = sorted(os.path.relpath(os.path.join(d, f)) for d, _, fs in os.walk(".") for f in fs
              if ".zip" not in f and "box-store-snap" not in f and f != "ZIP_SHA256SUMS")
for name, files in (("swarm-r0-v0.2.0-core.zip", core), ("swarm-r0-v0.2.0-full.zip", full)):
    with zipfile.ZipFile(name, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, "swarm-r0-2026-11-07/" + p)
    print(name, len(files))
