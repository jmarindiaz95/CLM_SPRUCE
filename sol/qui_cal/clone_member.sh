#!/bin/bash
# Clone a calibration member's 2015-2019 configuration into a new run directory (logs, timing and parameter file
# local to it), with another executable and optional extra trailing microbepar_in lines ("name<TAB>value").
# The source member is only read. Writes run_one.sh (sbatch) in the new directory.
# Usage: clone_member.sh <src member dir> <dst dir> <cesm.exe> ["name value" ...]
set -euo pipefail
S=$1; D=$2; EXE=$3; shift 3
[ -f $EXE ] || { echo "ERROR: $EXE missing"; exit 1; }
[ -e $D ] && { echo "ERROR: $D exists"; exit 1; }
mkdir -p $D/timing/checkpoints
for f in $S/*_in $S/*_modelio.nml $S/datm.streams.txt.* $S/datm.global1val.streams.co2.txt $S/microbepar_in \
         $S/clm_params_member.nc $S/finund_obswl.txt; do cp $f $D/; done
sed -i "s#^ fpftcon = .*# fpftcon = '$D/clm_params_member.nc'#" $D/lnd_in
sed -i "s#^ diro = .*# diro = '$D'#" $D/*_modelio.nml
grep -h "diro" $D/*_modelio.nml | sort -u | grep -qv "'$D'" && { echo "ERROR: diro not rewritten"; exit 1; }
for kv in "$@"; do
  k=${kv%% *}; v=${kv#* }
  grep -q "^$k[[:space:]]" $D/microbepar_in && { echo "ERROR: $k already in microbepar_in"; exit 1; }
  printf '%s\t%s\n' "$k" "$v" >> $D/microbepar_in
done
cat > $D/run_one.sh <<EOF
#!/bin/bash
#SBATCH --job-name=qui_clone
#SBATCH -p public
#SBATCH -N 1
#SBATCH -n 1
#SBATCH --mem=3G
#SBATCH -t 01:00:00
#SBATCH -o $D/slurm.%j.out
module purge
module load intel-oneapi-compilers-2022.1.0-gcc-11.2.0 intel-oneapi-mpi-2021.10.0-gcc-12.1.0 intel-oneapi-mkl-2022.1.0-aocc-3.1.0 netcdf-c-4.8.1-oneapi-2022.1.0 netcdf-fortran-4.5.3-oneapi-2022.1.0
export LD_LIBRARY_PATH=/scratch/jmarindi/clm_work/netcdf_merged_oneapi/lib:\$LD_LIBRARY_PATH
export UCX_TLS=sm,tcp,self
cd $D
srun -n 1 $EXE > cesm.log 2>&1
EOF
echo "== $D"; grep -E "^ fpftcon" $D/lnd_in; tail -n $(( $# + 1 )) $D/microbepar_in
