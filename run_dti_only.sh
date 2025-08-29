#!/bin/bash

# ==============================================================================
# Standalone DTI Analysis Script
# Run only the DTI analysis step (needed for bi-exponential model)
# ==============================================================================

set -e

echo "========================================"
echo "DWI Temperature Pipeline - DTI Analysis Only"
echo "Started at: $(date)"
echo "========================================"

# Check for output directory argument (optional - will auto-detect if not provided)
if [ $# -eq 0 ]; then
    echo "No output directory provided. Auto-detecting latest pipeline output..."
    OUTPUT_DIR=$(python3 get_latest_output.py)
    if [ $? -ne 0 ]; then
        echo "ERROR: Could not auto-detect output directory."
        echo "Usage: $0 [OUTPUT_DIR]"
        echo "Example: $0 /path/to/pipeline/output"
        exit 1
    fi
    echo "Using auto-detected directory: ${OUTPUT_DIR}"
elif [ $# -eq 1 ]; then
    OUTPUT_DIR="$1"
    echo "Using provided directory: ${OUTPUT_DIR}"
else
    echo "Usage: $0 [OUTPUT_DIR]"
    echo "  If no directory provided, will use the most recent pipeline output"
    echo "Example: $0 /path/to/pipeline/output"
    exit 1
fi

if [ ! -d "${OUTPUT_DIR}" ]; then
    echo "ERROR: Output directory does not exist: ${OUTPUT_DIR}"
    exit 1
fi

# Check configuration file
CONFIG_FILE="pipeline_config.json"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file ${CONFIG_FILE} not found!"
    exit 1
fi

# Check if DTI is enabled in config
DTI_ENABLED=$(python3 -c "import json; cfg=json.load(open('${CONFIG_FILE}')); print(cfg.get('processing',{}).get('biexponential_model',{}).get('fit_dti', False))")

if [ "${DTI_ENABLED}" != "True" ]; then
    echo "WARNING: DTI fitting is not enabled in configuration!"
    echo "To enable, set 'fit_dti': true in the biexponential_model section of pipeline_config.json"
    echo "Proceeding anyway..."
fi

echo "Using output directory: ${OUTPUT_DIR}"

# Create logs directory
mkdir -p logs

# Check if DTI submission script exists
if [ ! -f "03_run_dti.sh" ]; then
    echo "ERROR: DTI submission script 03_run_dti.sh not found!"
    echo "Make sure all pipeline scripts are present."
    exit 1
fi

# Submit DTI analysis job
echo "Submitting DTI analysis job..."
JOB1=$(qsub -v OUTPUT_DIR=${OUTPUT_DIR} 03_run_dti.sh)
echo "Submitted DTI job: ${JOB1}"

# Create summary file
SUMMARY_FILE="dti_job_$(date +%Y%m%d_%H%M%S).txt"
cat > ${SUMMARY_FILE} << EOL
DTI analysis submitted at: $(date)
Output directory: ${OUTPUT_DIR}
DTI job: ${JOB1}
EOL

echo "========================================"
echo "DTI analysis job submitted successfully!"
echo "Job ID: ${JOB1}"
echo "Monitor with: qstat -u \$USER"
echo "Results will be in: ${OUTPUT_DIR}/*/dti/"
echo "Job info saved to: ${SUMMARY_FILE}"
echo "========================================"

echo ""
echo "Next steps after DTI completes:"
echo "1. Check logs: tail -f logs/03_dti.out"
echo "2. Run temperature analysis: bash run_analysis_only.sh ${OUTPUT_DIR}"