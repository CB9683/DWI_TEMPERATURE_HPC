#!/bin/bash
#PBS -l ncpus=2,mem=8GB,walltime=01:00:00
#PBS -q normal
#PBS -P vp06
#PBS -l storage=gdata/vp06+scratch/vp06+gdata/hl36
#PBS -l wd
#PBS -N DTI_Analysis
#PBS -o logs/03_dti.out
#PBS -e logs/03_dti.err

# --- 1. CHECK PASSED VARIABLES ---
if [ -z "${OUTPUT_DIR}" ]; then
    echo "ERROR: OUTPUT_DIR not set! This job should be submitted via pipeline manager."
    exit 1
fi

# --- 2. INITIAL SETUP ---
set -e
echo "--- DTI analysis job started on $(hostname) at $(date) ---"
echo "--- Using output directory: ${OUTPUT_DIR} ---"

CONFIG_FILE="pipeline_config.json"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file ${CONFIG_FILE} not found!"
    exit 1
fi

# --- 3. LOAD MODULES AND ACTIVATE CONDA FIRST ---
module load gcc/11.1.0

# Get conda path using system python3
CONDA_ENV_PATH=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['conda_env'])")

# Activate conda environment FIRST
source "${CONDA_ENV_PATH%/*/*}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV_PATH}"

# Save the conda Python path
CONDA_PYTHON=$(which python)
echo "Conda Python: ${CONDA_PYTHON}"
echo "Python version in conda env: $(python --version)"

# --- 4. PARSE CONFIGURATION WITH CONDA PYTHON ---
SUBJECT=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['subjects'][0])")
MRTRIX3_BIN=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['mrtrix3_bin'])")

# --- 5. SET REMAINING ENVIRONMENT ---
# Add MRtrix3 to beginning of PATH
export PATH=${MRTRIX3_BIN}:${PATH}
# Ensure conda Python directory stays first
export PATH=${CONDA_PYTHON%/*}:${PATH}

export MRTRIX_TMPFILE_DIR=${PBS_JOBFS}

# Verify we're still using conda Python
echo "Python after all PATH changes: $(which python)"
echo "Python version: $(python --version)"

# Create logs directory
mkdir -p logs

echo "--- Processing subject: ${SUBJECT} ---"
echo "--- Output directory: ${OUTPUT_DIR} ---"

# --- 6. CHECK IF DTI IS ENABLED ---
DTI_ENABLED=$(python -c "import json; cfg=json.load(open('${CONFIG_FILE}')); print(cfg.get('processing',{}).get('biexponential_model',{}).get('fit_dti', False))")

if [ "${DTI_ENABLED}" != "True" ]; then
    echo "WARNING: DTI fitting is not enabled in configuration!"
    echo "To enable, set 'fit_dti': true in the biexponential_model section of pipeline_config.json"
    echo "Proceeding anyway..."
fi

# --- 7. EXECUTION ---
echo "--- Starting DTI analysis for subject: ${SUBJECT} ---"

python -u 03_fit_tensor.py \
    "${SUBJECT}" \
    "${OUTPUT_DIR}" \
    --config_file "${CONFIG_FILE}"

if [ $? -eq 0 ]; then
    echo "--- Successfully completed DTI analysis ---"
else
    echo "!!! ERROR in DTI analysis !!!"
    exit 1
fi

echo "--- DTI analysis job finished at $(date) ---"