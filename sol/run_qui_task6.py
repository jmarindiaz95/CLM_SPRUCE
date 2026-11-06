#!/usr/bin/env python3
"""Task 6: matched five-year branches; only fix_micfin_agg differs. fix_unsat_surf=1 in both."""
from pathlib import Path
import hashlib, json, re, shutil, subprocess, os

root = Path('/work')
src = root/'CLM_SPRUCE'
case = root/'cases/qui_ch4bud_task6'
template = root/'runs/qui_ch4bud_task6'
exe = template/'bld/cesm.exe'
out = root/'results/qui_micfin_agg'
symbols = subprocess.check_output(['strings', str(exe)], text=True)
required = ['fix_micfin_agg', 'fix_unsat_surf', 'CH4BUD_RES_REPORT_UNSAT', 'CH4BUD_PRE_INIT_SAT']
assert all(x in symbols for x in required)
base = (root/'results/qui_unsat_surf/on/microbepar_in').read_bytes()   # accepted task-5 'on' parameters
assert re.search(rb'^fix_unsat_surf\s+1', base, re.M)
assert not re.search(rb'^fix_micfin_agg\s', base, re.M)
out.mkdir()
prov = out/'provenance'; prov.mkdir()
for name in ['env_build.xml', 'env_run.xml', 'user_nl_clm', 'user_nl_datm', 'Macros', 'build_out.txt']:
    shutil.copy2(case/name, prov/name)
rst = root/'inputs/scratch/jmarindi/elm_work/runs/qui_ad500_restart/qui_microbe.clm2.r.0501-01-01-00000.nc'
meta = dict(source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=src, text=True).strip(),
            executable_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
            restart_sha256=hashlib.sha256(rst.read_bytes()).hexdigest(),
            platform='Claude cloud workspace, Ubuntu x86_64, apt GNU/MPICH/NetCDF, 1 process per branch',
            branches={})
procs = {}
for label, value in [('off', 0), ('on', 1)]:
    run = root/f'runs/qui_micfin_agg_{label}'
    run.mkdir(); (run/'timing/checkpoints').mkdir(parents=True)
    for p in template.iterdir():
        if p.is_file() and (p.name.endswith('_in') or p.name.endswith('.nml') or
                            p.name.startswith('datm.streams') or p.name == 'seq_maps.rc'):
            (run/p.name).write_text(p.read_text().replace(str(template), str(run)))
    params = base + f'\nfix_micfin_agg\t{value}\n'.encode()
    (run/'microbepar_in').write_bytes(params)
    meta['branches'][label] = dict(fix_micfin_agg=value, parameter_sha256=hashlib.sha256(params).hexdigest())
    log = (run/'cesm.log').open('w')
    procs[label] = (subprocess.Popen(['mpiexec', '-n', '1', str(exe)], cwd=run, stdout=log,
                                     stderr=subprocess.STDOUT, env={**os.environ, 'OMP_NUM_THREADS': '1'}), run, value)
(out/'provenance.json').write_text(json.dumps(meta, indent=2)+'\n')
for label, (pr, run, value) in procs.items():
    assert pr.wait() == 0, label
    assert any('SUCCESSFUL TERMINATION' in p.read_text(errors='replace') for p in run.glob('cpl.log.*'))
    assert any(re.search(r'fix_micfin_agg\s*=\s*'+('T' if value else 'F'), p.read_text(errors='replace'))
               for p in run.glob('lnd.log.*'))
    dest = out/label; dest.mkdir()
    for p in run.iterdir():
        if p.is_file() and ('.h0.' in p.name or '.h1.' in p.name or '.log' in p.name or p.name.endswith('_in')
                            or p.name.endswith('.nml') or p.name.startswith('datm.streams')):
            shutil.copy2(p, dest/p.name)
    print(f'{label}: successful termination', flush=True)
