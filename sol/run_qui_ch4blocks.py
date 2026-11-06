#!/usr/bin/env python3
"""Run instrumented fix-on branch and retain all diagnostic and provenance artifacts."""
from pathlib import Path
import subprocess
import os
import hashlib
import json
import shutil

root = Path('/work')
name=os.environ.get('CH4BLOCK_CASE','qui_ch4bud_blocks')
run = root/'runs'/name
case = root/'cases'/name
src = root/'CLM_SPRUCE'
out = root/'results/qui_ch4bud_blocks'
out.mkdir()  # Never overwrite an existing result.
exe=run/'bld/cesm.exe'
symbols=subprocess.check_output(['strings',str(exe)],text=True)
for name in ['CH4BUD_RES_CLIP_SAT','CH4BUD_RES_REPORT_UNSAT','CH4BUD_NORM_RES_SAT','fix_finund_repart']:
    assert name in symbols, name
assert (run/'microbepar_in').read_bytes()==(root/'results/qui_finund_repart/on/microbepar_in').read_bytes()
metadata=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=src,text=True).strip(),
              executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
              restart_sha256=hashlib.sha256((root/'inputs/scratch/jmarindi/elm_work/runs/qui_ad500_restart/qui_microbe.clm2.r.0501-01-01-00000.nc').read_bytes()).hexdigest())
(out/'provenance.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(metadata,flush=True)
(run/'timing/checkpoints').mkdir(parents=True,exist_ok=True)
with (run/'cesm.log').open('w') as log:
    subprocess.run(['mpiexec','-n','1',str(exe)],cwd=run,stdout=log,stderr=subprocess.STDOUT,
                   env={**os.environ,'OMP_NUM_THREADS':'1'},check=True)
assert any('SUCCESSFUL TERMINATION' in p.read_text() for p in run.glob('cpl.log.*'))
for p in run.iterdir():
    if p.is_file() and ('.h0.' in p.name or '.h1.' in p.name or '.log' in p.name or
                       p.name.endswith('_in') or p.name.endswith('.nml') or
                       p.name.startswith('datm.streams') or p.name=='microbepar_in'):
        shutil.copy2(p,out/p.name)
prov=out/'provenance'
prov.mkdir()
for name in ['env_build.xml','env_run.xml','user_nl_clm','user_nl_datm','Macros','build_out.txt']:
    shutil.copy2(case/name,prov/name)
print('Five-year diagnostic replay completed successfully',flush=True)
