#!/usr/bin/env python3
"""
Clean directional bi-exponential temperature calculation.
No fallbacks - raises errors for proper debugging.
"""

import numpy as np
import nibabel as nib
import os
import sys
import json
import argparse
from datetime import datetime
import logging

def setup_logging(log_file):
    """Setup logging configuration"""
    logger = logging.getLogger('temp_calc_clean')
    logger.setLevel(logging.DEBUG)
    
    # Clear any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
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
    
    result = subprocess.run(command, capture_output=True, text=True)
    
    with open(log_file, 'a') as f:
        f.write(f"\nCommand: {' '.join(command)}\n")
        f.write(f"Output: {result.stdout}\n")
        if result.stderr:
            f.write(f"Stderr: {result.stderr}\n")
    
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}\nError: {result.stderr}")
    
    return result.stdout

def load_gradient_directions(bvec_file, indices):
    """
    Load gradient directions from bvec file.
    
    Args:
        bvec_file: Path to .bvec file
        indices: Indices of volumes to load
    
    Returns:
        gradient_dirs: Array of gradient directions (N, 3)
    
    Raises:
        ValueError: If bvec file format is unexpected
        FileNotFoundError: If bvec file doesn't exist
    """
    if not os.path.exists(bvec_file):
        raise FileNotFoundError(f"B-vector file not found: {bvec_file}")
    
    # Load bvec file
    bvecs = np.loadtxt(bvec_file)
    print(f"DEBUG: bvecs shape: {bvecs.shape}")
    print(f"DEBUG: indices to select: {len(indices)}")
    
    if bvecs.shape[0] == 3:
        # Standard format: 3 rows (x, y, z)
        gradient_dirs = bvecs[:, indices].T
        print(f"DEBUG: Used standard format (3, N) -> selected shape: {gradient_dirs.shape}")
    elif bvecs.shape[1] == 3:
        # Alternative format: N rows x 3 columns
        gradient_dirs = bvecs[indices, :]
        print(f"DEBUG: Used alternative format (N, 3) -> selected shape: {gradient_dirs.shape}")
    else:
        raise ValueError(f"Unexpected bvec format: {bvecs.shape}. Expected (3, N) or (N, 3)")
    
    # Validate output shape
    if gradient_dirs.shape[1] != 3:
        raise ValueError(f"Gradient directions must have 3 components, got: {gradient_dirs.shape}")
    
    return gradient_dirs

def load_dti_metrics(dti_dir, expected_shape):
    """
    Load DTI metrics with explicit error checking.
    
    Args:
        dti_dir: Directory containing DTI outputs
        expected_shape: Expected 3D shape (x, y, z)
    
    Returns:
        dict: DTI metrics with FA, v1, MD
    
    Raises:
        FileNotFoundError: If required files missing
        ValueError: If shapes don't match
    """
    metrics = {}
    
    # Load FA
    fa_file = os.path.join(dti_dir, 'fa.mif')
    if not os.path.exists(fa_file):
        raise FileNotFoundError(f"FA file not found: {fa_file}")
    
    fa_nii = os.path.join(dti_dir, 'fa_temp.nii.gz')
    os.system(f"mrconvert {fa_file} {fa_nii} -force -quiet")
    
    fa_data = nib.load(fa_nii).get_fdata()
    print(f"DEBUG: FA shape: {fa_data.shape}, expected: {expected_shape}")
    
    if fa_data.shape != expected_shape:
        raise ValueError(f"FA shape mismatch: got {fa_data.shape}, expected {expected_shape}")
    
    metrics['FA'] = fa_data
    os.remove(fa_nii)
    
    # Load eigenvectors
    evec_file = os.path.join(dti_dir, 'evec.mif')
    if not os.path.exists(evec_file):
        raise FileNotFoundError(f"Eigenvector file not found: {evec_file}")
    
    evec_nii = os.path.join(dti_dir, 'evec_temp.nii.gz')
    os.system(f"mrconvert {evec_file} {evec_nii} -force -quiet")
    
    evec_data = nib.load(evec_nii).get_fdata()
    print(f"DEBUG: Eigenvector shape: {evec_data.shape}")
    
    expected_evec_shape = expected_shape + (3,)
    if evec_data.shape != expected_evec_shape:
        raise ValueError(f"Eigenvector shape mismatch: got {evec_data.shape}, expected {expected_evec_shape}")
    
    metrics['v1'] = evec_data  # This is the principal eigenvector
    os.remove(evec_nii)
    
    # Load MD
    md_file = os.path.join(dti_dir, 'md.mif')
    if not os.path.exists(md_file):
        raise FileNotFoundError(f"MD file not found: {md_file}")
    
    md_nii = os.path.join(dti_dir, 'md_temp.nii.gz')
    os.system(f"mrconvert {md_file} {md_nii} -force -quiet")
    
    md_data = nib.load(md_nii).get_fdata()
    print(f"DEBUG: MD shape: {md_data.shape}")
    
    if md_data.shape != expected_shape:
        raise ValueError(f"MD shape mismatch: got {md_data.shape}, expected {expected_shape}")
    
    metrics['MD'] = md_data
    os.remove(md_nii)
    
    return metrics

def calculate_tissue_diffusion(gradient_dir, v1, FA, MD):
    """
    Calculate directional tissue diffusion.
    
    Args:
        gradient_dir: Gradient direction vector (3,)
        v1: Principal eigenvector (3,)
        FA: Fractional anisotropy (scalar)
        MD: Mean diffusivity (scalar)
    
    Returns:
        D_tissue: Tissue diffusion in this direction
    
    Raises:
        ValueError: If input shapes are wrong
    """
    # Validate inputs
    gradient_dir = np.asarray(gradient_dir)
    v1 = np.asarray(v1)
    
    if gradient_dir.shape != (3,):
        raise ValueError(f"Gradient direction must be (3,), got {gradient_dir.shape}")
    if v1.shape != (3,):
        raise ValueError(f"Eigenvector must be (3,), got {v1.shape}")
    
    # Normalize vectors
    grad_norm = np.linalg.norm(gradient_dir)
    v1_norm = np.linalg.norm(v1)
    
    if grad_norm == 0:
        print(f"DEBUG: Zero gradient direction: {gradient_dir}")
        return MD  # For b=0, return isotropic diffusion
    
    if v1_norm == 0:
        print(f"DEBUG: Zero eigenvector, using isotropic diffusion")
        return MD
    
    gradient_dir = gradient_dir / grad_norm
    v1 = v1 / v1_norm
    
    # Calculate directional dependence
    if FA < 0.05:  # Nearly isotropic
        return MD
    
    # Calculate parallel and perpendicular diffusivities
    D_parallel = MD * (1 + 2 * FA / np.sqrt(3))
    D_perpendicular = MD * (1 - FA / np.sqrt(3))
    
    # Ensure physical bounds
    D_parallel = np.clip(D_parallel, 0.1e-3, 2.0e-3)
    D_perpendicular = np.clip(D_perpendicular, 0.1e-3, 1.5e-3)
    
    # Calculate angle between gradient and fiber
    cos_theta = np.abs(np.dot(gradient_dir, v1))
    
    # Directional diffusion
    D_tissue = D_parallel * cos_theta**2 + D_perpendicular * (1 - cos_theta**2)
    
    return D_tissue

def fit_directional_biexponential(signal, b_values, gradient_dirs, FA, v1, MD):
    """
    Fit directional bi-exponential model.
    
    Args:
        signal: DWI signal (N,)
        b_values: b-values (N,)
        gradient_dirs: Gradient directions (N, 3)
        FA: FA value (scalar)
        v1: Principal eigenvector (3,)
        MD: Mean diffusivity (scalar)
    
    Returns:
        dict: Fitting results
    
    Raises:
        ValueError: If inputs have wrong shapes
        RuntimeError: If optimization fails
    """
    from scipy.optimize import minimize
    
    # Validate inputs
    signal = np.asarray(signal)
    b_values = np.asarray(b_values)
    gradient_dirs = np.asarray(gradient_dirs)
    
    if signal.shape != b_values.shape:
        raise ValueError(f"Signal and b-values must have same length: {signal.shape} vs {b_values.shape}")
    
    if gradient_dirs.shape != (len(b_values), 3):
        raise ValueError(f"Gradient directions shape mismatch: got {gradient_dirs.shape}, expected ({len(b_values)}, 3)")
    
    if len(signal) < 4:
        raise ValueError(f"Need at least 4 measurements for 4-parameter fit, got {len(signal)}")
    
    # Check for invalid data
    if np.any(signal <= 0):
        raise ValueError("Signal contains non-positive values")
    
    if np.any(np.isnan(signal)) or np.any(np.isinf(signal)):
        raise ValueError("Signal contains NaN or infinite values")
    
    print(f"DEBUG: Fitting voxel with FA={FA:.3f}, MD={MD*1e3:.3f}e-3")
    print(f"DEBUG: Signal range: [{np.min(signal):.1f}, {np.max(signal):.1f}]")
    print(f"DEBUG: B-values: {b_values}")
    
    def objective(params):
        S0, f_free, D_free, tissue_scale = params
        
        predicted = np.zeros_like(signal)
        
        for i in range(len(b_values)):
            b = b_values[i]
            g = gradient_dirs[i]
            
            # Free water component (isotropic)
            free_component = f_free * np.exp(-b * D_free)
            
            # Tissue component (anisotropic)
            D_tissue_i = tissue_scale * calculate_tissue_diffusion(g, v1, FA, MD)
            tissue_component = (1 - f_free) * np.exp(-b * D_tissue_i)
            
            predicted[i] = S0 * (free_component + tissue_component)
        
        # Calculate residual
        residual = np.sum((signal - predicted) ** 2)
        
        print(f"DEBUG: S0={S0:.1f}, f_free={f_free:.3f}, D_free={D_free*1e3:.3f}e-3, scale={tissue_scale:.3f}, residual={residual:.2e}")
        
        return residual
    
    # Initial guess
    S0_init = signal[b_values == 0].mean() if np.any(b_values == 0) else signal[0]
    f_free_init = max(0.1, 1.0 - 2.0 * FA)  # High FA -> more tissue -> low f_free
    
    x0 = [S0_init, f_free_init, 3.0e-3, 1.0]
    
    # Bounds
    bounds = [
        (0.1 * S0_init, 3.0 * S0_init),  # S0
        (0.0, 1.0),                        # f_free
        (2.5e-3, 3.5e-3),                 # D_free (constrained)
        (0.3, 2.0)                         # tissue_scale
    ]
    
    print(f"DEBUG: Initial guess: {x0}")
    print(f"DEBUG: Bounds: {bounds}")
    
    # Optimize
    result = minimize(objective, x0, bounds=bounds, method='L-BFGS-B')
    
    if not result.success:
        raise RuntimeError(f"Optimization failed: {result.message}")
    
    S0_fit, f_free_fit, D_free_fit, tissue_scale_fit = result.x
    
    # Calculate R-squared
    predicted_final = np.zeros_like(signal)
    for i in range(len(b_values)):
        b = b_values[i]
        g = gradient_dirs[i]
        free_comp = f_free_fit * np.exp(-b * D_free_fit)
        D_tissue_i = tissue_scale_fit * calculate_tissue_diffusion(g, v1, FA, MD)
        tissue_comp = (1 - f_free_fit) * np.exp(-b * D_tissue_i)
        predicted_final[i] = S0_fit * (free_comp + tissue_comp)
    
    ss_res = np.sum((signal - predicted_final) ** 2)
    ss_tot = np.sum((signal - np.mean(signal)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    
    # Calculate effective tissue diffusion
    tissue_diffusions = []
    for i in range(len(b_values)):
        if b_values[i] > 0:  # Skip b=0
            D_tissue_i = tissue_scale_fit * calculate_tissue_diffusion(gradient_dirs[i], v1, FA, MD)
            tissue_diffusions.append(D_tissue_i)
    
    D_tissue_mean = np.mean(tissue_diffusions) if tissue_diffusions else 0.7e-3
    
    print(f"DEBUG: Final fit - D_free={D_free_fit*1e3:.3f}e-3, f_free={f_free_fit:.3f}, R²={r_squared:.3f}")
    
    return {
        'S0': S0_fit,
        'f_free': f_free_fit,
        'D_free': D_free_fit,
        'D_tissue': D_tissue_mean,
        'tissue_scale': tissue_scale_fit,
        'r_squared': r_squared,
        'fitting_success': True
    }

def main():
    parser = argparse.ArgumentParser(description="Clean directional bi-exponential fitting")
    parser.add_argument("subject_id")
    parser.add_argument("output_dir")
    parser.add_argument("bids_root")
    parser.add_argument("--bvals_for_adc", type=int, nargs='+', default=[0, 1200])
    parser.add_argument("--output_suffix", type=str, default="clean")
    parser.add_argument("--config_file", type=str, required=True)
    parser.add_argument("--test_voxel", type=int, nargs=3, help="Test single voxel [x y z]")
    args = parser.parse_args()
    
    # Setup directories and logging
    sub_out_dir = os.path.join(args.output_dir, args.subject_id)
    tmp_dir = os.path.join(sub_out_dir, f'tmp_{args.output_suffix}')
    os.makedirs(tmp_dir, exist_ok=True)
    
    log_file = os.path.join(sub_out_dir, f'log_calc_{args.output_suffix}.txt')
    logger = setup_logging(log_file)
    
    logger.info(f"=== Clean Directional Bi-exponential Fitting ===")
    logger.info(f"Subject: {args.subject_id}")
    
    # Load configuration
    with open(args.config_file, 'r') as f:
        config = json.load(f)
    
    # File paths
    dwi_upsampled = os.path.join(sub_out_dir, 'dwi_upsampled.mif')
    csf_mask_cleaned = os.path.join(sub_out_dir, f'csf_mask_cleaned_b0_1200.mif')
    dti_dir = os.path.join(sub_out_dir, 'dti')
    
    # Check all required files exist
    required_files = [dwi_upsampled, csf_mask_cleaned]
    for f in required_files:
        if not os.path.exists(f):
            raise FileNotFoundError(f"Required file not found: {f}")
    
    if not os.path.exists(dti_dir):
        raise FileNotFoundError(f"DTI directory not found: {dti_dir}")
    
    # Load b-values and select indices
    bval_file = os.path.join(args.bids_root, args.subject_id, 'ses-02', 'dwi',
                            f'{args.subject_id}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.bval')
    bvec_file = os.path.join(args.bids_root, args.subject_id, 'ses-02', 'dwi',
                            f'{args.subject_id}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.bvec')
    
    bvals = np.loadtxt(bval_file)
    bvalue_tolerance = config['processing']['bvalue_tolerance']
    
    indices_to_keep = [i for i, b in enumerate(bvals) 
                      if any(np.isclose(b, target_b, atol=bvalue_tolerance) 
                            for target_b in args.bvals_for_adc)]
    
    logger.info(f"Selected {len(indices_to_keep)} volumes from {len(bvals)} total")
    selected_bvals = bvals[indices_to_keep]
    
    logger.info(f"B-values: {np.unique(selected_bvals)}")
    
    # Load gradient directions
    gradient_dirs = load_gradient_directions(bvec_file, indices_to_keep)
    logger.info(f"Gradient directions loaded: {gradient_dirs.shape}")
    
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
    
    # Handle mask dimensions - squeeze extra dimensions
    mask_data = np.squeeze(mask_data)
    
    logger.info(f"DWI data shape: {dwi_data.shape}")
    logger.info(f"Mask shape: {mask_data.shape}")
    logger.info(f"Mask contains {np.sum(mask_data > 0)} voxels")
    
    # Get 3D shape for DTI loading
    spatial_shape = mask_data.shape[:3]  # (147, 147, 88)
    
    # Load DTI metrics
    logger.info("Loading DTI metrics...")
    dti_metrics = load_dti_metrics(dti_dir, spatial_shape)
    logger.info("DTI metrics loaded successfully")
    
    # Test on single voxel if specified
    if args.test_voxel:
        x, y, z = args.test_voxel
        logger.info(f"Testing single voxel at ({x}, {y}, {z})")
        
        if mask_data[x, y, z] == 0:
            raise ValueError(f"Test voxel ({x}, {y}, {z}) is not in the mask")
        
        # Extract data for this voxel
        signal = dwi_data[x, y, z, :]
        fa = dti_metrics['FA'][x, y, z]
        v1 = dti_metrics['v1'][x, y, z, :]
        md = dti_metrics['MD'][x, y, z]
        
        logger.info(f"Voxel data - FA: {fa:.3f}, MD: {md*1e3:.3f}e-3 mm²/s")
        logger.info(f"Signal: {signal}")
        logger.info(f"Eigenvector: {v1}")
        
        # Fit the model
        try:
            result = fit_directional_biexponential(signal, selected_bvals, gradient_dirs, fa, v1, md)
            logger.info(f"Fitting successful!")
            logger.info(f"Results: {result}")
        except Exception as e:
            logger.error(f"Fitting failed: {e}")
            raise
    
    else:
        # Process all voxels (not implemented yet - focus on single voxel testing first)
        logger.info("Full processing not implemented - use --test_voxel for debugging")
    
    logger.info("Processing complete!")

if __name__ == "__main__":
    main()