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
    logger.info(f"RUNNING: {cmd_str}")
    
    with open(log_file, 'a') as f:
        f.write(f"\n--- RUNNING: {cmd_str}\n")
        # If cmd is a list, pass it directly to subprocess.run
        # If cmd is a string, pass the string with shell=True
        if isinstance(cmd, list):
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, 
                                   text=True, check=False)
        else:
            result = subprocess.run(cmd_str, stdout=f, stderr=subprocess.STDOUT, 
                                   text=True, check=False, shell=True)
    
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

def try_mrtrix3tissue_command(cmd, log_file, logger, fallback_cmd=None):
    """Try to run a MRtrix3Tissue command with fallback to standard MRtrix3"""
    cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
    logger.info(f"Attempting MRtrix3Tissue command: {cmd_str}")
    
    try:
        with open(log_file, 'a') as f:
            f.write(f"\n--- RUNNING: {cmd_str}\n")
            if isinstance(cmd, list):
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, 
                                       text=True, check=True)
            else:
                result = subprocess.run(cmd_str, stdout=f, stderr=subprocess.STDOUT, 
                                       text=True, check=True, shell=True)
        logger.info("SUCCESS with MRtrix3Tissue")
        return True
    except subprocess.CalledProcessError as e:
        logger.warning(f"MRtrix3Tissue command failed with error: {e}")
        if fallback_cmd:
            logger.info(f"Attempting fallback to standard MRtrix3: {' '.join(fallback_cmd)}")
            run_command(fallback_cmd, log_file, logger)
            return False
        else:
            logger.error("No fallback available, exiting")
            sys.exit(1)

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
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Python executable: {sys.executable}")
    
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
                 '-scratch', args.jobfs_path, '-force'], log_file, logger)
    
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
    
    # Define response function files
    resp_wm = os.path.join(sub_out_dir, 'response_wm.txt')
    resp_gm = os.path.join(sub_out_dir, 'response_gm.txt')
    resp_csf = os.path.join(sub_out_dir, 'response_csf.txt')
    wmfod = os.path.join(sub_out_dir, 'wmfod.mif')
    gm = os.path.join(sub_out_dir, 'gm.mif')
    csf = os.path.join(sub_out_dir, 'csf.mif')
    wmfod_norm = os.path.join(sub_out_dir, 'wmfod_norm.mif')
    gm_norm = os.path.join(sub_out_dir, 'gm_norm.mif')
    csf_norm = os.path.join(sub_out_dir, 'csf_norm.mif')
    
    # Try MRtrix3Tissue dwi2response first, fallback to standard MRtrix3
    if args.mrtrix3tissue_bin:
        dwi2response_cmd = os.path.join(args.mrtrix3tissue_bin, 'dwi2response')
        used_mrtrix3tissue = try_mrtrix3tissue_command(
            [dwi2response_cmd, 'dhollander', preproc_dwi_unbiased, resp_wm, resp_gm, resp_csf, '-force'],
            log_file, logger,
            fallback_cmd=['dwi2response', 'dhollander', preproc_dwi_unbiased, resp_wm, resp_gm, resp_csf, '-force']
        )
    else:
        logger.info("No MRtrix3Tissue path provided, using standard MRtrix3")
        run_command(['dwi2response', 'dhollander', preproc_dwi_unbiased, resp_wm, resp_gm, resp_csf, '-force'], 
                    log_file, logger)
        used_mrtrix3tissue = False
    
    logger.info("Step 9: Multi-shell multi-tissue CSD")
    run_command(['dwi2fod', 'msmt_csd', dwi_upsampled, resp_wm, wmfod, resp_gm, gm, resp_csf, csf, 
                 '-mask', mask_upsampled, '-force'], log_file, logger)
    
    logger.info("Step 10: Multi-tissue normalization")
    # Try MRtrix3Tissue mtnormalise if available, otherwise use standard
    if args.mrtrix3tissue_bin and used_mrtrix3tissue:
        mtnormalise_cmd = os.path.join(args.mrtrix3tissue_bin, 'mtnormalise')
        try_mrtrix3tissue_command(
            [mtnormalise_cmd, wmfod, wmfod_norm, gm, gm_norm, csf, csf_norm, '-mask', mask_upsampled, '-force'],
            log_file, logger,
            fallback_cmd=['mtnormalise', wmfod, wmfod_norm, gm, gm_norm, csf, csf_norm, 
                         '-mask', mask_upsampled, '-force']
        )
    else:
        logger.info("Using standard MRtrix3 mtnormalise")
        run_command(['mtnormalise', wmfod, wmfod_norm, gm, gm_norm, csf, csf_norm, 
                    '-mask', mask_upsampled, '-force'], log_file, logger)
    
    # Save preprocessing summary
    summary = {
        'subject_id': args.subject_id,
        'preprocessing_date': datetime.now().isoformat(),
        'output_directory': sub_out_dir,
        'python_version': sys.version,
        'python_executable': sys.executable,
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