#!/usr/bin/env python3
"""
Resume preprocessing from existing dwi_preproc.mif
This script skips the already completed preprocessing steps and continues from bias correction
"""
import os, sys, subprocess, argparse, json, glob, logging
from datetime import datetime

def setup_logging(log_file):
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='a'),  # Append mode
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
    parser = argparse.ArgumentParser(description="Resume preprocessing from existing dwi_preproc.mif")
    parser.add_argument("subject_id")
    parser.add_argument("bids_root")
    parser.add_argument("output_dir")
    parser.add_argument("--mrtrix3tissue_bin")
    parser.add_argument("--jobfs_path", default="/tmp")
    parser.add_argument("--config_file")
    args = parser.parse_args()

    # Setup output directories and logging
    sub_out_dir = os.path.join(args.output_dir, args.subject_id)
    os.makedirs(sub_out_dir, exist_ok=True)
    log_file = os.path.join(sub_out_dir, 'log_02_preprocessing_resume.txt')
    
    logger = setup_logging(log_file)
    logger.info(f"=== RESUMING Preprocessing for: {args.subject_id} ===")
    logger.info(f"Resume time: {datetime.now()}")
    
    # Load configuration
    with open(args.config_file, 'r') as f:
        config = json.load(f)
    logger.info(f"Loaded configuration from: {args.config_file}")
    
    # Define file paths
    preproc_dwi = os.path.join(sub_out_dir, 'dwi_preproc.mif')
    preproc_dwi_unbiased = os.path.join(sub_out_dir, 'dwi_preproc_unbiased.mif')
    dwi_mask = os.path.join(sub_out_dir, 'dwi_mask.mif')
    dwi_upsampled = os.path.join(sub_out_dir, 'dwi_upsampled.mif')
    mask_upsampled = os.path.join(sub_out_dir, 'dwi_mask_upsampled.mif')
    
    # Check if dwi_preproc.mif exists
    if not os.path.exists(preproc_dwi):
        logger.error(f"ERROR: dwi_preproc.mif not found at {preproc_dwi}")
        logger.error("Cannot resume preprocessing without this file!")
        sys.exit(1)
    else:
        logger.info(f"Found existing dwi_preproc.mif at {preproc_dwi}")
    
    # Resume from Step 5: Bias field correction
    if not os.path.exists(preproc_dwi_unbiased):
        logger.info("Step 5: Bias field correction")
        run_command(['dwibiascorrect', 'ants', preproc_dwi, preproc_dwi_unbiased, '-force'], log_file, logger)
    else:
        logger.info(f"Step 5: Bias field correction - SKIPPED (already exists: {preproc_dwi_unbiased})")
    
    # Step 6: Creating brain mask
    if not os.path.exists(dwi_mask):
        logger.info("Step 6: Creating brain mask")
        run_command(['dwi2mask', preproc_dwi_unbiased, dwi_mask, '-force'], log_file, logger)
    else:
        logger.info(f"Step 6: Brain mask - SKIPPED (already exists: {dwi_mask})")
    
    # Step 7: Upsampling to 1.5mm isotropic
    if not os.path.exists(dwi_upsampled):
        logger.info("Step 7: Upsampling to 1.5mm isotropic")
        run_command(['mrgrid', preproc_dwi_unbiased, 'regrid', dwi_upsampled, '-voxel', '1.5', '-force'], log_file, logger)
    else:
        logger.info(f"Step 7: Upsampling - SKIPPED (already exists: {dwi_upsampled})")
    
    if not os.path.exists(mask_upsampled):
        logger.info("Step 7b: Upsampling mask")
        run_command(f"mrgrid {dwi_mask} regrid - -template {dwi_upsampled} -interp linear -datatype bit -force | "
                   f"maskfilter - median {mask_upsampled} -force", log_file, logger)
    else:
        logger.info(f"Step 7b: Mask upsampling - SKIPPED (already exists: {mask_upsampled})")

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
    
    # Check if response functions already exist
    if not all([os.path.exists(f) for f in [resp_wm, resp_gm, resp_csf]]):
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
    else:
        logger.info("Step 8: Response functions - SKIPPED (already exist)")
        used_mrtrix3tissue = False  # We don't know, but not critical
    
    # Step 9: Multi-shell multi-tissue CSD
    if not all([os.path.exists(f) for f in [wmfod, gm, csf]]):
        logger.info("Step 9: Multi-shell multi-tissue CSD")
        run_command(['dwi2fod', 'msmt_csd', dwi_upsampled, resp_wm, wmfod, resp_gm, gm, resp_csf, csf, 
                     '-mask', mask_upsampled, '-force'], log_file, logger)
    else:
        logger.info("Step 9: MSMT-CSD - SKIPPED (FODs already exist)")
    
    # Step 10: Multi-tissue normalization
    if not all([os.path.exists(f) for f in [wmfod_norm, gm_norm, csf_norm]]):
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
    else:
        logger.info("Step 10: Normalization - SKIPPED (normalized files already exist)")
    
    # Save preprocessing summary
    summary = {
        'subject_id': args.subject_id,
        'preprocessing_resumed': datetime.now().isoformat(),
        'output_directory': sub_out_dir,
        'processing_steps_resumed': [
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
    
    with open(os.path.join(sub_out_dir, 'preprocessing_resume_summary.json'), 'w') as f:
        json.dump(summary, f, indent=4)
    
    logger.info(f"=== Preprocessing RESUMED and COMPLETED for: {args.subject_id} ===")
    logger.info(f"End time: {datetime.now()}")

if __name__ == "__main__":
    main()