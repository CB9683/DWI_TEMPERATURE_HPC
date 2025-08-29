#!/bin/bash
#PBS -l ncpus=12,mem=32GB,jobfs=40GB,walltime=08:00:00
#PBS -q gpuvolta
#PBS -l ngpus=1
#PBS -P vp06
#PBS -l storage=gdata/vp06+scratch/vp06+gdata/hl36
#PBS -l wd
#PBS -N Resume_Preproc
#PBS -o logs/01_preproc_resume.out
#PBS -e logs/01_preproc_resume.err

# ==============================================================================
# Resume preprocessing from existing dwi_preproc.mif
# This script continues from where preprocessing left off
# ==============================================================================

# --- 1. SET OUTPUT DIRECTORY ---
# IMPORTANT: Set this to your existing output directory
OUTPUT_DIR="/g/data/hl36/cb4095/WAND/derivatives/temp_pipeline_2025-08-27_11-27-08"

# --- 2. INITIAL SETUP ---
set -e
echo "--- Resume job started on $(hostname) at $(date) ---"
echo "--- Using existing output directory: ${OUTPUT_DIR} ---"

CONFIG_FILE="pipeline_config.json"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file ${CONFIG_FILE} not found!"
    exit 1
fi

# --- 3. LOAD MODULES AND ACTIVATE CONDA ---
module load gcc/11.1.0
module load cuda/11.2.2

# Parse configuration
CONDA_ENV_PATH=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['conda_env'])")
SUBJECTS=$(python3 -c "import json; print(' '.join(json.load(open('${CONFIG_FILE}'))['subjects']))")
BIDS_ROOT=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['bids_root'])")
FSLDIR=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['fsl_dir'])")
MRTRIX3_BIN=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['mrtrix3_bin'])")
MRTRIX3TISSUE_BIN=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['mrtrix3tissue_bin'])")

# Activate conda environment
source "${CONDA_ENV_PATH%/*/*}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV_PATH}"

echo "Python version in conda env: $(python --version)"

# --- 4. SET ENVIRONMENT ---
export FSLDIR=${FSLDIR}
export PATH=${FSLDIR}/bin:${PATH}
export PATH=${MRTRIX3_BIN}:${PATH}
export MRTRIX_TMPFILE_DIR=${PBS_JOBFS}

# Create logs directory if needed
mkdir -p logs

# --- 5. CHECK EXISTING FILES ---
echo "--- Checking existing files ---"
for subject in ${SUBJECTS}; do
    PREPROC_FILE="${OUTPUT_DIR}/${subject}/dwi_preproc.mif"
    if [ -f "${PREPROC_FILE}" ]; then
        echo "Found existing dwi_preproc.mif for ${subject}"
    else
        echo "ERROR: dwi_preproc.mif not found for ${subject} at ${PREPROC_FILE}"
        echo "Cannot resume without this file!"
        exit 1
    fi
done

# --- 6. RESUME PREPROCESSING ---
echo "--- Resuming preprocessing from bias correction step ---"

for subject in ${SUBJECTS}; do
    echo "=================================================="
    echo "         RESUMING PREPROCESSING FOR ${subject}"
    echo "=================================================="
    
    # Check what files already exist
    echo "Checking existing outputs for ${subject}:"
    ls -la "${OUTPUT_DIR}/${subject}/" | head -20
    
    python -u 02_preprocess_subject_resume.py \
        "${subject}" \
        "${BIDS_ROOT}" \
        "${OUTPUT_DIR}" \
        --mrtrix3tissue_bin "${MRTRIX3TISSUE_BIN}" \
        --jobfs_path "${PBS_JOBFS}" \
        --config_file "${CONFIG_FILE}"
        
    if [ $? -eq 0 ]; then
        echo "--- Successfully resumed and completed preprocessing for ${subject} ---"
    else
        echo "!!! ERROR: Resume preprocessing failed for ${subject} !!!"
        exit 1
    fi
done

# Update metadata with completion time
python -c "
import json
from datetime import datetime
import os

metadata_file = '${OUTPUT_DIR}/pipeline_metadata.json'
if os.path.exists(metadata_file):
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
else:
    metadata = {}

metadata['preprocessing_resumed'] = datetime.now().isoformat()
metadata['preprocessing_status'] = 'completed'
metadata['resume_job_id'] = '${PBS_JOBID}'

with open(metadata_file, 'w') as f:
    json.dump(metadata, f, indent=4)
"

echo "--- Resume preprocessing job finished successfully at $(date) ---"
echo "--- All outputs saved in: ${OUTPUT_DIR} ---"
echo ""
echo "Next steps:"
echo "1. Check if all required files are present:"
echo "   ls ${OUTPUT_DIR}/sub-*/csf_norm.mif"
echo "   ls ${OUTPUT_DIR}/sub-*/dwi_upsampled.mif"
echo "   ls ${OUTPUT_DIR}/sub-*/dwi_mask_upsampled.mif"
echo ""
echo "2. If using bi-exponential model, run DTI analysis:"
echo "   bash run_dti_only.sh ${OUTPUT_DIR}"
echo ""
echo "3. Run temperature analysis:"
echo "   bash run_analysis_only.sh ${OUTPUT_DIR}"