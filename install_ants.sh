#!/bin/bash

# Script to install ANTs in the dwi_temperature conda environment
# ANTs is required for dwibiascorrect ants command

echo "========================================"
echo "Installing ANTs in dwi_temperature conda environment"
echo "========================================"

# Load configuration to get conda path
CONFIG_FILE="pipeline_config.json"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file ${CONFIG_FILE} not found!"
    exit 1
fi

# Get conda environment path
CONDA_ENV_PATH=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['conda_env'])")

# Activate conda environment
echo "Activating conda environment: ${CONDA_ENV_PATH}"
source "${CONDA_ENV_PATH%/*/*}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV_PATH}"

# Check if ANTs is already installed
if command -v N4BiasFieldCorrection &> /dev/null; then
    echo "ANTs appears to be already installed!"
    echo "N4BiasFieldCorrection found at: $(which N4BiasFieldCorrection)"
    exit 0
fi

echo "Installing ANTs via conda-forge..."
echo "This may take several minutes..."

# Install ANTs from conda-forge
conda install -c conda-forge ants -y

# Verify installation
if command -v N4BiasFieldCorrection &> /dev/null; then
    echo "========================================"
    echo "SUCCESS: ANTs installed successfully!"
    echo "N4BiasFieldCorrection found at: $(which N4BiasFieldCorrection)"
    echo "========================================"
    
    # Test that it works
    echo "Testing N4BiasFieldCorrection..."
    N4BiasFieldCorrection --version
    
    echo ""
    echo "You can now run the resume preprocessing script:"
    echo "  qsub 01_resume_preprocessing.sh"
else
    echo "========================================"
    echo "ERROR: ANTs installation may have failed"
    echo "N4BiasFieldCorrection not found in PATH"
    echo "========================================"
    echo ""
    echo "Alternative options:"
    echo "1. Try manual installation:"
    echo "   conda install -c conda-forge ants=2.3.5"
    echo ""
    echo "2. Use FSL-based bias correction instead:"
    echo "   python 02_preprocess_subject_resume_fsl.py"
    echo ""
    echo "3. Skip bias correction (not recommended):"
    echo "   python 02_preprocess_subject_resume_fsl.py --skip_bias"
    exit 1
fi