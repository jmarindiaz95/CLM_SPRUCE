#!/bin/bash
# Batch job: rebuild the QUI case, then submit three 30-year branches from the year-500 AD-spinup restart:
#   base     : as the 500-year spinup
#   noaom    : anaerobic oxidation of methane off (frac_ch4aom = 0)
#   noaom_wt : AOM off and the Yuan water coverage scalar applied only above the water table
# Monthly, column-level output. Usage:
#   sbatch /scratch/jmarindi/elm_work/CLM_SPRUCE/sol/run_qui_branches.sh ; cat /scratch/jmarindi/elm_work/runs/qui_br_build.log
#SBATCH --job-name=qui_br_build
#SBATCH -p htc
#SBATCH -N 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 01:00:00
#SBATCH -o /scratch/jmarindi/elm_work/runs/qui_br_build.log
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
RST=$R/qui_microbe.clm2.r.0501-01-01-00000.nc
NYRS=30

echo "source: $(cd $W/CLM_SPRUCE && git log --oneline -1)"
[ -f $RST ] || { echo "ERROR: $RST not found"; exit 1; }
mkdir -p $W/runs/qui_ad500_restart && cp -n $R/qui_microbe.clm2.r.0501-01-01-00000.nc $R/qui_microbe.clm2.rh0.0501-01-01-00000.nc $W/runs/qui_ad500_restart/ 2>/dev/null
RST=$W/runs/qui_ad500_restart/qui_microbe.clm2.r.0501-01-01-00000.nc

cd $CASE
if ./qui_microbe.build > build_out.txt 2>&1 && grep -q SUCCESSFULLY build_out.txt; then
  echo "== BUILD OK"
else
  echo "== BUILD FAILED"; grep -a -i -m5 -B1 -A4 error $(ls -t $BLD/*.bldlog.* | head -1) | cut -c1-300; exit 1
fi
./xmlchange -file env_run.xml -id STOP_N -val $NYRS
./xmlchange -file env_run.xml -id REST_N -val $NYRS
./xmlchange -file env_run.xml -id CONTINUE_RUN -val FALSE
cp user_nl_clm user_nl_clm.main
sed -i -e 's/^ hist_nhtfrq.*/ hist_nhtfrq = 0/' -e 's/^ hist_mfilt.*/ hist_mfilt = 12/' user_nl_clm
grep -q "^ finidat" user_nl_clm || echo " finidat = '$RST'" >> user_nl_clm
./preview_namelists > /dev/null
cp user_nl_clm.main user_nl_clm
grep -q "qui_ad500_restart" $R/lnd_in || { echo "ERROR: finidat not set in lnd_in"; exit 1; }

for v in $(env | grep -o '^SLURM_[A-Za-z_]*'); do unset $v; done
for T in base noaom noaom_wt; do
  D=$W/runs/qui_br_$T
  rm -rf $D; mkdir -p $D/timing/checkpoints
  find $R -maxdepth 1 -type f ! -name '*.nc' ! -name '*.log.*' ! -name 'rpointer.*' ! -name '*.gz' -exec cp {} $D/ \;
  sed -i "s#$R#$D#g" $D/*_modelio.nml
  if [ $T != base ]; then
    sed -i 's/^frac_ch4aom.*/frac_ch4aom\t\t0.0/' $D/microbepar_in
  fi
  if [ $T = noaom_wt ]; then
    sed -i '0,/&clm_inparm/s//\&clm_inparm\n finund_wt_only = .true./' $D/lnd_in
  fi
  echo "== $T: $(grep '^frac_ch4aom' $D/microbepar_in | tr '\t' ' ') | $(grep -c finund_wt_only $D/lnd_in) finund_wt_only line(s)"
  cat > $D/job.sh <<EOF
#!/bin/bash
#SBATCH --job-name=qui_$T
#SBATCH -p htc
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 01:30:00
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
echo "When all three finish:  cd $W/runs && tar czf ~/qui_branches.tgz qui_br_*/*.clm2.h0.*.nc qui_br_*/lnd.log.* qui_br_*/cesm.log"
