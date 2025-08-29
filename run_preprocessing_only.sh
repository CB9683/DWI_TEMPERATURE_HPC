#!/bin/bash

# ==============================================================================
# Standalone Preprocessing Script
# Run only the preprocessing step of the DWI temperature pipeline
# ==============================================================================

set -e

echo "========================================"
echo "DWI Temperature Pipeline - Preprocessing Only"
echo "Started at: $(date)"
echo "========================================"

# Check configuration file
CONFIG_FILE="pipeline_config.json"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file ${CONFIG_FILE} not found!"
    exit 1
fi

# Create timestamp for unique output directory
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BASE_OUTPUT_DIR=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['base_output'])")
OUTPUT_DIR="${BASE_OUTPUT_DIR}/temp_pipeline_${TIMESTAMP}"

echo "Pipeline output directory: ${OUTPUT_DIR}"

# Create logs directory
mkdir -p logs

# Submit preprocessing job
echo "Submitting preprocessing job..."
JOB1=$(qsub -v OUTPUT_DIR=${OUTPUT_DIR},TIMESTAMP=${TIMESTAMP} 01_run_preprocessing.sh)
echo "Submitted preprocessing job: ${JOB1}"

# Create summary file
SUMMARY_FILE="preprocessing_job_$(date +%Y%m%d_%H%M%S).txt"
cat > ${SUMMARY_FILE} << EOL
Preprocessing submitted at: $(date)
Output directory: ${OUTPUT_DIR}
Preprocessing job: ${JOB1}
EOL

echo "========================================"
echo "Preprocessing job submitted successfully!"
echo "Job ID: ${JOB1}"
echo "Monitor with: qstat -u \$USER"
echo "Results will be in: ${OUTPUT_DIR}"
echo "Job info saved to: ${SUMMARY_FILE}"

# Initialize pipeline state
echo "Initializing pipeline state tracking..."
python pipeline_state.py "${OUTPUT_DIR}" --update preprocessing running "${JOB1}"

echo "========================================"

echo ""
echo "Next steps after preprocessing completes:"
echo "1. Check logs: tail -f logs/01_preproc.out"
echo "2. Check status: python pipeline_state.py ${OUTPUT_DIR} --status"
echo "3. Run analysis: bash run_analysis_only.sh ${OUTPUT_DIR}"
echo "4. Or run DTI first (if using bi-exponential): bash run_dti_only.sh ${OUTPUT_DIR}"