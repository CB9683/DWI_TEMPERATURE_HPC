#!/bin/bash
#PBS -l ncpus=1,mem=8GB,walltime=00:30:00
#PBS -q normal
#PBS -P vp06
#PBS -l storage=gdata/vp06+scratch/vp06+gdata/hl36
#PBS -l wd
#PBS -N StableTempAnalysis
#PBS -o logs/08_stable_analysis.out
#PBS -e logs/08_stable_analysis.err

# ==============================================================================
#           PBS Submission Script for Stable Temperature Analysis
#
# This script runs the 08_create_stable_analysis.py script as a batch job.
#
# HOW TO USE:
# 1. Edit the variables in the "USER-CONFIGURABLE VARIABLES" section below.
# 2. Save the file.
# 3. Submit the job using: qsub 08_submit_stable_analysis.sh
#
# ==============================================================================

set -e

# --- USER-CONFIGURABLE VARIABLES ---
# Fill in these details before submitting the job.

# The subject ID you want to process (read from config file).
SUBJECT=$(python3 -c "import json; print(json.load(open('pipeline_config.json'))['subjects'][0])")

# The full path to the main output directory created by the pipeline manager.
OUTPUT_DIR="/g/data/hl36/cb4095/WAND/derivatives/temp_pipeline_2025-07-21_20-28-51"

# The suffix of the first analysis run to compare (e.g., 'b_0_200_500').
SUFFIX1="b0_200"

# The suffix of the second analysis run to compare (e.g., 'b_0_1200').
SUFFIX2="b0_1200"

# The maximum allowed temperature difference (in Celsius) to be considered stable.
THRESHOLD="5.0"

# --- END OF USER-CONFIGURABLE VARIABLES ---


# --- 1. INITIAL SETUP AND LOGGING ---
echo "--- Stable analysis job started on $(hostname) at $(date) ---"
echo "--- Configuration ---"
echo "Subject: ${SUBJECT}"
echo "Output Directory: ${OUTPUT_DIR}"
echo "Comparing: ${SUFFIX1} vs ${SUFFIX2}"
echo "Threshold: ${THRESHOLD}°C"
echo "---------------------"

# --- 2. SETUP ENVIRONMENT ---
CONFIG_FILE="pipeline_config.json"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file ${CONFIG_FILE} not found in the current directory!"
    exit 1
fi

module load gcc/11.1.0

CONDA_ENV_PATH=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['conda_env'])")
source "${CONDA_ENV_PATH%/*/*}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV_PATH}"
echo "Successfully activated Conda environment: $(which python)"

MRTRIX3_BIN=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['mrtrix3_bin'])")
export PATH=${MRTRIX3_BIN}:${PATH}
echo "MRtrix3 path configured. 'mrcalc' is at: $(which mrcalc)"

# --- 3. EXECUTION ---
SCRIPT_TO_RUN="08_create_stable_analysis.py"
if [ ! -f "${SCRIPT_TO_RUN}" ]; then
    echo "ERROR: The analysis script ${SCRIPT_TO_RUN} was not found!"
    exit 1
fi

echo "--- Starting the stable analysis script ---"
python -u "${SCRIPT_TO_RUN}" \
    "${SUBJECT}" \
    "${OUTPUT_DIR}" \
    "${SUFFIX1}" \
    "${SUFFIX2}" \
    --threshold "${THRESHOLD}"

if [ $? -eq 0 ]; then
    echo "--- Python script completed successfully. ---"
else
    echo "!!! ERROR: The Python script failed with an error. Check logs. !!!"
    exit 1
fi

# --- 4. JOB COMPLETION ---
RESULTS_DIR="${OUTPUT_DIR}/${SUBJECT}/stable_analysis_${SUFFIX1}_vs_${SUFFIX2}"
echo "======================================================"
echo "      Job finished successfully at $(date)"
echo "Results are located in: ${RESULTS_DIR}"
echo "======================================================"