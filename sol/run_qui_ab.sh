#!/bin/bash
# Batch job: rebuild the QUI case, then submit two short cold-start runs that differ only in the
# soil water retention curve:  vg  (use_vg_retention = .true., as in setup_qui.sh)
#                              ch  (use_vg_retention = .false., Clapp-Hornberger)
# Usage:  sbatch /scratch/jmarindi/elm_work/CLM_SPRUCE/sol/run_qui_ab.sh      then  cat /scratch/jmarindi/elm_work/runs/qui_ab_build.log
#SBATCH --job-name=qui_ab_build
#SBATCH -p htc
#SBATCH -N 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 01:00:00
#SBATCH -o /scratch/jmarindi/elm_work/runs/qui_ab_build.log
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0 intel-oneapi-mpi-2021.10.0-gcc-12.1.0 \
  intel-oneapi-mkl-2022.1.0-aocc-3.1.0 netcdf-c-4.8.1-oneapi-2022.1.0 netcdf-fortran-4.5.3-oneapi-2022.1.0
export I_MPI_CC=icc I_MPI_CXX=icpc I_MPI_FC=ifort I_MPI_F90=ifort I_MPI_F77=ifort
NCDF=/scratch/jmarindi/clm_work/netcdf_merged_oneapi
export LD_LIBRARY_PATH=$NCDF/lib:$LD_LIBRARY_PATH
W=/scratch/jmarindi/elm_work
CASE=$W/cases/qui_microbe
R=$W/runs/qui_microbe
BLD=$W/builds/qui_microbe
NYRS=5

echo "source: $(cd $W/CLM_SPRUCE && git log --oneline -1)"
cd $CASE
if ./qui_microbe.build > build_out.txt 2>&1 && grep -q SUCCESSFULLY build_out.txt; then
  echo "== BUILD OK"
else
  echo "== BUILD FAILED"; grep -a -i -m5 -B1 -A4 error $(ls -t $BLD/*.bldlog.* | head -1) | cut -c1-300; exit 1
fi
./xmlchange -file env_run.xml -id STOP_N -val $NYRS
./xmlchange -file env_run.xml -id REST_N -val $NYRS
./xmlchange -file env_run.xml -id CONTINUE_RUN -val FALSE
./preview_namelists > /dev/null
for v in $(env | grep -o '^SLURM_[A-Za-z_]*'); do unset $v; done
for T in vg ch; do
  D=$W/runs/qui_ab_$T
  rm -rf $D; mkdir -p $D/timing/checkpoints
  find $R -maxdepth 1 -type f ! -name '*.nc' ! -name '*.log.*' ! -name 'rpointer.*' ! -name '*.gz' -exec cp {} $D/ \;
  sed -i "s#$R#$D#g" $D/*_modelio.nml
  [ $T = ch ] && sed -i 's/use_vg_retention *= *.true./use_vg_retention = .false./' $D/lnd_in
  echo "== $T: $(grep use_vg_retention $D/lnd_in)"
  cat > $D/job.sh <<EOF
#!/bin/bash
#SBATCH --job-name=qui_$T
#SBATCH -p htc
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 01:00:00
#SBATCH --mem=8G
#SBATCH -o $D/job.%j.out
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0 intel-oneapi-mpi-2021.10.0-gcc-12.1.0 intel-oneapi-mkl-2022.1.0-aocc-3.1.0 netcdf-c-4.8.1-oneapi-2022.1.0 netcdf-fortran-4.5.3-oneapi-2022.1.0
export LD_LIBRARY_PATH=$NCDF/lib:\$LD_LIBRARY_PATH
export UCX_TLS=sm,tcp,self OMP_NUM_THREADS=1
cd $D
srun -n 1 $BLD/cesm.exe > cesm.log 2>&1
echo "exit code \$?" >> cesm.log
EOF
  sbatch $D/job.sh
done
echo "When both finish:  cd $W/runs && tar czf ~/qui_ab.tgz qui_ab_*/*.clm2.h0.*.nc qui_ab_*/lnd.log.* qui_ab_*/cesm.log"
