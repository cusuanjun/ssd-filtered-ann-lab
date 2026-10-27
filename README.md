# SSD Filtered ANN Lab

Course experiment by Meng Jingxuan. GateANN metadata-only adaptive search budget,
with measured results rather than an assumed speedup. The baseline course workload
contains 1M 192-dimensional uint8 vectors, three label-selectivity buckets, and
200 queries per bucket. All reported configurations use one thread, beamwidth 8,
K=10, Linux AIO, and GateANN FullAdj=32.

## Results

54 supplementary trials were run on 2026-10-27: five fixed budgets times three
buckets times three repetitions, plus the adaptive policy on three buckets times
three repetitions. Order was shuffled with seed 20261027 before the formal runs.

| Bucket | Fixed L=320 Recall | Adaptive Recall | Fixed latency us | Adaptive latency us |
|---|---:|---:|---:|---:|
| Low | 34.30% | 72.95% | 773.4 | 3174.6 |
| Medium | 72.05% | 88.75% | 865.1 | 1620.7 |
| High | 93.20% | 94.05% | 1191.9 | 1273.9 |

Numbers are medians of three trials. This prototype improves recall at additional
latency, not a universal speedup or a demonstrated Pareto improvement over tuned
fixed budgets. The source policy reads no ground truth. The original evaluator
still loads ground truth solely to evaluate returned results after search.

## Build and Enable

Requires the course dependencies and index. Do not replace the original baseline.
From this repository directory:

```bash
git clone https://github.com/GyuyeongKim/GateANN-public.git GateANN-adaptive
git -C GateANN-adaptive checkout 71e87cbf0e25c0400c0109dd25a64a7c4dccc9dd
git -C GateANN-adaptive apply ../gateann_aio_compat.patch
git -C GateANN-adaptive apply --ignore-space-change ../optimization.patch
cp adaptive_budget.h GateANN-adaptive/tests/
cmake -S GateANN-adaptive -B GateANN-adaptive/build -DUSE_AIO=ON -DCMAKE_BUILD_TYPE=Release
cmake --build GateANN-adaptive/build --target search_disk_index_yfcc -j 4
```

Use the original query arguments and the new binary. Set `GATEANN_ADAPTIVE=1`
to enable; **unset** this variable to disable. Any defined value enables the
policy, including `0`. Base L=320 is the evaluated configuration.

For N base points, evaluate up to 1024 evenly spaced metadata rows. Let s be the
matching fraction; set L to ceil(max(320,320*sqrt(0.10/max(s,1/1024)))/32)*32,
capped at 4096. Sampling occurs inside the original timed query loop. Internal
stage counters do not include that new sampling cost, but QPS does. There is no
index rebuild, label-specific ground-truth tuning, or traversal-rule change.

## Tests

```bash
g++ -std=c++17 -Wall -Wextra -fsanitize=address,undefined test_budget.cpp -o test_budget
./test_budget
```

Bounds, monotonicity, rounding, null predicates, empty stores, sampling indices,
and determinism pass. Debug High: baseline/disabled Recall=96.40%, adaptive=96.55%.
This is not a claim of exhaustive per-ID or multi-thread correctness.

`run_study.py` reproduces the historical experiment using the course directory
specified by `FVS_ROOT` (default `/home/mengjingxuan/fvs-course-lab`) and its saved
20260916 command manifests when present; otherwise it constructs the same arguments
from the standard course directory layout. It refuses to overwrite an existing
source/output directory. The saved plan is in `data/plan.json`. Each formal
process executes only one L. The first debug parsing attempt accidentally supplied
L twice, was rejected, and was excluded before formal testing. The parser is fixed.

Public CSVs contain aggregate measurements; private raw logs, hardware snapshots,
and query/index data are retained separately and are not uploaded. Run
`python3 analyze_study.py` (requires pandas, numpy, matplotlib) to reproduce the
figures and summaries from the public CSVs. No raw measurements are overwritten.

## Scope and Sources

Fixed-L recall rises from 20.90 to 83.75% on Low when L rises from 160 to 2560.
This supports a budget-coverage limitation but does not isolate topology/PQ causes.
The adaptive Low point does not dominate fixed L=1280. Caches and shared-system
load were not strictly controlled; no cold-cache claim is made. GateANN latency
uses 1e6 divided by its rounded integer QPS. Logical I/O is not device I/O.

- PipeANN: https://www.usenix.org/conference/osdi25/presentation/guo
- PipeANN-Filter: https://arxiv.org/abs/2605.17992
- GateANN: https://arxiv.org/abs/2603.21466
- Course: https://gitee.com/wei-fangyu/fvs-course-lab

Upstream code and the course compatibility patch retain their original licensing.
This package contains the small integration diff, not a relicensed upstream tree.
