#!/bin/bash
#!/bin/bash
#PBS -l ncpus=1,mem=4GB,walltime=00:30:00
#PBS -q normal
#PBS -P vp06
#PBS -l storage=gdata/vp06+scratch/vp06+gdata/hl36
#PBS -l wd
#PBS -N run_reports_only
#PBS -o run_reports_only.out
#PBS -e run_reports_only.err

# ==============================================================================
# Standalone Report Generation Script
# Run only the visualization and report generation step
# ==============================================================================

set -e

echo "========================================"
echo "DWI Temperature Pipeline - Reports Only"
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

if [ ${#TEMP_MAPS[@]} -eq 0 ]; then
    echo "ERROR: No temperature maps found in ${OUTPUT_DIR}/${SUBJECT}/"
    echo "Make sure temperature analysis completed successfully first."
    exit 1
fi

echo "Found ${#TEMP_MAPS[@]} temperature analysis results."
echo "Using output directory: ${OUTPUT_DIR}"
echo "Processing subject: ${SUBJECT}"

# Create logs directory
mkdir -p logs

# Submit report generation job
echo "Submitting report generation job..."
JOB1=$(qsub -v OUTPUT_DIR=${OUTPUT_DIR} 08_generate_reports.sh)
echo "Submitted report job: ${JOB1}"

# Create summary file
SUMMARY_FILE="reports_job_$(date +%Y%m%d_%H%M%S).txt"
cat > ${SUMMARY_FILE} << EOL
Report generation submitted at: $(date)
Output directory: ${OUTPUT_DIR}
Subject: ${SUBJECT}
Number of analyses found: ${#TEMP_MAPS[@]}
Report job: ${JOB1}
EOL

echo "========================================"
echo "Report generation job submitted successfully!"
echo "Job ID: ${JOB1}"
echo "Monitor with: qstat -u \$USER"
echo "Reports will be in: ${OUTPUT_DIR}/${SUBJECT}/comprehensive_report/"
echo "Job info saved to: ${SUMMARY_FILE}"
echo "========================================"

echo ""
echo "Next steps after reports complete:"
echo "1. Check logs: tail -f logs/08_reports.out"
echo "2. View HTML report: ${OUTPUT_DIR}/${SUBJECT}/comprehensive_report/report.html"
echo "3. Check histograms: ${OUTPUT_DIR}/${SUBJECT}/histograms/"