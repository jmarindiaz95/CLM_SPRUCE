#!/usr/bin/env python3
"""Task 6b: fresh case and executable for the paired fix_lat_weights test (same outputs as task 5/6)."""
from pathlib import Path
import os
import runpy
import subprocess

name = 'qui_ch4bud_task6b'
os.environ['CH4REPORT_CASE'] = name
runpy.run_path('/work/CLM_SPRUCE/sol/setup_qui_task4.py', run_name='__main__')
case = Path('/work/cases')/name
p = case/'user_nl_clm'
p.write_text(p.read_text().rstrip()+",\n 'CH4_AERE_DEPTH_UNSAT', 'CH4_EBUL_DEPTH_UNSAT'\n")
subprocess.run(['./preview_namelists'], cwd=case, check=True)
with (case/'build_out.txt').open('w') as log:
    subprocess.run([f'./{name}.build'], cwd=case, stdout=log, stderr=subprocess.STDOUT, check=True)
