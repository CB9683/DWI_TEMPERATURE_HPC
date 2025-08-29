#!/bin/bash
#PBS -l ncpus=2,mem=16GB,jobfs=20GB,walltime=02:00:00
#PBS -q normal
#PBS -P vp06
#PBS -l storage=gdata/vp06+scratch/vp06+gdata/hl36
#PBS -l wd
#PBS -N TempBvalSweep
#PBS -o logs/04_bvalue_sweep.out
#PBS -e logs/04_bvalue_sweep.err

# --- 1. CHECK PASSED VARIABLES ---
if [ -z "${OUTPUT_DIR}" ]; then
    echo "ERROR: OUTPUT_DIR not set! This job should be submitted via pipeline manager."
    exit 1
fi

# --- 2. INITIAL SETUP ---
set -e
echo "--- Job started on $(hostname) at $(date) ---"
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
# Now using conda's python (can use 'python' instead of 'python3')
SUBJECT=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['subjects'][0])")
BIDS_ROOT=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['bids_root'])")
FSLDIR=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['fsl_dir'])")
MRTRIX3_BIN=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['mrtrix3_bin'])")

# --- 5. SET REMAINING ENVIRONMENT WITH PROPER ORDER ---
export FSLDIR=${FSLDIR}
# IMPORTANT: Add FSL to END of PATH to preserve conda Python
export PATH=${PATH}:${FSLDIR}/bin
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

# --- 6. EXECUTION ---
echo "--- Starting b-value analysis sweep for subject: ${SUBJECT} ---"

# Get total number of b-value sets from config
TOTAL_BVAL_SETS=$(python -c "import json; print(len(json.load(open('${CONFIG_FILE}'))['bvalue_sets']))")

echo "--- Processing ${TOTAL_BVAL_SETS} b-value combinations ---"

# Process all b-value sets
for i in $(seq 0 $((TOTAL_BVAL_SETS - 1))); do
    # Get b-values for this index
    BVALS_STR=$(python -c "import json; print(' '.join(map(str, json.load(open('${CONFIG_FILE}'))['bvalue_sets'][${i}])))")
    
    # Create suffix from b-values
    SUFFIX=$(echo "${BVALS_STR}" | sed 's/ /_/g' | sed 's/^/b/')
    
    RUN_LOG_FILE="logs/calc_${SUBJECT}_${SUFFIX}.out"
    
    echo "--------------------------------------------------"
    echo "       Running analysis ${i}: ${SUFFIX}"
    echo "       B-values: ${BVALS_STR}"
    echo "       Detailed log: ${RUN_LOG_FILE}"
    echo "--------------------------------------------------"

    python -u 05_calculate_temperature.py \
        "${SUBJECT}" \
        "${OUTPUT_DIR}" \
        "${BIDS_ROOT}" \
        --bvals_for_adc ${BVALS_STR} \
        --output_suffix "${SUFFIX}" \
        --config_file "${CONFIG_FILE}" > "${RUN_LOG_FILE}" 2>&1

    if [ $? -eq 0 ]; then
        echo "--- Successfully completed analysis: ${SUFFIX} ---"
    else
        echo "!!! ERROR in analysis: ${SUFFIX} - check ${RUN_LOG_FILE} !!!"
    fi
done

# Run DTI fitting if enabled in config
DTI_ENABLED=$(python -c "import json; cfg=json.load(open('${CONFIG_FILE}')); print(cfg.get('processing',{}).get('biexponential_model',{}).get('fit_dti', False))")

if [ "${DTI_ENABLED}" = "True" ]; then
    echo "--------------------------------------------------"
    echo "       Running DTI Analysis"
    echo "--------------------------------------------------"
    
    DTI_LOG_FILE="logs/dti_${SUBJECT}.out"
    
    python -u 03_fit_tensor.py \
        "${SUBJECT}" \
        "${OUTPUT_DIR}" \
        --config_file "${CONFIG_FILE}" > "${DTI_LOG_FILE}" 2>&1
    
    if [ $? -eq 0 ]; then
        echo "--- Successfully completed DTI analysis ---"
    else
        echo "!!! ERROR in DTI analysis - check ${DTI_LOG_FILE} !!!"
    fi
else
    echo "--- DTI fitting disabled in configuration ---"
fi

echo "--- All b-value analyses complete. Job finished at $(date) ---"