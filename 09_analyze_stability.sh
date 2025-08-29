#!/bin/bash
#PBS -l ncpus=2,mem=16GB,walltime=00:30:00
#PBS -q express
#PBS -P vp06
#PBS -l storage=gdata/vp06+scratch/vp06+gdata/hl36
#PBS -l wd
#PBS -N TempStability
#PBS -o logs/09_stability_analysis.out
#PBS -e logs/09_stability_analysis.err

# This job runs the temperature stability analysis

set -e

echo "--- Temperature stability analysis job started at $(date) ---"

# Check for OUTPUT_DIR
if [ -z "${OUTPUT_DIR}" ]; then
    # If not passed, try to read from command line argument
    if [ $# -eq 1 ]; then
        OUTPUT_DIR="$1"
    else
        echo "ERROR: OUTPUT_DIR not set!"
        echo "Usage: qsub -v OUTPUT_DIR=/path/to/output 08_analyze_stability.sh"
        echo "   or: qsub 08_analyze_stability.sh /path/to/output"
        exit 1
    fi
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
SUBJECT=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['subjects'][0])")

# Activate conda environment
source "${CONDA_ENV_PATH%/*/*}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV_PATH}"

# Add MRtrix to PATH (needed for mrconvert)
export PATH=${MRTRIX3_BIN}:${PATH}

echo "Subject: ${SUBJECT}"
echo "Python version: $(python --version)"

# Check that the analysis script exists
if [ ! -f "10_analyze_stability.py" ]; then
    echo "ERROR: analyze_temperature_stability.py not found!"
    exit 1
fi

# Run stability analysis with configurable parameters
STABILITY_THRESHOLD=${STABILITY_THRESHOLD:-2.0}
MIN_ANALYSES=${MIN_ANALYSES:-5}
MIN_VALID_ANALYSES=${MIN_VALID_ANALYSES:-3}

echo "--- Running stability analysis ---"
echo "Stability threshold: ${STABILITY_THRESHOLD}°C"
echo "Minimum analyses required: ${MIN_ANALYSES}"

python 10_analyze_stability.py \
    "${SUBJECT}" \
    "${OUTPUT_DIR}" \
    --stability_threshold ${STABILITY_THRESHOLD} \
    --min_analyses ${MIN_ANALYSES} \
    --min_valid_analyses ${MIN_VALID_ANALYSES}

if [ $? -eq 0 ]; then
    echo "--- Stability analysis completed successfully ---"
    
    # List generated files
    echo "Generated files:"
    ls -la "${OUTPUT_DIR}/${SUBJECT}"/temperature_stability_* 2>/dev/null || true
    ls -la "${OUTPUT_DIR}/${SUBJECT}"/stable_voxels_* 2>/dev/null || true
else
    echo "ERROR: Stability analysis failed!"
    exit 1
fi

echo "========================================"
echo "Stability analysis finished at: $(date)"
echo "Results saved in: ${OUTPUT_DIR}/${SUBJECT}/"
echo "========================================"