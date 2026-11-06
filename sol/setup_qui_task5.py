#!/usr/bin/env python3
"""Fresh paired-test executable, with depth transport retained for independent checks."""
from pathlib import Path
import os
import runpy
import subprocess

os.environ['CH4REPORT_CASE'] = 'qui_ch4bud_task5'
runpy.run_path('/work/CLM_SPRUCE/sol/setup_qui_task4.py', run_name='__main__')
case = Path('/work/cases/qui_ch4bud_task5')
p = case/'user_nl_clm'
p.write_text(p.read_text().rstrip()+",\n 'CH4_AERE_DEPTH_UNSAT', 'CH4_EBUL_DEPTH_UNSAT'\n")
subprocess.run(['./preview_namelists'], cwd=case, check=True)
