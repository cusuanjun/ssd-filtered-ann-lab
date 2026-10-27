"""Create an isolated GateANN build and collect randomized repeated trials."""
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('FVS_ROOT', '/home/mengjingxuan/fvs-course-lab'))
SOURCE = ROOT / 'systems/GateANN-public'
VARIANT = HERE / 'GateANN-adaptive'

def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

def build():
    if VARIANT.exists():
        raise RuntimeError('Isolated build already exists; do not overwrite an experiment')
    run(['git', 'clone', '--no-hardlinks', str(SOURCE), str(VARIANT)])
    run(['git', '-C', str(VARIANT), 'checkout', '71e87cbf0e25c0400c0109dd25a64a7c4dccc9dd'])
    run(['git', '-C', str(VARIANT), 'apply', str(ROOT / 'patches/gateann_aio_compat.patch')])
    shutil.copy2(HERE / 'adaptive_budget.h', VARIANT / 'tests/adaptive_budget.h')
    path = VARIANT / 'tests/search_disk_index_yfcc.cpp'
    raw = path.read_bytes()
    newline = '\r\n' if b'\r\n' in raw else '\n'
    text = raw.decode().replace('\r\n', '\n')
    edits = [
        ('#include <omp.h>', '#include <omp.h>\n#include <cstdlib>\n#include "adaptive_budget.h"'),
        ('  bool is_fa =', '  const bool adaptive = std::getenv("GATEANN_ADAPTIVE") != nullptr;\n  bool is_fa ='),
        ('      if (is_fa) {', '      const uint64_t query_L = (adaptive && is_fa) ? adaptive_budget(*idx_->get_spmat_filter(), ql, L) : L;\n      if (is_fa) {'),
        ('recall_at, mem_L, L,', 'recall_at, mem_L, query_L,'),
    ]
    for old, new in edits:
        if old not in text:
            raise RuntimeError('Expected code anchor missing: ' + old)
        text = text.replace(old, new)
    path.write_bytes(text.replace('\n', newline).encode())
    with (HERE / 'optimization.patch').open('w') as f:
        run(['git', '-C', str(VARIANT), 'diff', '--ignore-space-at-eol', '--', 'tests/search_disk_index_yfcc.cpp'], stdout=f)
    with (HERE / 'build.log').open('w') as f:
        run(['cmake', '-S', str(VARIANT), '-B', str(VARIANT / 'build'), '-DCMAKE_BUILD_TYPE=Release', '-DUSE_AIO=ON'], stdout=f, stderr=subprocess.STDOUT)
        run(['cmake', '--build', str(VARIANT / 'build'), '--target', 'search_disk_index_yfcc', '-j', '4'], stdout=f, stderr=subprocess.STDOUT)

def measure(bucket, repeat, kind, L, tier='formal_1000000'):
    old_id = '20260916-203453-r1' if tier.startswith('formal') else 'debug-check-20260916-202926'
    original = ROOT / 'course_runs/results/gateann' / tier / bucket / old_id / 'command.json'
    if original.exists():
        command = json.loads(original.read_text())['command'][:16] + [str(L)]
    else:
        dataset = ROOT / 'datasets/yfcc_course_v1' / tier
        workload = dataset / 'workloads' / bucket
        command = [str(SOURCE/'build/tests/search_disk_index_yfcc'), 'uint8',
                   str(ROOT/'course_runs/indices/gateann'/tier/'yfcc'), '1', '8',
                   str(workload/'query.u8bin'), str(dataset/'base.metadata.spmat'),
                   str(workload/'query.metadata.spmat'), str(workload/'ground_truth.ids.ibin'),
                   '10', 'l2', 'pq', '8', '0', '0', '32', str(L)]
    if kind in ('adaptive', 'disabled'):
        command[0] = str(VARIANT / 'build/tests/search_disk_index_yfcc')
    directory = HERE / 'runs' / tier / f'{bucket}_{kind}_L{L}_r{repeat}'
    directory.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.pop('GATEANN_ADAPTIVE', None)
    if kind == 'adaptive':
        env['GATEANN_ADAPTIVE'] = '1'
    start = time.time()
    with (directory / 'run.log').open('w') as f:
        proc = subprocess.run(['/usr/bin/time', '-f', '%M', '-o', str(directory / 'rss.txt'), *command], env=env, stdout=f, stderr=subprocess.STDOUT)
    metadata = dict(command=command, adaptive=kind == 'adaptive', exit_code=proc.returncode, elapsed_seconds=time.time()-start, start_utc=datetime.datetime.fromtimestamp(start, datetime.timezone.utc).isoformat(), loadavg=os.getloadavg())
    (directory / 'command.json').write_text(json.dumps(metadata, indent=2))
    if proc.returncode:
        raise RuntimeError(str(directory))
    found = []
    for line in (directory / 'run.log').read_text().splitlines():
        fields = line.split()
        if len(fields) == 8 and fields[0] == str(L):
            try:
                found.append([float(x) for x in fields])
            except ValueError:
                pass
    if len(found) != 1:
        raise RuntimeError('Unexpected results: ' + str(directory))
    _, qps, recall, ios, skips, io, tunnel, process = found[0]
    result = dict(tier=tier, bucket=bucket, repeat=repeat, variant=kind, L=L, recall_percent=100*recall, mean_latency_us=1e6/qps, qps=qps, mean_ios=ios, filter_skips=skips, io_time_us=io, tunnel_time_us=tunnel, process_time_us=process, peak_rss_kb=int((directory/'rss.txt').read_text()), elapsed_seconds=metadata['elapsed_seconds'])
    print(json.dumps(result), flush=True)
    return result

def main():
    if '--existing-build' not in sys.argv:
        build()
    debug = [measure('high', 2, k, 320, 'debug_100000') for k in ('baseline', 'disabled', 'adaptive')]
    assert abs(debug[0]['recall_percent']-debug[1]['recall_percent']) < 0.001
    assert debug[2]['recall_percent'] >= 80
    # Predeclare all variants and the order seed before seeing supplementary results.
    plan = [(b, r, 'baseline', L) for r in (1,2,3) for b in ('low','medium','high') for L in (160,320,640,1280,2560)]
    plan += [(b, r, 'adaptive', 320) for r in (1,2,3) for b in ('low','medium','high')]
    random.Random(20261027).shuffle(plan)
    (HERE/'plan.json').write_text(json.dumps(plan, indent=2))
    with (HERE/'results.csv').open('w', newline='') as f:
        writer = None
        for args in plan:
            row = measure(*args)
            if writer is None:
                writer = csv.DictWriter(f, fieldnames=list(row))
                writer.writeheader()
            writer.writerow(row)
            f.flush()
    (HERE/'debug_results.json').write_text(json.dumps(debug, indent=2))
    print('STUDY COMPLETE', flush=True)

if __name__ == '__main__':
    main()
