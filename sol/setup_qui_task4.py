#!/usr/bin/env python3
"""Prepare the reporting-only replay, retaining instantaneous area/flux covariance."""
from pathlib import Path
import os
import runpy
import subprocess

name = os.environ.get('CH4REPORT_CASE', 'qui_ch4bud_task4')
os.environ['CH4BLOCK_CASE'] = name
runpy.run_path('/work/CLM_SPRUCE/sol/setup_qui_ch4blocks.py', run_name='__main__')
case = Path('/work/cases')/name
p = case/'user_nl_clm'
fields = [f'CH4BUD_{k}_{p}' for k in ['SRC_LEGACY','PRE_INIT','DDIF','DLAT']
          for p in ['SAT','UNSAT']]
fields += [f'CH4_SURF_{k}_{p}' for k in ['NETFLUX','DIF','AERE','EBUL']
           for p in ['SAT','UNSAT']]
fields += ['CH4_SURF_NETFLUX','CH4_SURF_DIFF','CH4_SURF_AERE','CH4_SURF_EBUL']
p.write_text(p.read_text().rstrip()+',\n '+',\n '.join(repr(x) for x in fields)+'\n')
subprocess.run(['./preview_namelists'], cwd=case, check=True)
