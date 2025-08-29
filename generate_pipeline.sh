#!/bin/bash

# ==============================================================================
#
#           generate_updated_pipeline.sh
#
# This script generates the updated, optimized CSF Temperature Pipeline scripts
# with improved error handling, automation, and analysis capabilities.
#
# Usage:
#   1. Save this file as generate_updated_pipeline.sh
#   2. Make it executable: chmod +x generate_updated_pipeline.sh
#   3. Run it: ./generate_updated_pipeline.sh
#
# ==============================================================================

echo "--- Generating updated CSF Temperature Pipeline scripts... ---"

# --- Create pipeline configuration file ---
cat << 'EOF' > pipeline_config.json
{
    "paths": {
        "bids_root": "/g/data/hl36/cb4095/WAND/WAND",
        "base_output": "/g/data/hl36/cb4095/WAND/derivatives",
        "fsl_dir": "/g/data/vp06/Christian/software/fsl",
        "mrtrix3_bin": "/g/data/vp06/Christian/software/mrtrix3/bin",
        "mrtrix3tissue_bin": "/g/data/vp06/Christian/software/MRtrix3Tissue/bin",
        "conda_env": "/g/data/vp06/Christian/software/Envs/miniconda3/envs/mrtrix_env"
    },
    "processing": {
        "csf_threshold": 0.05,
        "bvalue_tolerance": 20,
        "temperature_constants": {
            "A": 2256.74,
            "B": 4.39221
        }
    },
    "subjects": [],
    "bvalue_sets": [
        [0, 200],
        [0, 500],
        [0, 1200],
        [0, 2400],
        [0, 4000],
        [0, 6000],
        [0, 200, 500],
        [0, 200, 500, 1200],
        [0, 200, 500, 1200, 2400],
        [0, 200, 500, 1200, 2400]
    ]
}
EOF
echo "Generated pipeline_config.json"

# --- Script 1: Pipeline Manager ---
cat << 'EOF' > 00_pipeline_manager.sh
#!/bin/bash

# ==============================================================================
# Pipeline Manager - Orchestrates the entire CSF temperature analysis pipeline
# ==============================================================================

set -e

echo "========================================"
echo "CSF Temperature Pipeline Manager"
echo "Started at: $(date)"
echo "========================================"

# Check if logs directory exists
mkdir -p logs

# Step 1: Submit preprocessing job and wait for completion
echo "Step 1: Submitting preprocessing job..."
PREPROC_JOB_ID=$(qsub 01_run_preprocessing.sh)
echo "Preprocessing job submitted with ID: ${PREPROC_JOB_ID}"

# Wait for job to complete
while [ $(qstat -f ${PREPROC_JOB_ID} 2>/dev/null | grep -c "job_state = R\|job_state = Q") -gt 0 ]; do
    echo "Waiting for preprocessing to complete... ($(date))"
    sleep 30
done

# Check if preprocessing was successful
if [ ! -f logs/01_preproc.out ]; then
    echo "ERROR: Preprocessing log file not found!"
    exit 1
fi

# Extract the output directory from the preprocessing log
OUTPUT_DIR=$(grep "All outputs for this run will be saved in:" logs/01_preproc.out | awk '{print $NF}')

if [ -z "${OUTPUT_DIR}" ]; then
    echo "ERROR: Could not extract output directory from preprocessing log!"
    exit 1
fi

echo "Preprocessing complete. Output directory: ${OUTPUT_DIR}"

# Step 2: Submit b-value sweep analysis
echo "Step 2: Submitting b-value sweep analysis..."
ANALYSIS_JOB_ID=$(qsub -v OUTPUT_DIR="${OUTPUT_DIR}" 03_run_bvalue_sweep.sh)
echo "Analysis job submitted with ID: ${ANALYSIS_JOB_ID}"

# Wait for analysis to complete
while [ $(qstat -f ${ANALYSIS_JOB_ID} 2>/dev/null | grep -c "job_state = R\|job_state = Q") -gt 0 ]; do
    echo "Waiting for analysis to complete... ($(date))"
    sleep 30
done

echo "Analysis complete!"

# Step 3: Generate visualizations and reports
echo "Step 3: Generating visualizations and comprehensive report..."

# Load modules needed for Python
module load gcc/11.1.0
export PATH=/g/data/vp06/Christian/software/mrtrix3/bin:${PATH}
CONDA_ENV_PATH="/g/data/vp06/Christian/software/Envs/miniconda3/envs/mrtrix_env"
source "${CONDA_ENV_PATH%/*/*}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV_PATH}"

# Get subject from config
SUBJECT=$(python -c "import json; print(json.load(open('pipeline_config.json'))['subjects'][0])")

# Generate histograms
python 05_create_histograms.py "${SUBJECT}" "${OUTPUT_DIR}"

# Generate comprehensive analysis
python 06_comprehensive_analysis.py "${SUBJECT}" "${OUTPUT_DIR}"

echo "========================================"
echo "Pipeline completed successfully!"
echo "Results are in: ${OUTPUT_DIR}"
echo "Finished at: $(date)"
echo "========================================"
EOF
chmod +x 00_pipeline_manager.sh
echo "Generated 00_pipeline_manager.sh"

# --- Script 2: Preprocessing submission script ---
cat << 'EOF' > 01_run_preprocessing.sh
#!/bin/bash
#PBS -l ncpus=8,mem=32GB,jobfs=40GB,walltime=04:00:00
#PBS -q gpuq
#PBS -l ngpus=1
#PBS -l gputype=V100
#PBS -P vp06
#PBS -l storage=gdata/vp06+scratch/vp06+gdata/hl36
#PBS -l wd
#PBS -N Preproc_Temp_Pipeline
#PBS -o logs/01_preproc.out
#PBS -e logs/01_preproc.err

# --- 1. LOAD CONFIGURATION ---
CONFIG_FILE="pipeline_config.json"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file ${CONFIG_FILE} not found!"
    exit 1
fi

# Parse configuration using Python
SUBJECTS=$(python -c "import json; print(' '.join(json.load(open('${CONFIG_FILE}'))['subjects']))")
BIDS_ROOT=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['bids_root'])")
BASE_OUTPUT_DIR=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['base_output'])")
FSLDIR=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['fsl_dir'])")
MRTRIX3_BIN=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['mrtrix3_bin'])")
MRTRIX3TISSUE_BIN=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['mrtrix3tissue_bin'])")
CONDA_ENV_PATH=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['conda_env'])")

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
OUTPUT_DIR="${BASE_OUTPUT_DIR}/temp_pipeline_${TIMESTAMP}"

# --- 2. ENVIRONMENT SETUP ---
set -e
echo "--- Job started on $(hostname) at $(date) ---"
mkdir -p "${OUTPUT_DIR}"
mkdir -p logs
echo "All outputs for this run will be saved in: ${OUTPUT_DIR}"

# Save configuration to output directory for reproducibility
cp "${CONFIG_FILE}" "${OUTPUT_DIR}/pipeline_config.json"

module load gcc/11.1.0
module load cuda/11.2.2

export FSLDIR=${FSLDIR}
export PATH=${FSLDIR}/bin:${PATH}
export PATH=${MRTRIX3_BIN}:${PATH}

source "${CONDA_ENV_PATH%/*/*}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV_PATH}"
export MRTRIX_TMPFILE_DIR=${PBS_JOBFS}

# --- 3. EXECUTION ---
for subject in ${SUBJECTS}; do
    echo "=================================================="
    echo "         STARTING PREPROCESSING FOR ${subject}"
    echo "=================================================="
    
    python -u 02_preprocess_subject.py \
        "${subject}" \
        "${BIDS_ROOT}" \
        "${OUTPUT_DIR}" \
        --mrtrix3tissue_bin "${MRTRIX3TISSUE_BIN}" \
        --jobfs_path "${PBS_JOBFS}" \
        --config_file "${CONFIG_FILE}"
        
    echo "--- Finished preprocessing for ${subject} ---"
done

echo "--- Preprocessing job finished successfully at $(date) ---"
EOF
chmod +x 01_run_preprocessing.sh
echo "Generated 01_run_preprocessing.sh"

# --- Script 3: Enhanced preprocessing Python script ---
cat << 'EOF' > 02_preprocess_subject.py
#!/usr/bin/env python3
import os, sys, subprocess, argparse, json, glob, logging
from datetime import datetime

def setup_logging(log_file):
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def run_command(cmd, log_file, logger):
    """Run a command with proper logging and error handling"""
    cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
    shell_mode = isinstance(cmd, str)
    logger.info(f"RUNNING: {cmd_str}")
    
    with open(log_file, 'a') as f:
        f.write(f"\n--- RUNNING: {cmd_str}\n")
        result = subprocess.run(cmd_str, stdout=f, stderr=subprocess.STDOUT, 
                               text=True, check=False, shell=shell_mode)
    
    if result.returncode != 0:
        logger.error(f"Command failed with exit code {result.returncode}")
        sys.exit(1)
    
    logger.info("SUCCESS")
    return result

def validate_inputs(subject_id, bids_root, logger):
    """Validate that all required input files exist"""
    logger.info("Validating input files...")
    
    required_files = {
        'dwi_ap_nii': os.path.join(bids_root, subject_id, 'ses-02', 'dwi', 
                                   f'{subject_id}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.nii.gz'),
        'dwi_ap_bvec': os.path.join(bids_root, subject_id, 'ses-02', 'dwi', 
                                    f'{subject_id}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.bvec'),
        'dwi_ap_bval': os.path.join(bids_root, subject_id, 'ses-02', 'dwi', 
                                    f'{subject_id}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.bval'),
        'dwi_pa_nii': os.path.join(bids_root, subject_id, 'ses-02', 'dwi', 
                                   f'{subject_id}_ses-02_acq-CHARMED_dir-PA_part-mag_dwi.nii.gz'),
        'dwi_pa_bvec': os.path.join(bids_root, subject_id, 'ses-02', 'dwi', 
                                    f'{subject_id}_ses-02_acq-CHARMED_dir-PA_part-mag_dwi.bvec'),
        'dwi_pa_bval': os.path.join(bids_root, subject_id, 'ses-02', 'dwi', 
                                    f'{subject_id}_ses-02_acq-CHARMED_dir-PA_part-mag_dwi.bval')
    }
    
    all_valid = True
    for name, path in required_files.items():
        if not os.path.exists(path):
            logger.error(f"Required file not found: {name} at {path}")
            all_valid = False
        else:
            logger.info(f"Found {name}")
    
    if not all_valid:
        logger.error("Input validation failed!")
        sys.exit(1)
    
    logger.info("All input files validated successfully")
    return required_files

def main():
    parser = argparse.ArgumentParser(description="Enhanced preprocessing pipeline with validation.")
    parser.add_argument("subject_id")
    parser.add_argument("bids_root")
    parser.add_argument("output_dir")
    parser.add_argument("--mrtrix3tissue_bin")
    parser.add_argument("--jobfs_path")
    parser.add_argument("--config_file")
    args = parser.parse_args()

    # Setup output directories and logging
    sub_out_dir = os.path.join(args.output_dir, args.subject_id)
    os.makedirs(sub_out_dir, exist_ok=True)
    log_file = os.path.join(sub_out_dir, 'log_02_preprocessing.txt')
    if os.path.exists(log_file): 
        os.remove(log_file)
    
    logger = setup_logging(log_file)
    logger.info(f"=== Starting Enhanced Preprocessing for: {args.subject_id} ===")
    logger.info(f"Start time: {datetime.now()}")
    
    # Load configuration
    with open(args.config_file, 'r') as f:
        config = json.load(f)
    logger.info(f"Loaded configuration from: {args.config_file}")
    
    # Validate inputs
    file_paths = validate_inputs(args.subject_id, args.bids_root, logger)
    
    # Define all file paths
    ap_mif = os.path.join(args.jobfs_path, 'AP.mif')
    pa_mif = os.path.join(args.jobfs_path, 'PA.mif')
    dwi_den_unring = os.path.join(args.jobfs_path, 'dwi_denoised_unringed.mif')
    b0_pair = os.path.join(args.jobfs_path, 'b0_pair.mif')
    
    preproc_dwi = os.path.join(sub_out_dir, 'dwi_preproc.mif')
    preproc_dwi_unbiased = os.path.join(sub_out_dir, 'dwi_preproc_unbiased.mif')
    dwi_mask = os.path.join(sub_out_dir, 'dwi_mask.mif')
    dwi_upsampled = os.path.join(sub_out_dir, 'dwi_upsampled.mif')
    mask_upsampled = os.path.join(sub_out_dir, 'dwi_mask_upsampled.mif')
    
    # Processing steps
    logger.info("Step 1: Converting DWI data to MIF format")
    run_command(['mrconvert', file_paths['dwi_ap_nii'], ap_mif, '-fslgrad', 
                 file_paths['dwi_ap_bvec'], file_paths['dwi_ap_bval'], '-force'], log_file, logger)
    run_command(['mrconvert', file_paths['dwi_pa_nii'], pa_mif, '-fslgrad', 
                 file_paths['dwi_pa_bvec'], file_paths['dwi_pa_bval'], '-force'], log_file, logger)
    
    logger.info("Step 2: Denoising and unringing")
    run_command(f"dwidenoise {ap_mif} - -force | mrdegibbs - {dwi_den_unring} -force", log_file, logger)
    
    logger.info("Step 3: Extracting b0 pairs for distortion correction")
    run_command(f"dwiextract {dwi_den_unring} - -bzero -force | mrmath - mean - -axis 3 -force | "
                f"mrcat - {pa_mif} {b0_pair} -axis 3 -force", log_file, logger)
    
    logger.info("Step 4: Running FSL preprocessing with GPU acceleration")
    run_command(['dwifslpreproc', dwi_den_unring, preproc_dwi, '-pe_dir', 'AP', '-rpe_pair', 
                 '-se_epi', b0_pair, '-eddy_options', ' --slm=linear --data_is_shelled', 
                 '-scratch', args.jobfs_path, '-force', '-cuda'], log_file, logger)
    
    logger.info("Step 5: Bias field correction")
    run_command(['dwibiascorrect', 'ants', preproc_dwi, preproc_dwi_unbiased, '-force'], log_file, logger)
    
    logger.info("Step 6: Creating brain mask")
    run_command(['dwi2mask', preproc_dwi_unbiased, dwi_mask, '-force'], log_file, logger)
    
    logger.info("Step 7: Upsampling to 1.5mm isotropic")
    run_command(['mrgrid', preproc_dwi_unbiased, 'regrid', dwi_upsampled, '-voxel', '1.5', '-force'], log_file, logger)
    run_command(f"mrgrid {dwi_mask} regrid - -template {dwi_upsampled} -interp linear -datatype bit -force | "
                f"maskfilter - median {mask_upsampled} -force", log_file, logger)

    # Multi-tissue CSD
    logger.info("Step 8: Estimating tissue response functions")
    dwi2response_cmd = os.path.join(args.mrtrix3tissue_bin, 'dwi2response')
    mtnormalise_cmd = os.path.join(args.mrtrix3tissue_bin, 'mtnormalise')
    resp_wm = os.path.join(sub_out_dir, 'response_wm.txt')
    resp_gm = os.path.join(sub_out_dir, 'response_gm.txt')
    resp_csf = os.path.join(sub_out_dir, 'response_csf.txt')
    wmfod = os.path.join(sub_out_dir, 'wmfod.mif')
    gm = os.path.join(sub_out_dir, 'gm.mif')
    csf = os.path.join(sub_out_dir, 'csf.mif')
    wmfod_norm = os.path.join(sub_out_dir, 'wmfod_norm.mif')
    gm_norm = os.path.join(sub_out_dir, 'gm_norm.mif')
    csf_norm = os.path.join(sub_out_dir, 'csf_norm.mif')
    
    run_command([dwi2response_cmd, 'dhollander', preproc_dwi_unbiased, resp_wm, resp_gm, resp_csf, '-force'], 
                log_file, logger)
    
    logger.info("Step 9: Multi-shell multi-tissue CSD")
    run_command(['dwi2fod', 'msmt_csd', dwi_upsampled, resp_wm, wmfod, resp_gm, gm, resp_csf, csf, 
                 '-mask', mask_upsampled, '-force'], log_file, logger)
    
    logger.info("Step 10: Multi-tissue normalization")
    run_command([mtnormalise_cmd, wmfod, wmfod_norm, gm, gm_norm, csf, csf_norm, 
                 '-mask', mask_upsampled, '-force'], log_file, logger)
    
    # Save preprocessing summary
    summary = {
        'subject_id': args.subject_id,
        'preprocessing_date': datetime.now().isoformat(),
        'output_directory': sub_out_dir,
        'processing_steps': [
            'DWI denoising', 'Gibbs ringing removal', 'Distortion correction',
            'Bias field correction', 'Brain masking', 'Upsampling to 1.5mm',
            'Response function estimation', 'Multi-tissue CSD', 'Intensity normalization'
        ],
        'final_outputs': {
            'preprocessed_dwi': 'dwi_preproc_unbiased.mif',
            'upsampled_dwi': 'dwi_upsampled.mif',
            'brain_mask': 'dwi_mask_upsampled.mif',
            'csf_map': 'csf_norm.mif'
        }
    }
    
    with open(os.path.join(sub_out_dir, 'preprocessing_summary.json'), 'w') as f:
        json.dump(summary, f, indent=4)
    
    logger.info(f"=== Preprocessing complete for: {args.subject_id} ===")
    logger.info(f"End time: {datetime.now()}")

if __name__ == "__main__":
    main()
EOF
chmod +x 02_preprocess_subject.py
echo "Generated 02_preprocess_subject.py"

# --- Script 4: B-value sweep with array job support ---
cat << 'EOF' > 03_run_bvalue_sweep.sh
#!/bin/bash
#PBS -l ncpus=2,mem=16GB,jobfs=20GB,walltime=02:00:00
#PBS -q normal
#PBS -P vp06
#PBS -l storage=gdata/vp06+scratch/vp06+gdata/hl36
#PBS -l wd
#PBS -N TempBvalSweep
#PBS -o logs/03_bvalue_sweep.out
#PBS -e logs/03_bvalue_sweep.err

# --- 1. CONFIGURATION ---
CONFIG_FILE="pipeline_config.json"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file ${CONFIG_FILE} not found!"
    exit 1
fi

# Get configuration values
SUBJECT=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['subjects'][0])")
BIDS_ROOT=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['bids_root'])")
FSLDIR=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['fsl_dir'])")
MRTRIX3_BIN=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['mrtrix3_bin'])")
CONDA_ENV_PATH=$(python -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['conda_env'])")

# OUTPUT_DIR should be passed as environment variable from pipeline manager
if [ -z "${OUTPUT_DIR}" ]; then
    echo "ERROR: OUTPUT_DIR environment variable not set!"
    echo "This script should be called by the pipeline manager or with -v OUTPUT_DIR=..."
    exit 1
fi

# --- 2. ENVIRONMENT SETUP ---
set -e
echo "--- Job started on $(hostname) at $(date) ---"
echo "--- Processing subject: ${SUBJECT} ---"
echo "--- Output directory: ${OUTPUT_DIR} ---"
mkdir -p logs

module load gcc/11.1.0
export FSLDIR=${FSLDIR}
export PATH=${FSLDIR}/bin:${PATH}
export PATH=${MRTRIX3_BIN}:${PATH}
source "${CONDA_ENV_PATH%/*/*}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV_PATH}"
export MRTRIX_TMPFILE_DIR=${PBS_JOBFS}

# --- 3. EXECUTION ---
echo "--- Starting b-value analysis sweep for subject: ${SUBJECT} ---"

# Get total number of b-value sets from config
TOTAL_BVAL_SETS=$(python -c "import json; print(len(json.load(open('${CONFIG_FILE}'))['bvalue_sets']))")

echo "--- Processing ${TOTAL_BVAL_SETS} b-value combinations ---"

# Process all b-value sets
for i in $(seq 0 $((TOTAL_BVAL_SETS - 1))); do
    # Get b-values for this index
    BVALS_STR=$(python -c "import json; print(' '.join(map(str, json.load(open('${CONFIG_FILE}'))['bvalue_sets'][${i}])))")
    
    # Create suffix from b-values
    SUFFIX=$(echo "${BVALS_STR}" | sed 's/ /_/g' | sed 's/^/b/')
    
    RUN_LOG_FILE="logs/calc_${SUBJECT}_${SUFFIX}.out"
    
    echo "--------------------------------------------------"
    echo "       Running analysis ${i}: ${SUFFIX}"
    echo "       B-values: ${BVALS_STR}"
    echo "       Detailed log: ${RUN_LOG_FILE}"
    echo "--------------------------------------------------"

    python -u 04_calculate_temperature.py \
        "${SUBJECT}" \
        "${OUTPUT_DIR}" \
        "${BIDS_ROOT}" \
        --bvals_for_adc ${BVALS_STR} \
        --output_suffix "${SUFFIX}" \
        --config_file "${CONFIG_FILE}" > "${RUN_LOG_FILE}" 2>&1

    if [ $? -eq 0 ]; then
        echo "--- Successfully completed analysis: ${SUFFIX} ---"
    else
        echo "!!! ERROR in analysis: ${SUFFIX} - check ${RUN_LOG_FILE} !!!"
    fi
done

echo "--- All b-value analyses complete. Job finished at $(date) ---"
EOF
chmod +x 03_run_bvalue_sweep.sh
echo "Generated 03_run_bvalue_sweep.sh"

# --- Script 5: Enhanced temperature calculation ---
cat << 'EOF' > 04_calculate_temperature.py
#!/usr/bin/env python3
import os, sys, subprocess, argparse, numpy as np, nibabel as nib, matplotlib.pyplot as plt
import pandas as pd, json, logging, warnings
from datetime import datetime

warnings.filterwarnings('ignore')

def setup_logging(log_file):
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='a'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def run_command(cmd, log_file, logger):
    """Run a command with proper logging and error handling"""
    cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
    shell_mode = isinstance(cmd, str)
    logger.info(f"RUNNING: {cmd_str}")
    
    with open(log_file, 'a') as f:
        f.write(f"\n--- RUNNING: {cmd_str}\n")
        result = subprocess.run(cmd_str, stdout=f, stderr=subprocess.STDOUT, 
                               text=True, check=False, shell=shell_mode)
    
    if result.returncode != 0:
        logger.error(f"Command failed with exit code {result.returncode}")
        sys.exit(1)
    
    logger.info("SUCCESS")

def calculate_quality_metrics(adc_data, csf_mask, temp_data, logger):
    """Calculate quality control metrics for temperature estimation"""
    logger.info("Calculating quality control metrics...")
    
    # Get valid voxels
    valid_mask = (csf_mask > 0) & np.isfinite(adc_data) & (adc_data > 0)
    adc_values = adc_data[valid_mask]
    temp_values = temp_data[valid_mask]
    
    metrics = {
        'adc_mean': np.mean(adc_values) if len(adc_values) > 0 else 0,
        'adc_median': np.median(adc_values) if len(adc_values) > 0 else 0,
        'adc_std': np.std(adc_values) if len(adc_values) > 0 else 0,
        'adc_min': np.min(adc_values) if len(adc_values) > 0 else 0,
        'adc_max': np.max(adc_values) if len(adc_values) > 0 else 0,
        'adc_outliers_low': np.sum(adc_values < 1e-3) if len(adc_values) > 0 else 0,
        'adc_outliers_high': np.sum(adc_values > 4e-3) if len(adc_values) > 0 else 0,
        'temp_physiological_fraction': np.sum((temp_values > 35) & (temp_values < 39)) / len(temp_values) if len(temp_values) > 0 else 0,
        'temp_below_35': np.sum(temp_values < 35) if len(temp_values) > 0 else 0,
        'temp_above_39': np.sum(temp_values > 39) if len(temp_values) > 0 else 0,
        'csf_volume_ml': np.sum(csf_mask > 0) * 1.5**3 / 1000  # assuming 1.5mm isotropic
    }
    
    logger.info(f"Quality metrics calculated: {len(temp_values)} valid voxels")
    return metrics

def main():
    parser = argparse.ArgumentParser(description="Enhanced temperature calculation with QC metrics.")
    parser.add_argument("subject_id")
    parser.add_argument("output_dir")
    parser.add_argument("bids_root")
    parser.add_argument("--bvals_for_adc", type=int, nargs='+')
    parser.add_argument("--output_suffix", type=str, required=True)
    parser.add_argument("--config_file", type=str, required=True)
    args = parser.parse_args()

    # Setup directories and logging
    sub_out_dir = os.path.join(args.output_dir, args.subject_id)
    tmp_dir = os.path.join(sub_out_dir, f'tmp_{args.output_suffix}')
    os.makedirs(tmp_dir, exist_ok=True)
    
    log_file = os.path.join(sub_out_dir, f'log_calc_{args.output_suffix}.txt')
    logger = setup_logging(log_file)
    
    logger.info(f"=== Starting Temperature Calculation ===")
    logger.info(f"Subject: {args.subject_id}")
    logger.info(f"Analysis: {args.output_suffix}")
    logger.info(f"B-values: {args.bvals_for_adc}")
    logger.info(f"Start time: {datetime.now()}")
    
    # Load configuration
    with open(args.config_file, 'r') as f:
        config = json.load(f)
    
    # Define file paths
    dwi_upsampled = os.path.join(sub_out_dir, 'dwi_upsampled.mif')
    csf_norm_map = os.path.join(sub_out_dir, 'csf_norm.mif')
    dwi_ap_bval = os.path.join(args.bids_root, args.subject_id, 'ses-02', 'dwi', 
                               f'{args.subject_id}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.bval')
    
    # Check if required files exist
    required_files = [dwi_upsampled, csf_norm_map, dwi_ap_bval]
    for f in required_files:
        if not os.path.exists(f):
            logger.error(f"Required file not found: {f}")
            sys.exit(1)
    
    # Output files
    adc_map_full = os.path.join(sub_out_dir, f'adc_map_full_{args.output_suffix}.mif')
    csf_mask_raw = os.path.join(sub_out_dir, f'csf_mask_raw_{args.output_suffix}.mif')
    csf_mask_cleaned = os.path.join(sub_out_dir, f'csf_mask_cleaned_{args.output_suffix}.mif')
    adc_map_masked_safe = os.path.join(sub_out_dir, f'adc_map_masked_safe_{args.output_suffix}.mif')
    temp_map_masked = os.path.join(sub_out_dir, f'temperature_map_{args.output_suffix}.mif')

    logger.info("Step 1: Calculating ADC map")
    dwi_reduced = os.path.join(tmp_dir, 'dwi_reduced.mif')
    dwi_adc_raw = os.path.join(tmp_dir, 'dwi_adc_raw.mif')
    
    # Load b-values and select indices
    bvals = np.loadtxt(dwi_ap_bval)
    bvalue_tolerance = config['processing']['bvalue_tolerance']
    indices_to_keep = [i for i, b in enumerate(bvals) 
                      if any(np.isclose(b, target_b, atol=bvalue_tolerance) 
                            for target_b in args.bvals_for_adc)]
    
    if len(indices_to_keep) < 2:
        logger.error(f"Not enough b-values found! Requested: {args.bvals_for_adc}, Found indices: {indices_to_keep}")
        sys.exit(1)
    
    logger.info(f"Selected {len(indices_to_keep)} volumes with b-values: {[bvals[i] for i in indices_to_keep]}")
    indices_str = ",".join(map(str, indices_to_keep))
    
    run_command(['mrconvert', dwi_upsampled, dwi_reduced, '-coord', '3', indices_str, '-force'], log_file, logger)
    run_command(['dwi2adc', dwi_reduced, dwi_adc_raw, '-force'], log_file, logger)
    run_command(['mrconvert', dwi_adc_raw, adc_map_full, '-coord', '3', '1', '-force'], log_file, logger)

    logger.info("Step 2: Creating CSF mask")
    csf_threshold = config['processing']['csf_threshold']
    logger.info(f"Using CSF threshold: {csf_threshold}")
    run_command(['mrthreshold', csf_norm_map, '-abs', str(csf_threshold), csf_mask_raw, '-force'], log_file, logger)
    run_command(f"maskfilter {csf_mask_raw} erode - | maskfilter - dilate {csf_mask_cleaned} -force", log_file, logger)

    logger.info("Step 3: Applying mask and filtering non-physical ADC values")
    adc_map_masked = os.path.join(tmp_dir, 'adc_map_masked.mif')
    run_command(['mrcalc', adc_map_full, csf_mask_cleaned, '-mult', adc_map_masked, '-force'], log_file, logger)
    run_command(['mrcalc', adc_map_masked, '-finite', adc_map_masked, '0', '-if', adc_map_masked_safe, '-force'], 
                log_file, logger)
    
    logger.info("Step 4: Calculating temperature map")
    A = config['processing']['temperature_constants']['A']
    B = config['processing']['temperature_constants']['B']
    logger.info(f"Using temperature constants: A={A}, B={B}")
    
    temp_calc_cmd = (f"mrcalc {adc_map_masked_safe} 0 -gt {A} {B} {adc_map_masked_safe} -divide "
                    f"-log -divide 273.15 -subtract 0 -if {temp_map_masked} -force")
    run_command(temp_calc_cmd, log_file, logger)

    logger.info("Step 5: Generating statistics and quality control metrics")
    
    # Convert to NIfTI for analysis
    temp_nii_path = os.path.join(tmp_dir, 'temp_map_masked.nii.gz')
    adc_nii_path = os.path.join(tmp_dir, 'adc_map_masked_safe.nii.gz')
    csf_mask_nii_path = os.path.join(tmp_dir, 'csf_mask_cleaned.nii.gz')
    
    run_command(['mrconvert', temp_map_masked, temp_nii_path, '-force', '-quiet'], log_file, logger)
    run_command(['mrconvert', adc_map_masked_safe, adc_nii_path, '-force', '-quiet'], log_file, logger)
    run_command(['mrconvert', csf_mask_cleaned, csf_mask_nii_path, '-force', '-quiet'], log_file, logger)
    
    temp_data = nib.load(temp_nii_path).get_fdata()
    adc_data = nib.load(adc_nii_path).get_fdata()
    csf_mask_data = nib.load(csf_mask_nii_path).get_fdata()
    
    # Calculate quality metrics
    qc_metrics = calculate_quality_metrics(adc_data, csf_mask_data, temp_data, logger)
    
    # Calculate temperature statistics
    final_mask_bool = (csf_mask_data > 0)
    temp_values = temp_data[final_mask_bool]
    
    if len(temp_values) > 0:
        stats = {
            'subject_id': args.subject_id,
            'analysis': args.output_suffix,
            'b_values': '_'.join(map(str, args.bvals_for_adc)),
            'num_b_values': len(args.bvals_for_adc),
            'num_csf_voxels': len(temp_values),
            'temp_mean_C': np.mean(temp_values),
            'temp_median_C': np.median(temp_values),
            'temp_std_C': np.std(temp_values),
            'temp_min_C': np.min(temp_values),
            'temp_max_C': np.max(temp_values),
            'temp_q25_C': np.percentile(temp_values, 25),
            'temp_q75_C': np.percentile(temp_values, 75)
        }
        # Add QC metrics to stats
        stats.update(qc_metrics)
        
        # Save raw temperature values
        raw_values_txt = os.path.join(sub_out_dir, f'temperature_values_{args.output_suffix}.txt')
        np.savetxt(raw_values_txt, temp_values, fmt='%.4f')
        logger.info(f"Raw temperature values saved to: {raw_values_txt}")
    else:
        logger.warning("No valid temperature values found!")
        stats = {
            'subject_id': args.subject_id,
            'analysis': args.output_suffix,
            'b_values': '_'.join(map(str, args.bvals_for_adc)),
            'num_b_values': len(args.bvals_for_adc),
            'num_csf_voxels': 0,
            'temp_mean_C': 0,
            'temp_median_C': 0,
            'temp_std_C': 0,
            'temp_min_C': 0,
            'temp_max_C': 0,
            'temp_q25_C': 0,
            'temp_q75_C': 0
        }
        stats.update({k: 0 for k in qc_metrics.keys()})

    # Save statistics
    stats_csv = os.path.join(sub_out_dir, f'temperature_stats_{args.output_suffix}.csv')
    pd.DataFrame([stats]).to_csv(stats_csv, index=False)
    logger.info(f"Statistics saved to: {stats_csv}")

    # Generate visualization
    logger.info("Step 6: Creating visualization")
    vis_png = os.path.join(sub_out_dir, f'temperature_visualization_{args.output_suffix}.png')
    
    # Load background image
    bg_nii_path = os.path.join(tmp_dir, 'dwi_upsampled.nii.gz')
    run_command(['mrconvert', dwi_upsampled, bg_nii_path, '-force', '-quiet'], log_file, logger)
    bg_data = nib.load(bg_nii_path).get_fdata()
    slice_idx = bg_data.shape[2] // 2

    # Create figure with multiple panels
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), facecolor='black')
    
    # Panel 1: Temperature map overlay
    ax = axes[0, 0]
    ax.imshow(np.rot90(bg_data[:, :, slice_idx, 0]), cmap='gray', 
              vmin=0, vmax=np.percentile(bg_data[..., 0], 98))
    temp_slice = np.rot90(temp_data[:, :, slice_idx])
    masked_temp_slice = np.ma.masked_where(~np.isfinite(temp_slice) | (temp_slice == 0), temp_slice)
    im = ax.imshow(masked_temp_slice, cmap='hot', alpha=0.8, vmin=30, vmax=45)
    ax.set_title(f'Temperature Map - {args.output_suffix}', color='white', fontsize=12)
    ax.axis('off')
    
    # Add colorbar
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Temperature (°C)', color='white')
    cbar.ax.tick_params(colors='white')
    
    # Panel 2: ADC map
    ax = axes[0, 1]
    adc_slice = np.rot90(adc_data[:, :, slice_idx])
    masked_adc_slice = np.ma.masked_where(adc_slice == 0, adc_slice)
    im2 = ax.imshow(masked_adc_slice, cmap='viridis', vmin=0, vmax=0.004)
    ax.set_title(f'ADC Map - {args.output_suffix}', color='white', fontsize=12)
    ax.axis('off')
    cbar2 = fig.colorbar(im2, ax=ax, fraction=0.046, pad=0.04)
    cbar2.set_label('ADC (mm²/s)', color='white')
    cbar2.ax.tick_params(colors='white')
    
    # Panel 3: Temperature histogram
    ax = axes[1, 0]
    if len(temp_values) > 0:
        ax.hist(temp_values, bins=50, color='orange', alpha=0.7, edgecolor='white')
        ax.axvline(np.mean(temp_values), color='red', linestyle='--', 
                  label=f'Mean: {np.mean(temp_values):.1f}°C')
        ax.axvline(np.median(temp_values), color='blue', linestyle='--', 
                  label=f'Median: {np.median(temp_values):.1f}°C')
        ax.set_xlabel('Temperature (°C)', color='white')
        ax.set_ylabel('Frequency', color='white')
        ax.set_title('Temperature Distribution', color='white')
        ax.legend()
        ax.tick_params(colors='white')
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
    else:
        ax.text(0.5, 0.5, 'No valid temperature values', 
                transform=ax.transAxes, ha='center', va='center', color='white')
        ax.set_xticks([])
        ax.set_yticks([])
    
    # Panel 4: Statistics text
    ax = axes[1, 1]
    ax.axis('off')
    stats_text = f"""Temperature Statistics
    
Mean: {stats['temp_mean_C']:.2f} °C
Median: {stats['temp_median_C']:.2f} °C
Std Dev: {stats['temp_std_C']:.2f} °C
Range: [{stats['temp_min_C']:.2f}, {stats['temp_max_C']:.2f}] °C

CSF Volume: {stats['csf_volume_ml']:.1f} mL
Voxels: {stats['num_csf_voxels']}

Quality Metrics:
Physiological fraction: {stats['temp_physiological_fraction']:.1%}
ADC outliers: {stats['adc_outliers_low'] + stats['adc_outliers_high']}
"""
    ax.text(0.1, 0.9, stats_text, transform=ax.transAxes, 
            va='top', ha='left', color='white', fontsize=10, family='monospace')
    
    plt.tight_layout()
    plt.savefig(vis_png, dpi=150, bbox_inches='tight', facecolor='black')
    plt.close()
    logger.info(f"Saved visualization: {vis_png}")
    
    logger.info(f"=== Temperature calculation complete ===")
    logger.info(f"End time: {datetime.now()}")

if __name__ == "__main__":
    main()
EOF
chmod +x 04_calculate_temperature.py
echo "Generated 04_calculate_temperature.py"

# --- Script 6: Enhanced histogram generation ---
cat << 'EOF' > 05_create_histograms.py
#!/usr/bin/env python3
import os, sys, argparse, glob, numpy as np, nibabel as nib, matplotlib.pyplot as plt
import seaborn as sns, subprocess, json, pandas as pd
from matplotlib.gridspec import GridSpec

def run_mrconvert(input_path, output_path):
    subprocess.run(['mrconvert', input_path, output_path, '-force', '-quiet'], check=True)
    return nib.load(output_path)

def main():
    parser = argparse.ArgumentParser(description="Generate enhanced histograms for temperature analysis.")
    parser.add_argument("subject_id")
    parser.add_argument("output_dir")
    args = parser.parse_args()

    sub_out_dir = os.path.join(args.output_dir, args.subject_id)
    histogram_dir = os.path.join(sub_out_dir, 'histograms')
    os.makedirs(histogram_dir, exist_ok=True)
    
    # Load configuration
    config_path = os.path.join(args.output_dir, 'pipeline_config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    sns.set_style("whitegrid")
    
    print(f"=== Generating Enhanced Histograms for Subject: {args.subject_id} ===")
    
    # Find all temperature maps
    search_pattern = os.path.join(sub_out_dir, 'temperature_map_*.mif')
    temp_map_files = sorted(glob.glob(search_pattern))
    
    if not temp_map_files:
        print(f"!!! ERROR: No temperature maps found matching pattern: {search_pattern}")
        sys.exit(1)
    
    print(f"Found {len(temp_map_files)} analysis runs to plot.")
    
    # Load all statistics for comparison
    all_stats = []
    for stats_file in glob.glob(os.path.join(sub_out_dir, 'temperature_stats_*.csv')):
        df = pd.read_csv(stats_file)
        all_stats.append(df.iloc[0].to_dict())
    
    # Create individual histograms
    for temp_map_path in temp_map_files:
        try:
            suffix = os.path.basename(temp_map_path).replace('temperature_map_', '').replace('.mif', '')
            print(f"\n--- Creating individual plot for analysis: {suffix} ---")
            
            csf_mask_path = os.path.join(sub_out_dir, f'csf_mask_cleaned_{suffix}.mif')
            if not os.path.exists(csf_mask_path):
                print(f"!!! WARNING: CSF mask not found, skipping: {csf_mask_path}")
                continue

            tmp_dir = os.path.join(sub_out_dir, f'tmp_{suffix}')
            os.makedirs(tmp_dir, exist_ok=True)
            
            # Convert to NIfTI
            temp_nii_path = os.path.join(tmp_dir, 'temp_map.nii.gz')
            temp_data = run_mrconvert(temp_map_path, temp_nii_path).get_fdata()
            mask_nii_path = os.path.join(tmp_dir, 'csf_mask.nii.gz')
            mask_data = run_mrconvert(csf_mask_path, mask_nii_path).get_fdata()

            plausible_temps = temp_data[(mask_data > 0) & np.isfinite(temp_data) & (temp_data > 0)]
            
            if plausible_temps.size == 0:
                print("!!! WARNING: No plausible temperature values found. Skipping plot.")
                continue

            # Create enhanced histogram
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [3, 1]})
            
            # Main histogram
            counts, bins, _ = ax1.hist(plausible_temps, bins=50, alpha=0.7, color='steelblue', 
                                       edgecolor='black', density=True)
            
            # Add KDE
            from scipy import stats
            kde = stats.gaussian_kde(plausible_temps)
            x_range = np.linspace(plausible_temps.min(), plausible_temps.max(), 200)
            ax1.plot(x_range, kde(x_range), 'r-', linewidth=2, label='KDE')
            
            # Add statistics
            mean_temp = np.mean(plausible_temps)
            median_temp = np.median(plausible_temps)
            std_temp = np.std(plausible_temps)
            
            ax1.axvline(mean_temp, color='green', linestyle='--', linewidth=2, 
                       label=f'Mean: {mean_temp:.1f}°C')
            ax1.axvline(median_temp, color='orange', linestyle='--', linewidth=2, 
                       label=f'Median: {median_temp:.1f}°C')
            
            # Add shaded regions for physiological range
            ax1.axvspan(35, 39, alpha=0.2, color='green', label='Physiological range')
            
            ax1.set_xlabel('Temperature (°C)', fontsize=12)
            ax1.set_ylabel('Density', fontsize=12)
            ax1.set_title(f'Temperature Distribution - {args.subject_id}\nAnalysis: {suffix}', fontsize=14)
            ax1.legend(loc='upper right')
            ax1.set_xlim(20, 50)
            
            # Box plot below
            ax2.boxplot(plausible_temps, vert=False, widths=0.7, patch_artist=True,
                       boxprops=dict(facecolor='lightblue'),
                       medianprops=dict(color='red', linewidth=2))
            ax2.set_xlabel('Temperature (°C)', fontsize=12)
            ax2.set_xlim(20, 50)
            ax2.set_yticks([])
            
            plt.tight_layout()
            output_plot_path = os.path.join(histogram_dir, f'histogram_{suffix}.png')
            plt.savefig(output_plot_path, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"Saved histogram to: {output_plot_path}")
            
        except Exception as e:
            print(f"!!! ERROR processing file {temp_map_path}: {e}")
            import traceback
            traceback.print_exc()

    # Create comparison plot if multiple analyses exist
    if len(temp_map_files) > 1:
        print("\n--- Creating comparison plot across all b-value combinations ---")
        
        fig = plt.figure(figsize=(14, 10))
        gs = GridSpec(3, 2, figure=fig, hspace=0.3, wspace=0.3)
        
        # Collect all temperature data
        all_temps = {}
        for temp_map_path in temp_map_files:
            suffix = os.path.basename(temp_map_path).replace('temperature_map_', '').replace('.mif', '')
            values_file = os.path.join(sub_out_dir, f'temperature_values_{suffix}.txt')
            if os.path.exists(values_file):
                all_temps[suffix] = np.loadtxt(values_file)
        
        # Plot 1: Overlaid distributions
        ax1 = fig.add_subplot(gs[0, :])
        for suffix, temps in all_temps.items():
            ax1.hist(temps, bins=30, alpha=0.3, density=True, label=suffix)
        ax1.set_xlabel('Temperature (°C)')
        ax1.set_ylabel('Density')
        ax1.set_title('Temperature Distributions - All B-value Combinations')
        ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        
        # Plot 2: Box plots comparison
        ax2 = fig.add_subplot(gs[1, :])
        data_for_box = [temps for temps in all_temps.values()]
        labels_for_box = list(all_temps.keys())
        bp = ax2.boxplot(data_for_box, labels=labels_for_box, patch_artist=True)
        for patch in bp['boxes']:
            patch.set_facecolor('lightblue')
        ax2.set_ylabel('Temperature (°C)')
        ax2.set_title('Temperature Ranges by B-value Combination')
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Plot 3: Mean temperature trends
        if all_stats:
            ax3 = fig.add_subplot(gs[2, 0])
            df_stats = pd.DataFrame(all_stats)
            df_stats['num_b_values'] = df_stats['num_b_values'].astype(int)
            df_sorted = df_stats.sort_values('num_b_values')
            
            ax3.plot(df_sorted['num_b_values'], df_sorted['temp_mean_C'], 'o-', markersize=8)
            ax3.errorbar(df_sorted['num_b_values'], df_sorted['temp_mean_C'], 
                        yerr=df_sorted['temp_std_C'], fmt='none', capsize=5)
            ax3.set_xlabel('Number of B-values')
            ax3.set_ylabel('Mean Temperature (°C)')
            ax3.set_title('Temperature vs Number of B-values')
            ax3.grid(True, alpha=0.3)
            
            # Plot 4: Quality metrics
            ax4 = fig.add_subplot(gs[2, 1])
            ax4.scatter(df_sorted['csf_volume_ml'], df_sorted['temp_physiological_fraction']*100)
            for i, txt in enumerate(df_sorted['analysis']):
                ax4.annotate(txt, (df_sorted['csf_volume_ml'].iloc[i], 
                                  df_sorted['temp_physiological_fraction'].iloc[i]*100),
                           fontsize=8, rotation=45)
            ax4.set_xlabel('CSF Volume (mL)')
            ax4.set_ylabel('Physiological Fraction (%)')
            ax4.set_title('Quality Metrics')
            ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        comparison_path = os.path.join(histogram_dir, 'comparison_all_analyses.png')
        plt.savefig(comparison_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Saved comparison plot to: {comparison_path}")

    print("\n=== All histograms generated successfully! ===")

if __name__ == "__main__":
    main()
EOF
chmod +x 05_create_histograms.py
echo "Generated 05_create_histograms.py"

# --- Script 7: Comprehensive analysis ---
cat << 'EOF' > 06_comprehensive_analysis.py
#!/usr/bin/env python3
import os, sys, argparse, glob, numpy as np, pandas as pd, matplotlib.pyplot as plt
import seaborn as sns, json
from scipy import stats
from matplotlib.gridspec import GridSpec

def main():
    parser = argparse.ArgumentParser(description="Generate comprehensive analysis report.")
    parser.add_argument("subject_id")
    parser.add_argument("output_dir")
    args = parser.parse_args()

    sub_out_dir = os.path.join(args.output_dir, args.subject_id)
    report_dir = os.path.join(sub_out_dir, 'comprehensive_report')
    os.makedirs(report_dir, exist_ok=True)
    
    print(f"=== Generating Comprehensive Analysis for Subject: {args.subject_id} ===")
    
    # Load all statistics
    stats_files = glob.glob(os.path.join(sub_out_dir, 'temperature_stats_*.csv'))
    if not stats_files:
        print("ERROR: No statistics files found!")
        sys.exit(1)
    
    # Combine all statistics
    all_stats = []
    for f in stats_files:
        df = pd.read_csv(f)
        all_stats.append(df)
    
    combined_stats = pd.concat(all_stats, ignore_index=True)
    combined_stats['max_b_value'] = combined_stats['b_values'].apply(
        lambda x: max(map(int, x.split('_')))
    )
    
    # Create comprehensive figure
    fig = plt.figure(figsize=(16, 12))
    gs = GridSpec(4, 3, figure=fig, hspace=0.3, wspace=0.3)
    
    # 1. Temperature vs B-value
    ax1 = fig.add_subplot(gs[0, :2])
    unique_b_max = combined_stats['max_b_value'].unique()
    for b_max in sorted(unique_b_max):
        subset = combined_stats[combined_stats['max_b_value'] == b_max]
        ax1.scatter(subset['num_b_values'], subset['temp_mean_C'], 
                   label=f'Max b={b_max}', s=100, alpha=0.7)
    ax1.set_xlabel('Number of B-values Used')
    ax1.set_ylabel('Mean Temperature (°C)')
    ax1.set_title('Temperature Dependence on B-value Selection')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. ADC statistics
    ax2 = fig.add_subplot(gs[0, 2])
    ax2.scatter(combined_stats['adc_mean']*1000, combined_stats['temp_mean_C'])
    ax2.set_xlabel('Mean ADC (×10⁻³ mm²/s)')
    ax2.set_ylabel('Mean Temperature (°C)')
    ax2.set_title('Temperature vs ADC')
    ax2.grid(True, alpha=0.3)
    
    # 3. Temperature variability
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.bar(range(len(combined_stats)), combined_stats['temp_std_C'])
    ax3.set_xlabel('Analysis Index')
    ax3.set_ylabel('Temperature Std Dev (°C)')
    ax3.set_title('Temperature Variability')
    ax3.set_xticks(range(len(combined_stats)))
    ax3.set_xticklabels(combined_stats['analysis'], rotation=45, ha='right')
    
    # 4. CSF volume consistency
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.plot(combined_stats['csf_volume_ml'], 'o-')
    ax4.set_xlabel('Analysis Index')
    ax4.set_ylabel('CSF Volume (mL)')
    ax4.set_title('CSF Segmentation Consistency')
    ax4.set_xticks(range(len(combined_stats)))
    ax4.set_xticklabels(combined_stats['analysis'], rotation=45, ha='right')
    
    # 5. Quality control metrics
    ax5 = fig.add_subplot(gs[1, 2])
    quality_data = combined_stats[['temp_physiological_fraction', 'analysis']].copy()
    quality_data['physiological_pct'] = quality_data['temp_physiological_fraction'] * 100
    ax5.barh(quality_data['analysis'], quality_data['physiological_pct'])
    ax5.set_xlabel('Physiological Temperature Fraction (%)')
    ax5.set_title('Data Quality by Analysis')
    ax5.axvline(90, color='green', linestyle='--', alpha=0.5, label='90% threshold')
    
    # 6. Temperature distributions comparison
    ax6 = fig.add_subplot(gs[2, :])
    positions = []
    data_to_plot = []
    labels = []
    
    for i, (_, row) in enumerate(combined_stats.iterrows()):
        values_file = os.path.join(sub_out_dir, f'temperature_values_{row["analysis"]}.txt')
        if os.path.exists(values_file):
            temps = np.loadtxt(values_file)
            data_to_plot.append(temps)
            labels.append(row['analysis'])
            positions.append(i)
    
    if data_to_plot:
        parts = ax6.violinplot(data_to_plot, positions=positions, showmeans=True, showmedians=True)
        ax6.set_xticks(positions)
        ax6.set_xticklabels(labels, rotation=45, ha='right')
        ax6.set_ylabel('Temperature (°C)')
        ax6.set_title('Temperature Distributions - Violin Plots')
        ax6.grid(True, axis='y', alpha=0.3)
    
    # 7. ADC outliers analysis
    ax7 = fig.add_subplot(gs[3, 0])
    combined_stats['total_outliers'] = combined_stats['adc_outliers_low'] + combined_stats['adc_outliers_high']
    ax7.bar(range(len(combined_stats)), combined_stats['adc_outliers_low'], label='Low ADC')
    ax7.bar(range(len(combined_stats)), combined_stats['adc_outliers_high'], 
            bottom=combined_stats['adc_outliers_low'], label='High ADC')
    ax7.set_xlabel('Analysis Index')
    ax7.set_ylabel('Number of Outlier Voxels')
    ax7.set_title('ADC Outliers')
    ax7.set_xticks(range(len(combined_stats)))
    ax7.set_xticklabels(combined_stats['analysis'], rotation=45, ha='right')
    ax7.legend()
    
    # 8. Summary statistics table
    ax8 = fig.add_subplot(gs[3, 1:])
    ax8.axis('tight')
    ax8.axis('off')
    
    # Create summary table
    summary_data = combined_stats[['analysis', 'temp_mean_C', 'temp_std_C', 
                                   'csf_volume_ml', 'temp_physiological_fraction']].copy()
    summary_data['temp_mean_C'] = summary_data['temp_mean_C'].round(2)
    summary_data['temp_std_C'] = summary_data['temp_std_C'].round(2)
    summary_data['csf_volume_ml'] = summary_data['csf_volume_ml'].round(1)
    summary_data['temp_physiological_fraction'] = (summary_data['temp_physiological_fraction'] * 100).round(1)
    
    table = ax8.table(cellText=summary_data.values,
                     colLabels=['Analysis', 'Mean T (°C)', 'Std T (°C)', 'CSF Vol (mL)', 'Phys. Frac (%)'],
                     cellLoc='center',
                     loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.2, 1.5)
    ax8.set_title('Summary Statistics', pad=20)
    
    plt.suptitle(f'Comprehensive Temperature Analysis Report - {args.subject_id}', fontsize=16)
    plt.tight_layout()
    
    # Save comprehensive plot
    comprehensive_plot_path = os.path.join(report_dir, 'comprehensive_analysis.png')
    plt.savefig(comprehensive_plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved comprehensive analysis plot to: {comprehensive_plot_path}")
    
    # Save combined statistics
    stats_output_path = os.path.join(report_dir, 'all_statistics_combined.csv')
    combined_stats.to_csv(stats_output_path, index=False)
    print(f"Saved combined statistics to: {stats_output_path}")
    
    # Generate HTML report
    print("Generating HTML report...")
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>CSF Temperature Analysis Report - {args.subject_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .warning {{ color: orange; }}
        .error {{ color: red; }}
        .good {{ color: green; }}
        img {{ max-width: 100%; height: auto; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>CSF Temperature Analysis Report</h1>
    <h2>Subject: {args.subject_id}</h2>
    <h3>Analysis Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</h3>
    
    <h2>Summary</h2>
    <p>Analyzed {len(combined_stats)} different b-value combinations for CSF temperature estimation.</p>
    
    <h2>Key Findings</h2>
    <ul>
        <li>Mean temperature across all analyses: {combined_stats['temp_mean_C'].mean():.2f} ± {combined_stats['temp_mean_C'].std():.2f} °C</li>
        <li>Most consistent result (lowest std): {combined_stats.loc[combined_stats['temp_std_C'].idxmin(), 'analysis']} 
            with std = {combined_stats['temp_std_C'].min():.2f} °C</li>
        <li>Highest physiological fraction: {combined_stats.loc[combined_stats['temp_physiological_fraction'].idxmax(), 'analysis']} 
            with {combined_stats['temp_physiological_fraction'].max()*100:.1f}%</li>
    </ul>
    
    <h2>Comprehensive Analysis</h2>
    <img src="comprehensive_analysis.png" alt="Comprehensive Analysis">
    
    <h2>Quality Control Summary</h2>
    <p>Analyses with potential issues:</p>
    <ul>
"""
    
    # Add warnings for problematic analyses
    for _, row in combined_stats.iterrows():
        warnings = []
        if row['temp_physiological_fraction'] < 0.8:
            warnings.append(f"Low physiological fraction: {row['temp_physiological_fraction']*100:.1f}%")
        if row['total_outliers'] > 100:
            warnings.append(f"High number of ADC outliers: {row['total_outliers']}")
        if row['temp_std_C'] > 5:
            warnings.append(f"High temperature variability: {row['temp_std_C']:.2f} °C")
        
        if warnings:
            html_content += f"        <li><span class='warning'>{row['analysis']}</span>: {'; '.join(warnings)}</li>\n"
    
    html_content += """
    </ul>
    
    <h2>Detailed Statistics</h2>
    <p>See <a href="all_statistics_combined.csv">all_statistics_combined.csv</a> for complete data.</p>
    
    <h2>Individual Histograms</h2>
    <p>Individual temperature distribution plots are available in the histograms directory.</p>
    
</body>
</html>
"""
    
    html_path = os.path.join(report_dir, 'report.html')
    with open(html_path, 'w') as f:
        f.write(html_content)
    print(f"Saved HTML report to: {html_path}")
    
    print("\n=== Comprehensive analysis complete! ===")

if __name__ == "__main__":
    main()
EOF
chmod +x 06_comprehensive_analysis.py
echo "Generated 06_comprehensive_analysis.py"

# --- Generate README ---
cat << 'EOF' > README.md
# CSF Temperature Pipeline - Enhanced Version

## Overview
This pipeline estimates cerebrospinal fluid (CSF) temperature from diffusion-weighted MRI data using the temperature dependence of water diffusivity. The pipeline includes preprocessing, multi-b-value analysis, and comprehensive quality control.

## Pipeline Components

### 1. Configuration File (`pipeline_config.json`)
Central configuration file containing:
- **Paths**: BIDS root, output directory, software locations
- **Processing parameters**: CSF threshold, b-value tolerance, temperature constants
- **Subject list**: Subjects to process
- **B-value combinations**: Different b-value sets for ADC calculation

### 2. Pipeline Manager (`00_pipeline_manager.sh`)
Orchestrates the entire pipeline:
- Submits preprocessing job and waits for completion
- Automatically extracts output directory from logs
- Submits b-value sweep analysis with correct paths
- Generates visualizations and comprehensive report
- **Usage**: `bash 00_pipeline_manager.sh`

### 3. Preprocessing (`01_run_preprocessing.sh` & `02_preprocess_subject.py`)
**Purpose**: Prepare DWI data for temperature calculation
**Inputs**: 
- Raw DWI data (AP and PA phase encoding)
- B-values and b-vectors
**Processing steps**:
1. Denoising and Gibbs ringing removal
2. Distortion correction using reverse phase encoding
3. Bias field correction
4. Brain masking
5. Upsampling to 1.5mm isotropic resolution
6. Multi-tissue constrained spherical deconvolution
7. Intensity normalization
**Outputs**:
- `dwi_preproc_unbiased.mif`: Preprocessed DWI
- `dwi_upsampled.mif`: Upsampled DWI
- `csf_norm.mif`: Normalized CSF tissue map
- `preprocessing_summary.json`: Processing metadata

### 4. Temperature Calculation (`03_run_bvalue_sweep.sh` & `04_calculate_temperature.py`)
**Purpose**: Calculate CSF temperature using different b-value combinations
**Theory**: Temperature calculation based on: