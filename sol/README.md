# Sol (ASU) setup for ELM-SPRUCE

- `setup_elm_spruce.sh`: creates the US-SPR microbial test case on Sol (Intel oneAPI 2022.1, Intel MPI 2021.10, oneAPI NetCDF; everything under /scratch/jmarindi/elm_work). Writes `submit_run.sh` (sbatch) into the case.
- `Macros.test_case_intel_june2026`: the Macros from the June 2026 CLM-Microbe case that built and ran on Sol (reference for the port).
- Scratch is purged after 90 days without access. Code lives in this repo; rebuild cases with the setup script.

Model base: ELM-SPRUCE (Ricciuto et al. 2021), microbial CH4 module, hummock-hollow (-DHUM_HOL).
Dissertation target: reproduce Yuan et al. (2023) at PE-QFR, then extend. See `docs/elm_quistococha_implementation_spec.md`.
