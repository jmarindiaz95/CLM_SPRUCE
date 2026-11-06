#!/usr/bin/env python3
"""Task 7: 20-year reference case, all accepted fixes on, same outputs as task 6b (h1 half-hourly kept all years)."""
from pathlib import Path
import os
import re
import runpy
import shutil
import subprocess

name = 'qui_ref20'
os.environ['CH4REPORT_CASE'] = name
runpy.run_path('/work/CLM_SPRUCE/sol/setup_qui_task4.py', run_name='__main__')
case = Path('/work/cases')/name
p = case/'user_nl_clm'
p.write_text(p.read_text().rstrip()+",\n 'CH4_AERE_DEPTH_UNSAT', 'CH4_EBUL_DEPTH_UNSAT'\n")
subprocess.run(['./xmlchange', 'STOP_OPTION=nyears,STOP_N=20,REST_OPTION=nyears,REST_N=5'], cwd=case, check=True)
params = Path('/work/results/qui_lat_weights/on/microbepar_in').read_bytes()
for sw in ['fix_ch4_unsat', 'fix_finund_repart', 'fix_unsat_surf', 'fix_micfin_agg', 'fix_lat_weights']:
    assert re.search(rb'^' + sw.encode() + rb'\s+1\s*$', params, re.M), sw
(case/'microbepar_in').write_bytes(params)
subprocess.run(['./preview_namelists'], cwd=case, check=True)
with (case/'build_out.txt').open('w') as log:
    subprocess.run([f'./{name}.build'], cwd=case, stdout=log, stderr=subprocess.STDOUT, check=True)
