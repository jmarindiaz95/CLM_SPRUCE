#!/bin/bash
# Rebuild qui_microbe with the CH4 budget diagnostic (CH4BUD_* history fields), then submit two 5-year
# branches from the year-500 restart (run_qui_ch4bud.sh: bud2_aom0, bud2_aom0_nofr, bud2_base).
# Usage:  cd /scratch/jmarindi/elm_work/CLM_SPRUCE && git pull
#         sbatch sol/build_qui_ch4bud.sh ; cat /scratch/jmarindi/elm_work/runs/qui_bud_build.log
#SBATCH --job-name=qui_bud_build
#SBATCH -p htc
#SBATCH -N 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 01:00:00
#SBATCH -o /scratch/jmarindi/elm_work/runs/qui_bud_build.log
W=/scratch/jmarindi/elm_work
SRC=$W/CLM_SPRUCE
CASE=$W/cases/qui_microbe
BLD=$W/builds/qui_microbe
NCDF=/scratch/jmarindi/clm_work/netcdf_merged_oneapi
echo "source: $(cd $SRC && git log --oneline -1)"
grep -q "fix_finund_repart" $SRC/models/lnd/clm/src/clm4_5/biogeochem/microbeMod.F90 || { echo "ERROR: patch not in source (git pull?)"; exit 1; }
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0 intel-oneapi-mpi-2021.10.0-gcc-12.1.0 intel-oneapi-mkl-2022.1.0-aocc-3.1.0 netcdf-c-4.8.1-oneapi-2022.1.0 netcdf-fortran-4.5.3-oneapi-2022.1.0
export LD_LIBRARY_PATH=$NCDF/lib:$LD_LIBRARY_PATH
export I_MPI_CC=icc I_MPI_CXX=icpc I_MPI_FC=ifort I_MPI_F90=ifort I_MPI_F77=ifort
cd $CASE
# Force the land model to recompile from source and cesm.exe to relink (an incremental make skipped it on Nov 3)
rm -f $BLD/lnd/obj/*.o $BLD/lnd/obj/*.mod $BLD/lib/liblnd.a $BLD/cesm.exe
if ./qui_microbe.build > build_out.txt 2>&1 && grep -q SUCCESSFULLY build_out.txt && [ -x $BLD/cesm.exe ]; then
  # the fix writes 'fix_ch4_unsat = ' to lnd.log, so that string must be inside the new executable
  strings $BLD/cesm.exe | grep -q "fix_finund_repart" || { echo "ERROR: cesm.exe built but does not contain fix_finund_repart (case compiles another source?)"; grep -i -m3 biogeochem $CASE/Buildconf/clmconf/Filepath; exit 1; }
  echo "== BUILD OK $(date), CH4 budget diagnostic and fix_finund_repart compiled in"
  bash $SRC/sol/run_qui_ch4bud.sh
else
  echo "== BUILD FAILED"
  zcat -f $(ls -t $BLD/*.bldlog.* | head -1) | grep -a -i -m5 -B1 -A4 error | cut -c1-300
  exit 1
fi
