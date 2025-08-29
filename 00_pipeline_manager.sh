#!/bin/bash

# ==============================================================================
# Pipeline Manager - Orchestrates the entire CSF temperature analysis pipeline
# Using PBS job dependencies for efficient scheduling
# ==============================================================================

set -e

echo "========================================"
echo "CSF Temperature Pipeline Manager"
echo "Started at: $(date)"
echo "========================================"

# Parse command line arguments
SKIP_PREPROC=false
EXISTING_OUTPUT_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-preprocessing)
            SKIP_PREPROC=true
            shift
            ;;
        --output-dir)
            EXISTING_OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--skip-preprocessing --output-dir /path/to/existing/output]"
            exit 1
            ;;
    esac
done

# Check if logs directory exists
mkdir -p logs

if [ "$SKIP_PREPROC" = true ]; then
    if [ -z "$EXISTING_OUTPUT_DIR" ]; then
        echo "ERROR: --output-dir must be specified when using --skip-preprocessing"
        exit 1
    fi
    
    if [ ! -d "$EXISTING_OUTPUT_DIR" ]; then
        echo "ERROR: Output directory does not exist: $EXISTING_OUTPUT_DIR"
        exit 1
    fi
    
    OUTPUT_DIR="$EXISTING_OUTPUT_DIR"
    echo "Skipping preprocessing, using existing output directory: ${OUTPUT_DIR}"
    
    # Verify required files exist
    SUBJECT=$(python3 -c "import json; print(json.load(open('pipeline_config.json'))['subjects'][0])")
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
            echo "Cannot skip preprocessing without all required files."
            exit 1
        fi
    done
    echo "All required preprocessing outputs found."
    
    # Submit only the analysis, stability and report jobs
    echo "Step 1: Submitting b-value sweep analysis job..."
    JOB2=$(qsub -v OUTPUT_DIR=${OUTPUT_DIR} 04_run_bvalue_sweep.sh)
    echo "Submitted analysis job: ${JOB2}"
    
    echo "Step 2: Submitting stability analysis job..."
    JOB3=$(qsub -W depend=afterok:${JOB2} -v OUTPUT_DIR=${OUTPUT_DIR} 09_analyze_stability.sh)
    echo "Submitted stability analysis job: ${JOB3}"
    
    echo "Step 3: Submitting report generation job..."
    JOB4=$(qsub -W depend=afterok:${JOB2}:${JOB3} -v OUTPUT_DIR=${OUTPUT_DIR} 08_generate_reports.sh)
    echo "Submitted report generation job: ${JOB4}"
    
    echo "========================================"
    echo "Jobs submitted successfully (preprocessing skipped)!"
    echo "Job chain: ${JOB2} -> (${JOB3}, ${JOB4})"
    
else
    # Normal pipeline execution with preprocessing
    TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
    BASE_OUTPUT_DIR=$(python3 -c "import json; print(json.load(open('pipeline_config.json'))['paths']['base_output'])")
    OUTPUT_DIR="${BASE_OUTPUT_DIR}/temp_pipeline_${TIMESTAMP}"
    
    echo "Pipeline output directory: ${OUTPUT_DIR}"
    
    # Step 1: Submit preprocessing job with OUTPUT_DIR
    echo "Step 1: Submitting preprocessing job..."
    JOB1=$(qsub -v OUTPUT_DIR=${OUTPUT_DIR},TIMESTAMP=${TIMESTAMP} 01_run_preprocessing.sh)
    echo "Submitted preprocessing job: ${JOB1}"
    
    # Step 2: Submit b-value sweep analysis (depends on preprocessing)
    echo "Step 2: Submitting b-value sweep analysis job..."
    JOB2=$(qsub -W depend=afterok:${JOB1} -v OUTPUT_DIR=${OUTPUT_DIR} 04_run_bvalue_sweep.sh)
 S   echo "Submitted analysis job: ${JOB2}"
    
    # Step 3: Submit stability analysis (depends on b-value sweep)
    echo "Step 3: Submitting temperature stability analysis..."
    JOB3=$(qsub -W depend=afterok:${JOB2} -v OUTPUT_DIR=${OUTPUT_DIR} 09_analyze_stability.sh)
    echo "Submitted stability analysis job: ${JOB3}"

    # Step 4: Submit final report generation (depends on both analysis and stability)
    echo "Step 4: Submitting report generation job..."
    JOB4=$(qsub -W depend=afterok:${JOB2}:${JOB3} -v OUTPUT_DIR=${OUTPUT_DIR} 08_generate_reports.sh)
    echo "Submitted report generation job: ${JOB4}"
    echo "========================================"
    echo "All jobs submitted successfully!"
    echo "Job chain: ${JOB1} -> ${JOB2} -> (${JOB3}, ${JOB4})"
fi

echo "Use 'qstat -u \$USER' to monitor job progress"
echo "Results will be in: ${OUTPUT_DIR}"
echo "========================================"

# Create a summary file with job information
SUMMARY_FILE="pipeline_jobs_$(date +%Y%m%d_%H%M%S).txt"
cat > ${SUMMARY_FILE} << EOL
Pipeline submitted at: $(date)
Output directory: ${OUTPUT_DIR}
Preprocessing skipped: ${SKIP_PREPROC}
EOL

if [ "$SKIP_PREPROC" = false ]; then
    echo "Preprocessing job: ${JOB1}" >> ${SUMMARY_FILE}
fi
echo "Analysis job: ${JOB2}" >> ${SUMMARY_FILE}
echo "Stability job: ${JOB3}" >> ${SUMMARY_FILE}
echo "Report job: ${JOB4}" >> ${SUMMARY_FILE}

echo "Job information saved to ${SUMMARY_FILE}"