#!/bin/bash
# Batch wrapper: builds on a compute node (login nodes kill large compiles), then
# run_diag_test.sh submits the two 20-year diagnostic runs as their own jobs.
# Usage:  sbatch /scratch/jmarindi/elm_work/CLM_SPRUCE/sol/submit_diag_build.sh
#         then check  cat /scratch/jmarindi/elm_work/runs/diag_build.log
#SBATCH --job-name=diag_build
#SBATCH -p htc
#SBATCH -N 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 01:00:00
#SBATCH -o /scratch/jmarindi/elm_work/runs/diag_build.log
bash /scratch/jmarindi/elm_work/CLM_SPRUCE/sol/run_diag_test.sh
