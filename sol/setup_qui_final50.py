#!/usr/bin/env python3
"""Final spinup (Yuan et al. 2023 phase 2): 50 years, normal decomposition (spinup_state = 0), 1850 conditions,
from the task-7 year-20 restart (520 AD years in all). Same history fields and parameters as qui_ref20."""
from pathlib import Path
import os, re, runpy, subprocess


VARIANT = os.environ.get('QUI_VARIANT', 'fix')        # 'fix': accepted switches on; 'pub': all fix switches 0 (published code)
SWITCHES = ['fix_dom_n', 'fix_co2_dt', 'fix_ch4_unsat', 'fix_finund_repart', 'fix_unsat_surf', 'fix_micfin_agg', 'fix_lat_weights']
def variant_params(params):
    if VARIANT in ('fix', 'npp'):
        for sw in SWITCHES[2:]:
            assert re.search(rb'^' + sw.encode() + rb'\s+1\s*$', params, re.M), sw
        assert not re.search(rb'^fix_nppratio\s', params, re.M)
        return params if VARIANT == 'fix' else params.rstrip(b'\n') + b'\nfix_nppratio\t1\n'
    for sw in SWITCHES:
        params, n = re.subn(rb'^' + sw.encode() + rb'\s+1\s*$', sw.encode() + b'\t0', params, flags=re.M)
        assert n == 1, sw
    return params
name = 'qui_final50' + {'fix': '', 'pub': '_pub', 'npp': '_npp'}[VARIANT]
os.environ['CH4REPORT_CASE'] = name
runpy.run_path('/work/CLM_SPRUCE/sol/setup_qui_task4.py', run_name='__main__')
case = Path('/work/cases')/name
p = case/'user_nl_clm'
t = p.read_text().rstrip()+",\n 'CH4_AERE_DEPTH_UNSAT', 'CH4_EBUL_DEPTH_UNSAT'\n"
fin = '/work/runs/qui_ref20/qui_ref20.clm2.r.0021-01-01-00000.nc' if VARIANT in ('fix', 'npp') else '/work/inputs/scratch/jmarindi/elm_work/runs/qui_ad500_restart/qui_microbe.clm2.r.0501-01-01-00000.nc'
assert Path(fin).exists()
t, n1 = re.subn(r"^ finidat = .*$", f" finidat = '{fin}'", t, flags=re.M)
t, n2 = re.subn(r"^ spinup_state = 1$", " spinup_state = 0", t, flags=re.M)
assert n1 == 1 and n2 == 1
p.write_text(t)
subprocess.run(['./xmlchange', 'STOP_OPTION=nyears,STOP_N=50,REST_OPTION=nyears,REST_N=10'], cwd=case, check=True)
params = variant_params(Path('/work/results/qui_ref20/microbepar_in').read_bytes())
(case/'microbepar_in').write_bytes(params)
subprocess.run(['./preview_namelists'], cwd=case, check=True)
with (case/'build_out.txt').open('w') as log:
    subprocess.run([f'./{name}.build'], cwd=case, stdout=log, stderr=subprocess.STDOUT, check=True)
