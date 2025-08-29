#!/bin/bash
#PBS -l ncpus=4,mem=32GB,walltime=02:00:00
#PBS -q normal
#PBS -P vp06
#PBS -l storage=gdata/vp06+scratch/vp06+gdata/hl36
#PBS -l wd
#PBS -N BiexpTest
#PBS -o logs/test_biexponential.out
#PBS -e logs/test_biexponential.err

# This job tests the bi-exponential diffusion model on preprocessed data

set -e

echo "--- Bi-exponential model test started at $(date) ---"

# Check for OUTPUT_DIR
if [ -z "${OUTPUT_DIR}" ]; then
    # Default to existing analysis directory
    OUTPUT_DIR="/g/data/hl36/cb4095/WAND/derivatives/temp_pipeline_2025-07-22_14-06-20"
    echo "Using default output directory: ${OUTPUT_DIR}"
fi

echo "Using output directory: ${OUTPUT_DIR}"

# Load configuration
CONFIG_FILE="pipeline_config.json"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file ${CONFIG_FILE} not found!"
    exit 1
fi

# Setup environment
module load gcc/11.1.0

# Get configuration values
CONDA_ENV_PATH=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['conda_env'])")
MRTRIX3_BIN=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['mrtrix3_bin'])")
BIDS_ROOT=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['bids_root'])")
SUBJECT=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['subjects'][0])")

# Activate conda environment
source "${CONDA_ENV_PATH%/*/*}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV_PATH}"

# Add MRtrix to PATH
export PATH=${MRTRIX3_BIN}:${PATH}

echo "Subject: ${SUBJECT}"
echo "Python version: $(python --version)"
echo "Temperature model: biexponential (from config)"

# Check that the calculation script exists
if [ ! -f "05_calculate_temperature.py" ]; then
    echo "ERROR: 05_calculate_temperature.py not found!"
    exit 1
fi

# Test bi-exponential fitting on b=1200 data
echo "--- Testing bi-exponential model on b=1200 data ---"

# Prepare files in expected locations
SUBJECT_DIR="${OUTPUT_DIR}/${SUBJECT}"
echo "Setting up files in: ${SUBJECT_DIR}"

# Check if DWI data exists from preprocessing
if [ -f "${SUBJECT_DIR}/dwi_upsampled.mif" ]; then
    echo "Using preprocessed DWI data for bi-exponential analysis..."
    echo "DWI file: ${SUBJECT_DIR}/dwi_upsampled.mif exists"
else
    echo "ERROR: dwi_upsampled.mif not found in preprocessing output"
    ls -la "${SUBJECT_DIR}/" || echo "Subject directory not found"
    exit 1
fi

# Skip FA generation - not needed for bi-exponential fitting
echo "Note: Running bi-exponential model without FA (FA is optional - used only for validation)"
echo "The bi-exponential parameters are fitted directly from the DWI signal decay"

# Check CSF norm map (required for 3tissue mask method)
if [ -f "${SUBJECT_DIR}/csf_norm.mif" ]; then
    echo "CSF norm map already exists from preprocessing"
else
    echo "ERROR: CSF norm map not found in preprocessing output"
    exit 1
fi

# Note: CSF masks will be created by the temperature calculation script
echo "CSF masks will be generated during temperature calculation process"

python 05_calculate_temperature.py \
    "${SUBJECT}" \
    "${OUTPUT_DIR}" \
    "${BIDS_ROOT}" \
    --output_suffix "b0_1200_biexp_test" \
    --config_file "${CONFIG_FILE}" \
    --bvals_for_adc 0 1200 \
    --mask_method 3tissue

if [ $? -eq 0 ]; then
    echo "--- Bi-exponential analysis completed successfully ---"
    
    # List generated parameter maps
    echo "Generated bi-exponential parameter maps:"
    ls -la "${OUTPUT_DIR}/${SUBJECT}"/d_free_map_*biexp_test* 2>/dev/null || true
    ls -la "${OUTPUT_DIR}/${SUBJECT}"/d_tissue_map_*biexp_test* 2>/dev/null || true  
    ls -la "${OUTPUT_DIR}/${SUBJECT}"/f_free_map_*biexp_test* 2>/dev/null || true
    ls -la "${OUTPUT_DIR}/${SUBJECT}"/r_squared_map_*biexp_test* 2>/dev/null || true
    ls -la "${OUTPUT_DIR}/${SUBJECT}"/model_used_map_*biexp_test* 2>/dev/null || true
    ls -la "${OUTPUT_DIR}/${SUBJECT}"/temperature_map_*biexp_test* 2>/dev/null || true
    
    # Run DTI analysis if enabled
    if [ -f "03_fit_tensor.py" ]; then
        echo "--- Running DTI analysis for FA calculation ---"
        python 03_fit_tensor.py \
            "${SUBJECT}" \
            "${OUTPUT_DIR}" \
            --config_file "${CONFIG_FILE}"
    fi
    
    # Run bi-exponential analysis visualization if available
    if [ -f "09_biexponential_analysis.py" ]; then
        echo "--- Creating bi-exponential visualizations ---"
        python 09_biexponential_analysis.py \
            "${SUBJECT}" \
            "${OUTPUT_DIR}" \
            --suffix "b0_1200_biexp_test" \
            --config_file "${CONFIG_FILE}"
    fi
    
else
    echo "ERROR: Bi-exponential analysis failed!"
    exit 1
fi

echo "========================================"
echo "Bi-exponential test finished at: $(date)"
echo "Results saved in: ${OUTPUT_DIR}/${SUBJECT}/"
echo "Check the following files for results:"
echo "- d_free_map_b0_1200_biexp_test.nii.gz"
echo "- d_tissue_map_b0_1200_biexp_test.nii.gz"
echo "- f_free_map_b0_1200_biexp_test.nii.gz"
echo "- r_squared_map_b0_1200_biexp_test.nii.gz"
echo "- temperature_map_b0_1200_biexp_test.mif"
echo "========================================"