#!/bin/bash
# Rebuild qui_microbe on a compute node with the fix_ch4_unsat patch, then submit the
# second branch set (run_qui_branches2.sh: aom0, aom10, aom0_min) from the year-500 restart.
# fix_ch4_unsat (default on, switch line "fix_ch4_unsat 0" in microbepar_in restores the original):
#   unsaturated fraction ebullition was a concentration used as a rate (x dt, up to 1800x too large),
#   and plant transport + ebullition had no limiter there. Dormant while CH4 < m_dCH4min, which is
#   exactly what the aom0 / aom0_min branches are meant to change.
# Usage:  cd /scratch/jmarindi/elm_work/CLM_SPRUCE && git pull
#         sbatch sol/build_qui_branches2.sh ; cat /scratch/jmarindi/elm_work/runs/qui_br2_build.log
#SBATCH --job-name=qui_br2_build
#SBATCH -p htc
#SBATCH -N 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 01:00:00
#SBATCH -o /scratch/jmarindi/elm_work/runs/qui_br2_build.log
W=/scratch/jmarindi/elm_work
SRC=$W/CLM_SPRUCE
CASE=$W/cases/qui_microbe
BLD=$W/builds/qui_microbe
NCDF=/scratch/jmarindi/clm_work/netcdf_merged_oneapi
echo "source: $(cd $SRC && git log --oneline -1)"
grep -q "fix_ch4_unsat" $SRC/models/lnd/clm/src/clm4_5/biogeochem/microbeMod.F90 || { echo "ERROR: patch not in source (git pull?)"; exit 1; }
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0 intel-oneapi-mpi-2021.10.0-gcc-12.1.0 intel-oneapi-mkl-2022.1.0-aocc-3.1.0 netcdf-c-4.8.1-oneapi-2022.1.0 netcdf-fortran-4.5.3-oneapi-2022.1.0
export LD_LIBRARY_PATH=$NCDF/lib:$LD_LIBRARY_PATH
export I_MPI_CC=icc I_MPI_CXX=icpc I_MPI_FC=ifort I_MPI_F90=ifort I_MPI_F77=ifort
cd $CASE
# Force the land model to recompile from source and cesm.exe to relink (an incremental make skipped it on Nov 3)
rm -f $BLD/lnd/obj/*.o $BLD/lnd/obj/*.mod $BLD/lib/liblnd.a $BLD/cesm.exe
if ./qui_microbe.build > build_out.txt 2>&1 && grep -q SUCCESSFULLY build_out.txt && [ -x $BLD/cesm.exe ]; then
  # the fix writes 'fix_ch4_unsat = ' to lnd.log, so that string must be inside the new executable
  strings $BLD/cesm.exe | grep -q "fix_ch4_unsat" || { echo "ERROR: cesm.exe built but does not contain fix_ch4_unsat (case compiles another source?)"; grep -i -m3 biogeochem $CASE/Buildconf/clmconf/Filepath; exit 1; }
  echo "== BUILD OK $(date), fix_ch4_unsat compiled in"
  bash $SRC/sol/run_qui_branches2.sh
else
  echo "== BUILD FAILED"
  zcat -f $(ls -t $BLD/*.bldlog.* | head -1) | grep -a -i -m5 -B1 -A4 error | cut -c1-300
  exit 1
fi
