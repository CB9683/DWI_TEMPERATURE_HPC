#!/bin/bash
#PBS -l ncpus=1,mem=8GB,walltime=00:30:00
#PBS -q normal
#PBS -P vp06
#PBS -l storage=gdata/vp06+scratch/vp06+gdata/hl36
#PBS -l wd
#PBS -N Generate_Reports
#PBS -o logs/08_reports.out
#PBS -e logs/08_reports.err

# This job runs the visualization and report generation scripts

set -e

echo "--- Report generation job started at $(date) ---"

# Check for OUTPUT_DIR from pipeline manager
if [ -z "${OUTPUT_DIR}" ]; then
    echo "ERROR: OUTPUT_DIR not set! This job should be submitted via pipeline manager."
    exit 1
fi

echo "Using output directory: ${OUTPUT_DIR}"

# Load configuration
CONFIG_FILE="pipeline_config.json"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file ${CONFIG_FILE} not found!"
    exit 1
fi

# Get configuration values - use python3 for initial parsing
SUBJECT=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['subjects'][0])")
MRTRIX3_BIN=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['mrtrix3_bin'])")
CONDA_ENV_PATH=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['conda_env'])")

echo "Subject: ${SUBJECT}"
echo "Output directory: ${OUTPUT_DIR}"

# Setup environment
module load gcc/11.1.0

# Activate conda FIRST
source "${CONDA_ENV_PATH%/*/*}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV_PATH}"

# Now we can use 'python' within the conda environment
echo "Python version in conda env: $(python --version)"

# Add MRtrix to path (needed for mrconvert in the histogram script)
export PATH=${MRTRIX3_BIN}:${PATH}

# Check that required Python scripts exist
if [ ! -f "06_create_histograms.py" ]; then
    echo "ERROR: 06_create_histograms.py not found!"
    exit 1
fi

if [ ! -f "07_comprehensive_analysis.py" ]; then
    echo "ERROR: 07_comprehensive_analysis.py not found!"
    exit 1
fi

# Generate histograms
echo "--- Generating histograms ---"
python 06_create_histograms.py "${SUBJECT}" "${OUTPUT_DIR}"

if [ $? -ne 0 ]; then
    echo "ERROR: Histogram generation failed!"
    exit 1
fi

# Generate comprehensive analysis
echo "--- Generating comprehensive analysis ---"
python 07_comprehensive_analysis.py "${SUBJECT}" "${OUTPUT_DIR}"

if [ $? -ne 0 ]; then
    echo "ERROR: Comprehensive analysis failed!"
    exit 1
fi

# Check if bi-exponential model is enabled
BIEXP_ENABLED=$(python -c "import json; cfg=json.load(open('${CONFIG_FILE}')); print(cfg.get('processing',{}).get('temperature_model','monoexponential') == 'biexponential')")

if [ "${BIEXP_ENABLED}" = "True" ]; then
    echo "--- Generating bi-exponential analysis ---"
    if [ -f "13_biexponential_analysis.py" ]; then
        python 13_biexponential_analysis.py "${SUBJECT}" "${OUTPUT_DIR}"
        
        if [ $? -ne 0 ]; then
            echo "WARNING: Bi-exponential analysis failed!"
        fi
    else
        echo "WARNING: 13_biexponential_analysis.py not found!"
    fi
    
    echo "--- Generating model comparison ---"
    if [ -f "14_model_comparison.py" ]; then
        python 14_model_comparison.py "${SUBJECT}" "${OUTPUT_DIR}" \
            "$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['bids_root'])")" \
            --config_file "${CONFIG_FILE}" \
            --skip_calculation
        
        if [ $? -ne 0 ]; then
            echo "WARNING: Model comparison failed!"
        fi
    else
        echo "WARNING: 14_model_comparison.py not found!"
    fi
else
    echo "--- Bi-exponential model disabled, skipping advanced analyses ---"
fi

echo "========================================"
echo "All reports generated successfully!"
echo "Results are in: ${OUTPUT_DIR}"
echo "View report at: ${OUTPUT_DIR}/${SUBJECT}/comprehensive_report/report.html"
if [ "${BIEXP_ENABLED}" = "True" ]; then
    echo "Bi-exponential analysis: ${OUTPUT_DIR}/${SUBJECT}/biexponential_analysis/"
    echo "Model comparison: ${OUTPUT_DIR}/${SUBJECT}/model_comparison/"
fi
echo "Finished at: $(date)"
echo "========================================"