#!/bin/bash
#PBS -l ncpus=1,mem=4GB,walltime=00:30:00
#PBS -q normal
#PBS -P vp06
#PBS -l storage=gdata/vp06+scratch/vp06+gdata/hl36
#PBS -l wd
#PBS -N run_analysis_only
#PBS -o run_analysis_only.out
#PBS -e run_analysis_only.err

# ==============================================================================
# Standalone Temperature Analysis Script
# Run only the b-value sweep temperature analysis step
# ==============================================================================

set -e

echo "========================================"
echo "DWI Temperature Pipeline - Analysis Only"
echo "Started at: $(date)"
echo "========================================"

# Check for output directory argument (optional - will auto-detect if not provided)
if [ $# -eq 0 ]; then
    echo "No output directory provided. Auto-detecting latest pipeline output..."
    OUTPUT_DIR=$(cd /g/data/vp06/Christian/dwi-temperature_updated && python3 get_latest_output.py)
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
CONFIG_FILE="/g/data/vp06/Christian/dwi-temperature_updated/pipeline_config.json"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file ${CONFIG_FILE} not found!"
    exit 1
fi

# Verify required preprocessing files exist
SUBJECT=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['subjects'][0])")
REQUIRED_FILES=(
    "${OUTPUT_DIR}/${SUBJECT}/dwi_preproc_unbiased.mif"
    "${OUTPUT_DIR}/${SUBJECT}/dwi_upsampled.mif"
    "${OUTPUT_DIR}/${SUBJECT}/csf_norm.mif"
    "${OUTPUT_DIR}/${SUBJECT}/dwi_mask_upsampled.mif"
)

echo "Checking for required preprocessing outputs..."
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "ERROR: Required file not found: $file"
        echo "Make sure preprocessing completed successfully first."
        exit 1
    fi
done
echo "All required preprocessing outputs found."

echo "Using output directory: ${OUTPUT_DIR}"
echo "Processing subject: ${SUBJECT}"

# Create logs directory
mkdir -p logs

# Submit analysis job
echo "Submitting b-value sweep analysis job..."
cd /g/data/vp06/Christian/dwi-temperature_updated
JOB1=$(qsub -v OUTPUT_DIR=${OUTPUT_DIR} 04_run_bvalue_sweep.sh)
echo "Submitted analysis job: ${JOB1}"

# Create summary file
SUMMARY_FILE="analysis_job_$(date +%Y%m%d_%H%M%S).txt"
cat > ${SUMMARY_FILE} << EOL
Temperature analysis submitted at: $(date)
Output directory: ${OUTPUT_DIR}
Subject: ${SUBJECT}
Analysis job: ${JOB1}
EOL

echo "========================================"
echo "Temperature analysis job submitted successfully!"
echo "Job ID: ${JOB1}"
echo "Monitor with: qstat -u \$USER"
echo "Results will be in: ${OUTPUT_DIR}/${SUBJECT}/"
echo "Job info saved to: ${SUMMARY_FILE}"
echo "========================================"

echo ""
echo "Next steps after analysis completes:"
echo "1. Check logs: tail -f logs/04_bvalue_sweep.out"
echo "2. Run reports: qsub run_reports_only.sh (pass OUTPUT_DIR=${OUTPUT_DIR})"
echo "3. Run stability analysis: qsub run_stability_only.sh (pass OUTPUT_DIR=${OUTPUT_DIR})"
echo ""
echo "NOTE: This script should be submitted via qsub, not run directly:"
echo "  qsub run_analysis_only.sh"
echo "  or with specific output dir:"
echo "  qsub -v OUTPUT_DIR=/path/to/output run_analysis_only.sh"