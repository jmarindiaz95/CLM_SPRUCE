#!/usr/bin/env python3
"""Run matched five-year branches; only fix_unsat_surf differs between parameters."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess

root = Path('/work')
src = root/'CLM_SPRUCE'
case = root/'cases/qui_ch4bud_task5'
template = root/'runs/qui_ch4bud_task5'
exe = template/'bld/cesm.exe'
out = root/'results/qui_unsat_surf'
symbols = subprocess.check_output(['strings',str(exe)],text=True)
required = ['fix_unsat_surf','CH4BUD_RES_REPORT_UNSAT','CH4BUD_PRE_INIT_SAT']
assert all(x in symbols for x in required)
base = (root/'results/qui_ch4bud_task4/microbepar_in').read_bytes()
assert (template/'microbepar_in').read_bytes() == base
assert not re.search(rb'^fix_unsat_surf\s',base,re.M)
out.mkdir()  # Refuse to overwrite any previous experiment.
prov=out/'provenance'
prov.mkdir()
for name in ['env_build.xml','env_run.xml','user_nl_clm','user_nl_datm','Macros','build_out.txt']:
    shutil.copy2(case/name,prov/name)
(prov/'strings_check.txt').write_text('\n'.join(required)+'\n')
metadata = dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=src,text=True).strip(),
                executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                restart_sha256=hashlib.sha256((root/'inputs/scratch/jmarindi/elm_work/runs/qui_ad500_restart/qui_microbe.clm2.r.0501-01-01-00000.nc').read_bytes()).hexdigest(),
                executable=str(exe), branches={})
for label,value in [('off',0),('on',1)]:
    run=root/f'runs/qui_unsat_surf_{label}'
    run.mkdir()
    (run/'timing/checkpoints').mkdir(parents=True)
    for p in template.iterdir():
        if p.is_file() and (p.name.endswith('_in') or p.name.endswith('.nml') or
                           p.name.startswith('datm.streams') or p.name=='seq_maps.rc'):
            (run/p.name).write_text(p.read_text().replace(str(template),str(run)))
    params=base+f'\nfix_unsat_surf\t{value}\n'.encode()
    (run/'microbepar_in').write_bytes(params)
    metadata['branches'][label]=dict(fix_unsat_surf=value,parameter_sha256=hashlib.sha256(params).hexdigest())
    (out/'provenance.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(f'Running {label}: fix_unsat_surf={value}',flush=True)
    with (run/'cesm.log').open('w') as log:
        subprocess.run(['mpiexec','-n','1',str(exe)],cwd=run,stdout=log,stderr=subprocess.STDOUT,
                       env={**os.environ,'OMP_NUM_THREADS':'1'},check=True)
    assert any('SUCCESSFUL TERMINATION' in p.read_text(errors='replace') for p in run.glob('cpl.log.*'))
    assert any(re.search(r'fix_unsat_surf\s*=\s*'+('T' if value else 'F'),p.read_text(errors='replace')) for p in run.glob('lnd.log.*'))
    dest=out/label
    dest.mkdir()
    for p in run.iterdir():
        if p.is_file() and ('.h0.' in p.name or '.h1.' in p.name or '.log' in p.name or
                           p.name.endswith('_in') or p.name.endswith('.nml') or
                           p.name.startswith('datm.streams') or p.name=='seq_maps.rc'):
            shutil.copy2(p,dest/p.name)
    print(f'{label}: successful termination',flush=True)
