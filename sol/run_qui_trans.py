#!/usr/bin/env python3
"""Transient 1980-2020: run qui_trans and archive h0, logs and h1 for 2018-2019."""
from pathlib import Path
import hashlib, json, re, shutil, subprocess, os

root = Path('/work')
V = {'fix': '', 'pub': '_pub', 'npp': '_npp', 'yuan': '_yuan'}[os.environ.get('QUI_VARIANT', 'fix')]
src = root/'CLM_SPRUCE'
case = root/f'cases/qui_trans{V}'
run = root/f'runs/qui_trans{V}'
exe = run/'bld/cesm.exe'
out = root/f'results/qui_trans{V}'
symbols = subprocess.check_output(['strings', str(exe)], text=True)
required = ['fix_nppratio', 'fix_lat_weights', 'lat_hum_wt', 'fix_micfin_agg', 'fix_unsat_surf', 'CH4BUD_RES_REPORT_UNSAT']
assert all(x in symbols for x in required)
params = (case/'microbepar_in').read_bytes()
assert (run/'microbepar_in').read_bytes() == params
assert (run/'datm.global1val.streams.co2.txt').exists()
out.mkdir()
prov = out/'provenance'; prov.mkdir()
for name in ['env_build.xml', 'env_run.xml', 'user_nl_clm', 'user_nl_datm', 'Macros', 'build_out.txt']:
    shutil.copy2(case/name, prov/name)
rst = root/f'runs/qui_final50{V}/qui_final50{V}.clm2.r.0051-01-01-00000.nc'
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
    assert re.search(sw + r'\s*=\s*' + ('F' if V == '_pub' else 'T'), lnd), sw
assert re.search(r'fix_nppratio\s*=\s*' + ('T' if V in ('_npp', '_yuan') else 'F'), lnd)
for sw in ['fix_finund_ponded', 'fix_finund_rates', 'fix_finund_hum_datum']:
    assert re.search(sw + r'\s*=\s*' + ('T' if V == '_yuan' else 'F'), lnd), sw
for p in run.iterdir():
    keep_h1 = '.h1.' in p.name and p.name.split('.h1.')[1][:4] in ('2018', '2019')
    if p.is_file() and ('.h0.' in p.name or keep_h1 or '.log' in p.name or p.name.endswith('_in')
                        or p.name.endswith('.nml') or p.name.startswith('datm.streams') or p.name.startswith('datm.global1val')):
        shutil.copy2(p, out/p.name)
print('successful termination', flush=True)
