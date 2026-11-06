#!/usr/bin/env python3
"""Task 7: run the 20-year reference case from the year-500 restart and archive outputs."""
from pathlib import Path
import hashlib, json, re, shutil, subprocess, os

root = Path('/work')
src = root/'CLM_SPRUCE'
case = root/'cases/qui_ref20'
run = root/'runs/qui_ref20'
exe = run/'bld/cesm.exe'
out = root/'results/qui_ref20'
symbols = subprocess.check_output(['strings', str(exe)], text=True)
required = ['fix_lat_weights', 'lat_hum_wt', 'fix_micfin_agg', 'fix_unsat_surf', 'CH4BUD_RES_REPORT_UNSAT']
assert all(x in symbols for x in required)
params = (case/'microbepar_in').read_bytes()
assert (run/'microbepar_in').read_bytes() == params
out.mkdir()
prov = out/'provenance'; prov.mkdir()
for name in ['env_build.xml', 'env_run.xml', 'user_nl_clm', 'user_nl_datm', 'Macros', 'build_out.txt']:
    shutil.copy2(case/name, prov/name)
rst = root/'inputs/scratch/jmarindi/elm_work/runs/qui_ad500_restart/qui_microbe.clm2.r.0501-01-01-00000.nc'
meta = dict(source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=src, text=True).strip(),
            executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
            restart_sha256=hashlib.sha256(rst.read_bytes()).hexdigest(),
            parameter_sha256=hashlib.sha256(params).hexdigest(),
            platform='Mac Docker image elm-local (Ubuntu 24.04 ARM64, GNU 13.3, MPICH 4.2), 1 process')
(out/'provenance.json').write_text(json.dumps(meta, indent=2)+'\n')
(run/'timing/checkpoints').mkdir(parents=True, exist_ok=True)
with (run/'cesm.log').open('w') as log:
    subprocess.run(['mpiexec', '-n', '1', str(exe)], cwd=run, stdout=log, stderr=subprocess.STDOUT,
                   env={**os.environ, 'OMP_NUM_THREADS': '1'}, check=True)
assert any('SUCCESSFUL TERMINATION' in p.read_text(errors='replace') for p in run.glob('cpl.log.*'))
lnd = ''.join(p.read_text(errors='replace') for p in run.glob('lnd.log.*'))
for sw in ['fix_ch4_unsat', 'fix_finund_repart', 'fix_unsat_surf', 'fix_micfin_agg', 'fix_lat_weights']:
    assert re.search(sw + r'\s*=\s*T', lnd), sw
for p in run.iterdir():
    if p.is_file() and ('.h0.' in p.name or '.h1.' in p.name or '.log' in p.name or p.name.endswith('_in')
                        or p.name.endswith('.nml') or p.name.startswith('datm.streams')):
        shutil.copy2(p, out/p.name)
print('successful termination', flush=True)
