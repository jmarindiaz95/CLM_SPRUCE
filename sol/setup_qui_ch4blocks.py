#!/usr/bin/env python3
"""Create a fresh build case for diagnostic-only replay of the accepted fix-on run."""
from pathlib import Path
import os
import subprocess
import shutil

blocks = ['PRE','REACT','REMOVE','CLIP','MOVE','SURF','REPORT','OTHER']
case = Path('/work/cases/qui_ch4bud_blocks')
subprocess.run(['bash','/work/CLM_SPRUCE/sol/setup_qui_local.sh'],
               env={**os.environ, 'CNAME':'qui_ch4bud_blocks'}, check=True)
p = case/'user_nl_clm'
text = p.read_text()
anchor = " 'CH4BUD_SRC_SAT', 'CH4BUD_SRC_UNSAT'"
assert text.count(anchor)==1
extra = ',\n'.join(" 'CH4BUD_RES_"+b+"_SAT', 'CH4BUD_RES_"+b+"_UNSAT'" for b in blocks)
p.write_text(text.replace(anchor,anchor+',\n'+extra))
shutil.copy2('/work/results/qui_finund_repart/on/microbepar_in', case/'microbepar_in')
subprocess.run(['./preview_namelists'],cwd=case,check=True)
