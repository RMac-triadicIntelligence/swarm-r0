#!/usr/bin/env bash
# Corrected v0.2.0 matrix. Seed S=20261107 and k=2 were fixed before running (ASSUMPTION-5); never tuned.
set -u
cd "$(dirname "$0")"
for e in 1 2 3; do for b in naive smart; do for a in 1 10; do
  ./run_cmd.sh "exp${e}_${b}_a${a}" bash -c "python3 swarm_r0.py --exp $e --alpha $a --byz $b --runs 10 --seed 20261107 --k 2 --workers 7 --out outputs/matrix/exp${e}_${b}_a${a} > outputs/matrix/exp${e}_${b}_a${a}.stdout.json"
done; done; done
./run_cmd.sh r0_gate bash -c "python3 swarm_r0.py r0-gate --root outputs/matrix > outputs/matrix/r0_gate.stdout.json"
