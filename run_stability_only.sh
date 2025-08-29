#!/bin/bash

# ==============================================================================
# Standalone Stability Analysis Script
# Run only the temperature stability analysis step
# ==============================================================================

set -e

echo "========================================"
echo "DWI Temperature Pipeline - Stability Analysis Only"
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

# Verify required analysis files exist
SUBJECT=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['subjects'][0])")

echo "Checking for temperature analysis results..."
TEMP_MAPS=($(find "${OUTPUT_DIR}/${SUBJECT}" -name "temperature_map_*.mif" 2>/dev/null || true))

if [ ${#TEMP_MAPS[@]} -lt 2 ]; then
    echo "ERROR: Found only ${#TEMP_MAPS[@]} temperature maps in ${OUTPUT_DIR}/${SUBJECT}/"
    echo "Stability analysis requires at least 2 temperature analyses."
    echo "Make sure multiple b-value temperature analyses completed successfully first."
    exit 1
fi

echo "Found ${#TEMP_MAPS[@]} temperature analysis results - sufficient for stability analysis."
echo "Using output directory: ${OUTPUT_DIR}"
echo "Processing subject: ${SUBJECT}"

# Create logs directory
mkdir -p logs

# Submit stability analysis job
echo "Submitting stability analysis job..."
JOB1=$(qsub -v OUTPUT_DIR=${OUTPUT_DIR} 09_analyze_stability.sh)
echo "Submitted stability job: ${JOB1}"

# Create summary file
SUMMARY_FILE="stability_job_$(date +%Y%m%d_%H%M%S).txt"
cat > ${SUMMARY_FILE} << EOL
Stability analysis submitted at: $(date)
Output directory: ${OUTPUT_DIR}
Subject: ${SUBJECT}
Number of analyses found: ${#TEMP_MAPS[@]}
Stability job: ${JOB1}
EOL

echo "========================================"
echo "Stability analysis job submitted successfully!"
echo "Job ID: ${JOB1}"
echo "Monitor with: qstat -u \$USER"
echo "Results will be in: ${OUTPUT_DIR}/${SUBJECT}/temperature_stability_*"
echo "Job info saved to: ${SUMMARY_FILE}"
echo "========================================"

echo ""
echo "Next steps after stability analysis completes:"
echo "1. Check logs: tail -f logs/09_stability_analysis.out"
echo "2. View stability maps: ${OUTPUT_DIR}/${SUBJECT}/stable_voxels_*"
echo "3. Check stability visualizations: ${OUTPUT_DIR}/${SUBJECT}/temperature_stability_*"