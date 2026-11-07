#!/usr/bin/env python3
"""Task 8: matched five-year branches; only fix_nppratio differs. All accepted fixes (incl. fix_lat_weights) on in both."""
from pathlib import Path
import hashlib, json, re, shutil, subprocess, os

root = Path('/work')
src = root/'CLM_SPRUCE'
case = root/'cases/qui_ch4bud_task8'
template = root/'runs/qui_ch4bud_task8'
exe = template/'bld/cesm.exe'
out = root/'results/qui_nppratio'
symbols = subprocess.check_output(['strings', str(exe)], text=True)
required = ['fix_nppratio', 'fix_lat_weights', 'fix_micfin_agg', 'fix_unsat_surf', 'CH4BUD_RES_REPORT_UNSAT', 'CH4BUD_PRE_INIT_SAT']
assert all(x in symbols for x in required)
base = (root/'results/qui_lat_weights/on/microbepar_in').read_bytes()   # accepted task-6b 'on' parameters
assert re.search(rb'^fix_unsat_surf\s+1', base, re.M)
assert re.search(rb'^fix_micfin_agg\s+1', base, re.M)
assert re.search(rb'^fix_lat_weights\s+1', base, re.M)
assert not re.search(rb'^fix_nppratio\s', base, re.M)
out.mkdir()
prov = out/'provenance'; prov.mkdir()
for name in ['env_build.xml', 'env_run.xml', 'user_nl_clm', 'user_nl_datm', 'Macros', 'build_out.txt']:
    shutil.copy2(case/name, prov/name)
rst = root/'inputs/scratch/jmarindi/elm_work/runs/qui_ad500_restart/qui_microbe.clm2.r.0501-01-01-00000.nc'
meta = dict(source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=src, text=True).strip(),
            executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
            restart_sha256=hashlib.sha256(rst.read_bytes()).hexdigest(),
            platform='Mac Docker image elm-local (Ubuntu 24.04 ARM64, GNU 13.3, MPICH 4.2), 1 process per branch',
            branches={})
procs = {}
for label, value in [('off', 0), ('on', 1)]:
    run = root/f'runs/qui_nppratio_{label}'
    run.mkdir(); (run/'timing/checkpoints').mkdir(parents=True)
    for p in template.iterdir():
        if p.is_file() and (p.name.endswith('_in') or p.name.endswith('.nml') or
                            p.name.startswith('datm.streams') or p.name == 'seq_maps.rc'):
            (run/p.name).write_text(p.read_text().replace(str(template), str(run)))
    params = base.rstrip(b'\n') + f'\nfix_nppratio\t{value}\n'.encode()
    (run/'microbepar_in').write_bytes(params)
    meta['branches'][label] = dict(fix_nppratio=value, parameter_sha256=hashlib.sha256(params).hexdigest())
    log = (run/'cesm.log').open('w')
    procs[label] = (subprocess.Popen(['mpiexec', '-n', '1', str(exe)], cwd=run, stdout=log,
                                     stderr=subprocess.STDOUT, env={**os.environ, 'OMP_NUM_THREADS': '1'}), run, value)
(out/'provenance.json').write_text(json.dumps(meta, indent=2)+'\n')
for label, (pr, run, value) in procs.items():
    assert pr.wait() == 0, label
    assert any('SUCCESSFUL TERMINATION' in p.read_text(errors='replace') for p in run.glob('cpl.log.*'))
    assert any(re.search(r'fix_nppratio\s*=\s*'+('T' if value else 'F'), p.read_text(errors='replace'))
               for p in run.glob('lnd.log.*'))
    dest = out/label; dest.mkdir()
    for p in run.iterdir():
        if p.is_file() and ('.h0.' in p.name or '.h1.' in p.name or '.log' in p.name or p.name.endswith('_in')
                            or p.name.endswith('.nml') or p.name.startswith('datm.streams')):
            shutil.copy2(p, dest/p.name)
    print(f'{label}: successful termination', flush=True)
