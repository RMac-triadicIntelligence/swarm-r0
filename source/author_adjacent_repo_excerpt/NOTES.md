STATE STAMP: SEED-v0.1 cdc788b1996bd923d48a034b28f58ee728ce10d82924724c722b2b7be7e719f5

# Author-adjacent public code consulted (secondary grounding only)

Repo: https://github.com/rainazakir/size_regulation  (first author's GitHub account)
Commit: 6822f544985cba01614ab5d27cdf8e9ed8aadfad (2026-05-10 21:32:37 +0200 = 2026-05-10 14:32 CDT)
README title: "Mitigating Latency and Partitioning through Size Regulation in Blockchain-Enabled Robot Swarms" (ANTS 2026 submission).
It is NOT the paper's code. The paper's Data Availability URL https://github.com/rainazakir/dao returned HTTP 404 on 2026-11-07 (checked 08:5x CST).
The repo has no LICENSE file, so no files are copied here; only parameter values are cited.

Values read (file:line):
- HelloWorld/experimentconfig.sh:81  MEANTYPE "0" normal or "0.09" smart byzantine
- HelloWorld/experimentconfig.sh:82  BLOCKWAIT=5  (block wait for getting votes)
- HelloWorld/experimentconfig.sh:83  ALPHA=1
- HelloWorld/experimentconfig.sh:84  whichfuntion="adaptive"
- HelloWorld/experimentconfig.sh:86  collusiontolerance=0.007
- HelloWorld/experimentconfig.sh:87  k=2  ("std tolerance, applicable for adaptive")
- HelloWorld/experimentconfig.sh:88  thresholdcheck=0.07 ("only for simple thresholding")
- HelloWorld/experimentconfig.sh:79  NEWROUNDTIMER=15
- toychain/src/Block.py:142,281  ticketPrice = 40 ; :305-307 UBI 20 tokens at block heights [0,2,4,8,...,16384]
- toychain/src/Block.py:351,373  estimate needs balance > 39, deducts 40
- toychain/src/Block.py:369      estimate stored round(estimate, 3)
- toychain/src/Block.py:376      round closes when entries >= robotCount/2 and robotCount > 4
- toychain/src/Block.py:499-583  running (cumulative) mean; removed robots' past votes subtracted; payout 40 to each counted robot
- toychain/src/Block.py:534-543  ALPHA applied as "rounds participated" for robots with id > 380 (estimate eligibility, not vote eligibility)
- HelloWorld/controllers/main.py:411  honest estimate = (0.5+white)/(white+black+1)
