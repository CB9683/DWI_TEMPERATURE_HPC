#!/usr/bin/env python3
"""
Enhanced temperature calculation with directional bi-exponential model.

This version uses gradient directions and DTI metrics to properly model
tissue anisotropy in partial volume voxels.
"""

import numpy as np
import nibabel as nib
import os
import sys
import json
import argparse
from datetime import datetime
import logging

# Add utils to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.directional_fitting import (
    fit_directional_biexponential, 
    fit_constrained_biexponential,
    select_optimal_directions
)

def setup_logging(log_file):
    """Setup logging configuration"""
    logger = logging.getLogger('temp_calc_directional')
    logger.setLevel(logging.DEBUG)
    
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger

def run_command(command, log_file, logger):
    """Run shell command and log output"""
    import subprocess
    logger.info(f"Running: {' '.join(command)}")
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        with open(log_file, 'a') as f:
            f.write(f"\nCommand: {' '.join(command)}\n")
            f.write(f"Output: {result.stdout}\n")
            if result.stderr:
                f.write(f"Stderr: {result.stderr}\n")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        logger.error(f"Stderr: {e.stderr}")
        raise

def load_gradient_directions(bvec_file, indices):
    """
    Load gradient directions from bvec file for specified indices.
    
    Args:
        bvec_file: Path to .bvec file
        indices: Indices of volumes to load
    
    Returns:
        gradient_dirs: Array of gradient directions (N, 3)
    """
    # Load bvec file (3 x N format)
    bvecs = np.loadtxt(bvec_file)
    
    if bvecs.shape[0] == 3:
        # Standard format: 3 rows (x, y, z)
        gradient_dirs = bvecs[:, indices].T
    else:
        # Alternative format: N rows x 3 columns
        gradient_dirs = bvecs[indices, :]
    
    return gradient_dirs

def load_dti_metrics(dti_dir, shape):
    """
    Load DTI metrics (FA, eigenvectors, eigenvalues).
    
    Args:
        dti_dir: Directory containing DTI outputs
        shape: Expected 3D shape of the data
    
    Returns:
        dict: DTI metrics including FA, v1, MD
    """
    metrics = {}
    
    # Load FA
    fa_file = os.path.join(dti_dir, 'fa.mif')
    if os.path.exists(fa_file):
        # Convert to nifti for easier loading
        fa_nii = fa_file.replace('.mif', '_temp.nii.gz')
        os.system(f"mrconvert {fa_file} {fa_nii} -force -quiet")
        metrics['FA'] = nib.load(fa_nii).get_fdata()
        os.remove(fa_nii)
    else:
        # If FA not available, create zeros
        metrics['FA'] = np.zeros(shape)
    
    # Load eigenvectors - MRtrix stores principal eigenvector in evec.mif
    evec_file = os.path.join(dti_dir, 'evec.mif')
    if os.path.exists(evec_file):
        evec_nii = evec_file.replace('.mif', '_temp.nii.gz')
        os.system(f"mrconvert {evec_file} {evec_nii} -force -quiet")
        evec_data = nib.load(evec_nii).get_fdata()
        
        print(f"Eigenvector data shape: {evec_data.shape}")
        
        # evec.mif from dwi2tensor typically contains the principal eigenvector only
        if evec_data.ndim == 4 and evec_data.shape[3] == 3:
            # Shape is (x, y, z, 3) - this IS the principal eigenvector
            metrics['v1'] = evec_data
        else:
            print(f"Warning: Unexpected eigenvector shape: {evec_data.shape}")
            # Default to z-direction
            metrics['v1'] = np.zeros(shape + (3,))
            metrics['v1'][..., 2] = 1.0
        
        os.remove(evec_nii)
    else:
        # Default to z-direction if not available
        metrics['v1'] = np.zeros(shape + (3,))
        metrics['v1'][..., 2] = 1.0
    
    # Load mean diffusivity
    md_file = os.path.join(dti_dir, 'md.mif')
    if os.path.exists(md_file):
        md_nii = md_file.replace('.mif', '_temp.nii.gz')
        os.system(f"mrconvert {md_file} {md_nii} -force -quiet")
        metrics['MD'] = nib.load(md_nii).get_fdata()
        os.remove(md_nii)
    else:
        # Default MD value
        metrics['MD'] = np.ones(shape) * 0.7e-3
    
    return metrics

def process_voxel_directional(signal, b_values, gradient_dirs, fa, v1, md, config, logger):
    """
    Process a single voxel with directional bi-exponential model.
    
    Args:
        signal: DWI signal for this voxel (N,)
        b_values: b-values (N,)
        gradient_dirs: Gradient directions (N, 3)
        fa: FA value for this voxel
        v1: Principal eigenvector (3,)
        md: Mean diffusivity
        config: Configuration dictionary
        logger: Logger instance
    
    Returns:
        dict: Fitting results
    """
    
    # Check signal validity
    if np.any(signal <= 0) or np.any(np.isnan(signal)):
        return {'fitting_success': False}
    
    # Try directional bi-exponential fitting
    result = fit_directional_biexponential(
        signal, b_values, gradient_dirs, fa, v1, md, config, logger
    )
    
    # If directional fitting fails, try constrained fitting
    if not result.get('fitting_success', False) or result.get('r_squared', 0) < 0.7:
        logger.debug("Directional fitting failed, trying constrained model")
        result = fit_constrained_biexponential(signal, b_values)
    
    # Set D_for_temperature
    if result.get('fitting_success', False):
        result['D_for_temperature'] = result.get('D_free', 0)
    
    return result

def main():
    parser = argparse.ArgumentParser(description="Directional bi-exponential temperature calculation")
    parser.add_argument("subject_id")
    parser.add_argument("output_dir")
    parser.add_argument("bids_root")
    parser.add_argument("--bvals_for_adc", type=int, nargs='+', default=[0, 1200])
    parser.add_argument("--output_suffix", type=str, default="directional")
    parser.add_argument("--config_file", type=str, required=True)
    parser.add_argument("--use_subset", action="store_true", 
                       help="Use subset of optimally distributed directions")
    parser.add_argument("--n_directions", type=int, default=12,
                       help="Number of directions to use if --use_subset")
    args = parser.parse_args()
    
    # Setup directories and logging
    sub_out_dir = os.path.join(args.output_dir, args.subject_id)
    tmp_dir = os.path.join(sub_out_dir, f'tmp_{args.output_suffix}')
    os.makedirs(tmp_dir, exist_ok=True)
    
    log_file = os.path.join(sub_out_dir, f'log_calc_{args.output_suffix}.txt')
    logger = setup_logging(log_file)
    
    logger.info(f"=== Directional Bi-exponential Temperature Calculation ===")
    logger.info(f"Subject: {args.subject_id}")
    logger.info(f"B-values: {args.bvals_for_adc}")
    
    # Load configuration
    with open(args.config_file, 'r') as f:
        config = json.load(f)
    
    # File paths
    dwi_upsampled = os.path.join(sub_out_dir, 'dwi_upsampled.mif')
    csf_mask_cleaned = os.path.join(sub_out_dir, f'csf_mask_cleaned_b0_1200.mif')
    dti_dir = os.path.join(sub_out_dir, 'dti')
    
    # Load b-values and b-vectors
    bval_file = os.path.join(args.bids_root, args.subject_id, 'ses-02', 'dwi',
                            f'{args.subject_id}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.bval')
    bvec_file = os.path.join(args.bids_root, args.subject_id, 'ses-02', 'dwi',
                            f'{args.subject_id}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.bvec')
    
    # Load b-values and select indices
    bvals = np.loadtxt(bval_file)
    bvalue_tolerance = config['processing']['bvalue_tolerance']
    indices_to_keep = [i for i, b in enumerate(bvals) 
                      if any(np.isclose(b, target_b, atol=bvalue_tolerance) 
                            for target_b in args.bvals_for_adc)]
    
    logger.info(f"Selected {len(indices_to_keep)} volumes")
    selected_bvals = bvals[indices_to_keep]
    
    # Load gradient directions
    gradient_dirs = load_gradient_directions(bvec_file, indices_to_keep)
    logger.info(f"Loaded gradient directions: {gradient_dirs.shape}")
    
    # Optionally select subset of directions
    if args.use_subset:
        direction_indices = select_optimal_directions(gradient_dirs, args.n_directions)
        gradient_dirs = gradient_dirs[direction_indices]
        selected_bvals = selected_bvals[direction_indices]
        indices_to_keep = [indices_to_keep[i] for i in direction_indices]
        logger.info(f"Using {len(direction_indices)} optimally distributed directions")
    
    # Extract DWI volumes
    dwi_reduced = os.path.join(tmp_dir, 'dwi_reduced.mif')
    indices_str = ",".join(map(str, indices_to_keep))
    run_command(['mrconvert', dwi_upsampled, dwi_reduced, '-coord', '3', indices_str, '-force'], 
               log_file, logger)
    
    # Convert to NIfTI
    dwi_nii = os.path.join(tmp_dir, 'dwi_reduced.nii.gz')
    mask_nii = os.path.join(tmp_dir, 'csf_mask.nii.gz')
    run_command(['mrconvert', dwi_reduced, dwi_nii, '-force'], log_file, logger)
    run_command(['mrconvert', csf_mask_cleaned, mask_nii, '-force'], log_file, logger)
    
    # Load data
    dwi_data = nib.load(dwi_nii).get_fdata()
    mask_data = nib.load(mask_nii).get_fdata()
    affine = nib.load(dwi_nii).affine
    
    logger.info(f"DWI data shape: {dwi_data.shape}")
    logger.info(f"Mask contains {np.sum(mask_data > 0)} voxels")
    
    # Load DTI metrics
    logger.info("Loading DTI metrics...")
    dti_metrics = load_dti_metrics(dti_dir, mask_data.shape)
    
    # Initialize output arrays
    shape_3d = mask_data.shape
    d_free_map = np.zeros(shape_3d)
    d_tissue_map = np.zeros(shape_3d)
    f_free_map = np.zeros(shape_3d)
    r_squared_map = np.zeros(shape_3d)
    temp_map = np.zeros(shape_3d)
    model_used_map = np.zeros(shape_3d)
    
    # Process voxels
    valid_voxels = np.where(mask_data > 0)
    total_voxels = len(valid_voxels[0])
    logger.info(f"Processing {total_voxels} voxels with directional model...")
    
    # Temperature calculation constants
    A = config['processing']['temperature_constants']['A']
    B = config['processing']['temperature_constants']['B']
    
    # Process each voxel
    for idx in range(total_voxels):
        if idx % 1000 == 0:
            logger.info(f"Processing voxel {idx}/{total_voxels}")
        
        x, y, z = valid_voxels[0][idx], valid_voxels[1][idx], valid_voxels[2][idx]
        
        # Extract signal for this voxel
        signal = dwi_data[x, y, z, :]
        
        # Get DTI metrics for this voxel
        fa = dti_metrics['FA'][x, y, z]
        v1 = dti_metrics['v1'][x, y, z, :]
        md = dti_metrics['MD'][x, y, z]
        
        # Fit model
        result = process_voxel_directional(
            signal, selected_bvals, gradient_dirs, fa, v1, md, config, logger
        )
        
        if result.get('fitting_success', False):
            d_free_map[x, y, z] = result.get('D_free', 0)
            d_tissue_map[x, y, z] = result.get('D_tissue', 0)
            f_free_map[x, y, z] = result.get('f_free', 0)
            r_squared_map[x, y, z] = result.get('r_squared', 0)
            
            # Calculate temperature
            D = result.get('D_for_temperature', 0)
            if D > 0:
                D_m2s = D * 1e-6  # Convert to m²/s
                temp = (A / (B - np.log(D_m2s))) - 273.15
                if 20 < temp < 50:  # Sanity check
                    temp_map[x, y, z] = temp
            
            # Mark model used (1=constrained, 2=directional)
            if result.get('model_used') == 'directional_biexponential':
                model_used_map[x, y, z] = 2
            else:
                model_used_map[x, y, z] = 1
    
    # Save results
    logger.info("Saving parameter maps...")
    
    output_suffix = f"{args.output_suffix}_bvals_{'_'.join(map(str, args.bvals_for_adc))}"
    
    # Save parameter maps
    nib.save(nib.Nifti1Image(d_free_map, affine), 
             os.path.join(sub_out_dir, f'd_free_map_{output_suffix}.nii.gz'))
    nib.save(nib.Nifti1Image(d_tissue_map, affine), 
             os.path.join(sub_out_dir, f'd_tissue_map_{output_suffix}.nii.gz'))
    nib.save(nib.Nifti1Image(f_free_map, affine), 
             os.path.join(sub_out_dir, f'f_free_map_{output_suffix}.nii.gz'))
    nib.save(nib.Nifti1Image(r_squared_map, affine), 
             os.path.join(sub_out_dir, f'r_squared_map_{output_suffix}.nii.gz'))
    nib.save(nib.Nifti1Image(temp_map, affine), 
             os.path.join(sub_out_dir, f'temperature_map_{output_suffix}.nii.gz'))
    nib.save(nib.Nifti1Image(model_used_map, affine), 
             os.path.join(sub_out_dir, f'model_used_map_{output_suffix}.nii.gz'))
    
    # Print summary statistics
    mask = temp_map > 0
    if np.any(mask):
        logger.info(f"\n=== Results Summary ===")
        logger.info(f"Temperature: {np.mean(temp_map[mask]):.1f} ± {np.std(temp_map[mask]):.1f}°C")
        logger.info(f"D_free: {np.mean(d_free_map[mask])*1e3:.3f} ± {np.std(d_free_map[mask])*1e3:.3f} × 10⁻³ mm²/s")
        logger.info(f"f_free: {np.mean(f_free_map[mask]):.2f} ± {np.std(f_free_map[mask]):.2f}")
        logger.info(f"R²: {np.mean(r_squared_map[mask]):.3f} ± {np.std(r_squared_map[mask]):.3f}")
        
        # Check for bifurcation
        d_free_values = d_free_map[mask]
        hist, bins = np.histogram(d_free_values * 1e3, bins=50)
        
        # Simple bifurcation detection: look for bimodal distribution
        if len(hist) > 10:
            peaks = []
            for i in range(1, len(hist)-1):
                if hist[i] > hist[i-1] and hist[i] > hist[i+1]:
                    peaks.append(bins[i])
            
            if len(peaks) > 1:
                logger.warning(f"Potential bifurcation detected! Peaks at: {peaks}")
            else:
                logger.info("No bifurcation detected - single peak distribution")
    
    logger.info("Processing complete!")

if __name__ == "__main__":
    main()