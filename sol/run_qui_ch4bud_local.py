#!/usr/bin/env python3
"""Prepare and run matched five-year repartition branches in the local container."""
from pathlib import Path
import hashlib
import shutil
import subprocess
import re
import os

root = Path('/work')
template = root / 'runs/qui_microbe_local'
exe = template / 'bld/cesm.exe'
out = root / 'results/qui_finund_repart'
out.mkdir(parents=True, exist_ok=True)
assert exe.is_file()
symbols = subprocess.check_output(['strings', str(exe)], text=True)
assert 'fix_finund_repart' in symbols and 'CH4BUD_RESX_SAT' in symbols
print('Executable SHA256:', hashlib.sha256(exe.read_bytes()).hexdigest(), flush=True)

for label, switch in [('off', 0), ('on', 1)]:
    run = root / f'runs/qui_finund_{label}'
    run.mkdir()  # Refuse to overwrite an existing experiment.
    (run / 'timing/checkpoints').mkdir(parents=True)
    for p in template.iterdir():
        if p.is_file() and (p.name.endswith('_in') or p.name.endswith('.nml') or
                           p.name.startswith('datm.streams') or p.name == 'seq_maps.rc'):
            text = p.read_text().replace(str(template), str(run))
            (run / p.name).write_text(text)
    params = (root / 'CLM_SPRUCE/inputdata/lnd/clm2/paramdata/microbepar_in_qui').read_text()
    for key, value in [('frac_ch4aom', '1.0'), ('m_dGrowRAOMMethanotrophs', '0.0')]:
        params, count = re.subn(rf'^{key}\s+.*$', f'{key}\t{value}', params, flags=re.M)
        assert count == 1
    params += f'\nfix_ch4_unsat\t1\nfix_finund_repart\t{switch}\n'
    (run / 'microbepar_in').write_text(params)
    assert 'finund_wt_only = .true.' in (run / 'lnd_in').read_text()
    dest = out / label
    dest.mkdir()
    for name in ['microbepar_in', 'lnd_in', 'drv_in', 'datm_in']:
        shutil.copy2(run / name, dest / name)
    print(f'Running {label}, fix_finund_repart={switch}', flush=True)
    with (run / 'cesm.log').open('w') as log:
        subprocess.run(['mpiexec', '-n', '1', str(exe)], cwd=run, stdout=log,
                       stderr=subprocess.STDOUT, env={**os.environ, 'OMP_NUM_THREADS': '1'}, check=True)
    for p in run.iterdir():
        if p.is_file() and ('.h0.' in p.name or '.h1.' in p.name or '.log' in p.name):
            shutil.copy2(p, dest / p.name)
    logs = list(run.glob('cpl.log.*'))
    assert logs and 'SUCCESSFUL TERMINATION' in logs[0].read_text()
    print(f'{label}: successful termination', flush=True)
