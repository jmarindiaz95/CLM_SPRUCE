#!/bin/bash
# CH4 budget test: two 5-year branches from the year-500 AD restart with the CH4BUD_* history fields
# (exe must contain them; built by build_qui_ch4bud.sh). Both finund_wt_only = .true., fix_ch4_unsat on.
#   bud2_aom0      : AOM growth 0, fix_finund_repart on (default)
#   bud2_aom0_nofr : AOM growth 0, fix_finund_repart off (original repartition), to isolate its effect
#   bud2_base      : default AOM (0.004), fix_finund_repart on
# (first set, Nov 5: bud_aom0 / bud_base, diagnostic only)
# Usage: called by build_qui_ch4bud.sh
#SBATCH --job-name=qui_bud_setup
#SBATCH -p htc
#SBATCH -N 1
#SBATCH -c 1
#SBATCH --mem=4G
#SBATCH -t 00:20:00
#SBATCH -o /scratch/jmarindi/elm_work/runs/qui_bud_setup.log
W=/scratch/jmarindi/elm_work
CASE=$W/cases/qui_microbe
R=$W/runs/qui_microbe
BLD=$W/builds/qui_microbe
NCDF=/scratch/jmarindi/clm_work/netcdf_merged_oneapi
RST=$W/runs/qui_ad500_restart/qui_microbe.clm2.r.0501-01-01-00000.nc
[ -f $RST ] || { echo "ERROR: $RST not found"; exit 1; }
[ -x $BLD/cesm.exe ] || { echo "ERROR: $BLD/cesm.exe not found"; exit 1; }
SRCD=$W/runs/qui_br_noaom_wt          # template: run directory of the previous branch (same exe, finidat, monthly output)
grep -q "qui_ad500_restart" $SRCD/lnd_in && grep -q "finund_wt_only = .true." $SRCD/lnd_in || { echo "ERROR: template lnd_in not as expected"; exit 1; }

setp() { sed -i "s/^$1[[:space:]].*/$1\t$2/" $3; grep -q "^$1[[:space:]]*$2\$" $3 || { echo "ERROR: $1 not set"; exit 1; }; }

for v in $(env | grep -o '^SLURM_[A-Za-z_]*'); do unset $v; done
for T in bud2_aom0 bud2_aom0_nofr bud2_base; do
  D=$W/runs/qui_br_$T
  rm -rf $D; mkdir -p $D/timing/checkpoints
  find $SRCD -maxdepth 1 -type f ! -name '*.nc' ! -name '*.log*' ! -name 'rpointer.*' ! -name '*.gz' ! -name 'job*' ! -name 'cesm.log' -exec cp {} $D/ \;
  sed -i "s#$SRCD#$D#g" $D/*_modelio.nml
  setp frac_ch4aom 1.0 $D/microbepar_in
  case $T in
    bud2_aom0)      setp m_dGrowRAOMMethanotrophs 0.0 $D/microbepar_in ;;
    bud2_aom0_nofr) setp m_dGrowRAOMMethanotrophs 0.0 $D/microbepar_in; printf 'fix_finund_repart\t0\n' >> $D/microbepar_in ;;
    bud2_base)      setp m_dGrowRAOMMethanotrophs 0.004 $D/microbepar_in ;;
  esac
  sed -i 's/^\( *stop_n *= *\).*/\15/' $D/drv_in
  grep -q "stop_n *= *5" $D/drv_in || { echo "ERROR: stop_n not set to 5 in drv_in"; exit 1; }
  echo "== $T: $(grep -E '^(m_dGrowRAOMMethanotrophs|m_dCH4min|frac_ch4aom)' $D/microbepar_in | tr '\t\n' '  ') | $(grep -c 'finund_wt_only = .true.' $D/lnd_in) wt_only"
  cat > $D/job.sh <<EOF
#!/bin/bash
#SBATCH --job-name=qui_$T
#SBATCH -p htc
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -t 00:40:00
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
echo "When all three finish:  cd $W/runs && zip -qr ~/qui_bud2.zip qui_br_bud2_aom0 qui_br_bud2_aom0_nofr qui_br_bud2_base -i '*.clm2.h0.*.nc' '*cesm.log' '*drv_in' '*microbepar_in'"
