#!/bin/bash
#PBS -l ncpus=12,mem=32GB,jobfs=80GB,walltime=12:00:00
#PBS -q gpuvolta
#PBS -l ngpus=1
#PBS -P vp06
#PBS -l storage=gdata/vp06+scratch/vp06+gdata/hl36
#PBS -l wd
#PBS -N Preproc_Temp_Pipeline
#PBS -o logs/01_preproc.out
#PBS -e logs/01_preproc.err

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
module load cuda/11.2.2

# Quick parse to get conda path using python3 (system python)
CONDA_ENV_PATH=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['conda_env'])")

# Activate conda environment
source "${CONDA_ENV_PATH%/*/*}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV_PATH}"

# NOW we can use 'python' because we're in the conda environment
echo "Python version in conda env: $(python --version)"

# --- 4. PARSE REMAINING CONFIGURATION ---
# Now using conda's python (can use 'python' instead of 'python3')
SUBJECTS=$(python -c "import json; print(' '.join(json.load(open('${CONFIG_FILE}'))['subjects']))")
BIDS_ROOT=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['bids_root'])")
FSLDIR=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['fsl_dir'])")
MRTRIX3_BIN=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['mrtrix3_bin'])")
MRTRIX3TISSUE_BIN=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['mrtrix3tissue_bin'])")

# --- 5. SET REMAINING ENVIRONMENT ---
export FSLDIR=${FSLDIR}
export PATH=${FSLDIR}/bin:${PATH}
export PATH=${MRTRIX3_BIN}:${PATH}
export MRTRIX_TMPFILE_DIR=${PBS_JOBFS}

# Create output directory
mkdir -p "${OUTPUT_DIR}"
mkdir -p logs

# Save configuration to output directory
cp "${CONFIG_FILE}" "${OUTPUT_DIR}/pipeline_config.json"

# Save pipeline metadata (now using conda's python)
python -c "
import json
from datetime import datetime
metadata = {
    'pipeline_version': '2.0',
    'preprocessing_start': datetime.now().isoformat(),
    'pbs_job_id': '${PBS_JOBID}',
    'hostname': '$(hostname)',
    'output_directory': '${OUTPUT_DIR}'
}
with open('${OUTPUT_DIR}/pipeline_metadata.json', 'w') as f:
    json.dump(metadata, f, indent=4)
"

# --- 6. EXECUTION ---
echo "--- Processing ${SUBJECTS} ---"

for subject in ${SUBJECTS}; do
    echo "=================================================="
    echo "         STARTING PREPROCESSING FOR ${subject}"
    echo "=================================================="
    
    python -u 02_preprocess_subject.py \
        "${subject}" \
        "${BIDS_ROOT}" \
        "${OUTPUT_DIR}" \
        --mrtrix3tissue_bin "${MRTRIX3TISSUE_BIN}" \
        --jobfs_path "${PBS_JOBFS}" \
        --config_file "${CONFIG_FILE}"
        
    if [ $? -eq 0 ]; then
        echo "--- Successfully finished preprocessing for ${subject} ---"
    else
        echo "!!! ERROR: Preprocessing failed for ${subject} !!!"
        exit 1
    fi
done

# Update metadata with completion time
python -c "
import json
from datetime import datetime
with open('${OUTPUT_DIR}/pipeline_metadata.json', 'r') as f:
    metadata = json.load(f)
metadata['preprocessing_end'] = datetime.now().isoformat()
metadata['preprocessing_status'] = 'completed'
with open('${OUTPUT_DIR}/pipeline_metadata.json', 'w') as f:
    json.dump(metadata, f, indent=4)
"

echo "--- Preprocessing job finished successfully at $(date) ---"
echo "--- All outputs saved in: ${OUTPUT_DIR} ---"