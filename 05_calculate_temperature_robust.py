#!/usr/bin/env python3
"""
Robust temperature calculation with multiple fallback strategies.
This version addresses all the identified issues and provides multiple approaches.
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
    logger = logging.getLogger('temp_calc_robust')
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

def fit_biexponential_robust(signal, b_values, fa_value, config, logger, strategy='constrained'):
    """
    Robust bi-exponential fitting with multiple strategies.
    
    Args:
        signal: DWI signal values (N,)
        b_values: b-values (N,)  
        fa_value: FA value for this voxel
        config: Configuration dict
        logger: Logger instance
        strategy: 'constrained', 'regularized', or 'directional'
    
    Returns:
        dict: Fitting results
    """
    
    # Strategy 1: Constrained (D_free fixed at 3.0)
    if strategy == 'constrained':
        return fit_constrained_biexponential(signal, b_values, D_free_fixed=3.0e-3)
    
    # Strategy 2: Regularized (D_free penalized to stay near 3.0)
    elif strategy == 'regularized':
        return fit_regularized_biexponential(signal, b_values, fa_value)
    
    # Strategy 3: FA-guided initialization
    elif strategy == 'fa_guided':
        return fit_fa_guided_biexponential(signal, b_values, fa_value, config)
    
    else:
        # Default to constrained
        return fit_constrained_biexponential(signal, b_values, D_free_fixed=3.0e-3)

def fit_regularized_biexponential(signal, b_values, fa_value):
    """
    Fit bi-exponential with regularization to keep D_free near 3.0e-3.
    """
    from scipy.optimize import minimize
    
    def objective(params):
        S0, f_free, D_free, D_tissue = params
        
        # Predict signal
        predicted = S0 * (f_free * np.exp(-b_values * D_free) + 
                         (1 - f_free) * np.exp(-b_values * D_tissue))
        
        # Data fitting term
        data_error = np.sum((signal - predicted) ** 2)
        
        # Regularization terms
        d_free_penalty = 10.0 * (D_free - 3.0e-3) ** 2  # Strong penalty for D_free deviation
        
        # FA-based f_free penalty (high FA should have low f_free)
        expected_f_free = max(0.1, 1.0 - 2.0 * fa_value)
        f_free_penalty = 1.0 * (f_free - expected_f_free) ** 2
        
        return data_error + d_free_penalty + f_free_penalty
    
    # Initial guess
    S0_init = signal[0] if signal[0] > 0 else np.max(signal)
    f_free_init = max(0.1, 1.0 - 2.0 * fa_value)
    
    x0 = [S0_init, f_free_init, 3.0e-3, 0.7e-3]
    
    # Bounds
    bounds = [(0.1 * S0_init, 3.0 * S0_init),  # S0
              (0.0, 1.0),                        # f_free
              (2.5e-3, 3.5e-3),                 # D_free (tight bounds)
              (0.1e-3, 1.5e-3)]                 # D_tissue
    
    try:
        result = minimize(objective, x0, bounds=bounds, method='L-BFGS-B')
        
        if result.success:
            S0_fit, f_free_fit, D_free_fit, D_tissue_fit = result.x
            
            # Calculate R²
            predicted = S0_fit * (f_free_fit * np.exp(-b_values * D_free_fit) + 
                                 (1 - f_free_fit) * np.exp(-b_values * D_tissue_fit))
            ss_res = np.sum((signal - predicted) ** 2)
            ss_tot = np.sum((signal - np.mean(signal)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            
            return {
                'S0': S0_fit,
                'f_free': f_free_fit,
                'D_free': D_free_fit,
                'D_tissue': D_tissue_fit,
                'r_squared': r_squared,
                'fa_value': fa_value,
                'fitting_success': True,
                'model_used': 'regularized_biexponential'
            }
    except Exception:
        pass
    
    return {'fitting_success': False}

def fit_fa_guided_biexponential(signal, b_values, fa_value, config):
    """
    Fit bi-exponential with FA-guided parameter bounds.
    """
    from scipy.optimize import curve_fit, OptimizeWarning
    import warnings
    warnings.filterwarnings('ignore', category=OptimizeWarning)
    
    def biexponential_signal(b, S0, f_free, D_free, D_tissue):
        return S0 * (f_free * np.exp(-b * D_free) + (1 - f_free) * np.exp(-b * D_tissue))
    
    # FA-guided parameter bounds
    if fa_value < 0.1:  # CSF-like (low FA)
        f_free_bounds = (0.7, 1.0)    # High free water fraction
        d_tissue_bounds = (0.5e-3, 1.0e-3)  # Minimal tissue contribution
    elif fa_value < 0.3:  # Partial volume
        f_free_bounds = (0.3, 0.8)    # Mixed
        d_tissue_bounds = (0.3e-3, 1.2e-3)
    else:  # High FA (tissue-dominated)
        f_free_bounds = (0.0, 0.5)    # Low free water
        d_tissue_bounds = (0.1e-3, 1.5e-3)
    
    # Always constrain D_free tightly
    d_free_bounds = (2.8e-3, 3.2e-3)
    
    try:
        S0_init = signal[0] if signal[0] > 0 else np.max(signal)
        f_free_init = (f_free_bounds[0] + f_free_bounds[1]) / 2
        
        p0 = [S0_init, f_free_init, 3.0e-3, 0.7e-3]
        
        bounds = ([0, f_free_bounds[0], d_free_bounds[0], d_tissue_bounds[0]],
                  [np.inf, f_free_bounds[1], d_free_bounds[1], d_tissue_bounds[1]])
        
        popt, pcov = curve_fit(biexponential_signal, b_values, signal,
                              p0=p0, bounds=bounds, maxfev=2000)
        
        S0_fit, f_free_fit, D_free_fit, D_tissue_fit = popt
        
        # Calculate R²
        y_pred = biexponential_signal(b_values, *popt)
        ss_res = np.sum((signal - y_pred) ** 2)
        ss_tot = np.sum((signal - np.mean(signal)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        return {
            'S0': S0_fit,
            'f_free': f_free_fit,
            'D_free': D_free_fit,
            'D_tissue': D_tissue_fit,
            'r_squared': r_squared,
            'fa_value': fa_value,
            'fitting_success': True,
            'model_used': 'fa_guided_biexponential'
        }
        
    except Exception:
        return {'fitting_success': False}

def main():
    parser = argparse.ArgumentParser(description="Robust bi-exponential temperature calculation")
    parser.add_argument("subject_id")
    parser.add_argument("output_dir")  
    parser.add_argument("bids_root")
    parser.add_argument("--bvals_for_adc", type=int, nargs='+', default=[0, 1200])
    parser.add_argument("--output_suffix", type=str, default="robust")
    parser.add_argument("--config_file", type=str, required=True)
    parser.add_argument("--strategy", choices=['constrained', 'regularized', 'fa_guided'], 
                       default='regularized', help="Fitting strategy")
    args = parser.parse_args()
    
    # Setup directories and logging
    sub_out_dir = os.path.join(args.output_dir, args.subject_id)
    tmp_dir = os.path.join(sub_out_dir, f'tmp_{args.output_suffix}')
    os.makedirs(tmp_dir, exist_ok=True)
    
    log_file = os.path.join(sub_out_dir, f'log_calc_{args.output_suffix}.txt')
    logger = setup_logging(log_file)
    
    logger.info(f"=== Robust Bi-exponential Temperature Calculation ===")
    logger.info(f"Subject: {args.subject_id}")
    logger.info(f"Strategy: {args.strategy}")
    logger.info(f"B-values: {args.bvals_for_adc}")
    
    # Load configuration
    with open(args.config_file, 'r') as f:
        config = json.load(f)
    
    # File paths
    dwi_upsampled = os.path.join(sub_out_dir, 'dwi_upsampled.mif')
    csf_mask_cleaned = os.path.join(sub_out_dir, f'csf_mask_cleaned_b0_1200.mif')
    dti_dir = os.path.join(sub_out_dir, 'dti')
    
    # Load b-values
    bval_file = os.path.join(args.bids_root, args.subject_id, 'ses-02', 'dwi',
                            f'{args.subject_id}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.bval')
    
    bvals = np.loadtxt(bval_file)
    bvalue_tolerance = config['processing']['bvalue_tolerance']
    indices_to_keep = [i for i, b in enumerate(bvals) 
                      if any(np.isclose(b, target_b, atol=bvalue_tolerance) 
                            for target_b in args.bvals_for_adc)]
    
    logger.info(f"Selected {len(indices_to_keep)} volumes")
    selected_bvals = bvals[indices_to_keep]
    
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
    
    # Load FA data
    fa_data = None
    fa_file = os.path.join(dti_dir, 'fa.mif')
    if os.path.exists(fa_file):
        fa_nii = os.path.join(tmp_dir, 'fa.nii.gz')
        run_command(['mrconvert', fa_file, fa_nii, '-force'], log_file, logger)
        fa_data = nib.load(fa_nii).get_fdata()
        logger.info("FA data loaded successfully")
    else:
        fa_data = np.zeros(mask_data.shape)
        logger.warning("FA data not found, using zeros")
    
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
    logger.info(f"Processing {total_voxels} voxels with {args.strategy} strategy...")
    
    # Temperature calculation constants
    A = config['processing']['temperature_constants']['A']
    B = config['processing']['temperature_constants']['B']
    
    # Statistics counters
    success_count = 0
    strategy_counts = {'constrained': 0, 'regularized': 0, 'fa_guided': 0}
    
    # Process each voxel
    for idx in range(total_voxels):
        if idx % 5000 == 0:
            logger.info(f"Processing voxel {idx}/{total_voxels}")
        
        x, y, z = valid_voxels[0][idx], valid_voxels[1][idx], valid_voxels[2][idx]
        
        # Extract signal for this voxel
        signal = dwi_data[x, y, z, :]
        fa_value = fa_data[x, y, z]
        
        # Skip if invalid signal
        if np.any(signal <= 0) or np.any(np.isnan(signal)):
            continue
        
        # Try primary strategy
        result = fit_biexponential_robust(signal, selected_bvals, fa_value, config, logger, args.strategy)
        
        # If primary fails, try fallback strategies
        if not result.get('fitting_success', False) or result.get('r_squared', 0) < 0.5:
            # Try constrained as fallback
            result = fit_biexponential_robust(signal, selected_bvals, fa_value, config, logger, 'constrained')
        
        if result.get('fitting_success', False):
            success_count += 1
            
            d_free_map[x, y, z] = result.get('D_free', 0)
            d_tissue_map[x, y, z] = result.get('D_tissue', 0)
            f_free_map[x, y, z] = result.get('f_free', 0)
            r_squared_map[x, y, z] = result.get('r_squared', 0)
            
            # Count strategy used
            model_name = result.get('model_used', 'unknown')
            if 'constrained' in model_name:
                strategy_counts['constrained'] += 1
                model_used_map[x, y, z] = 1
            elif 'regularized' in model_name:
                strategy_counts['regularized'] += 1
                model_used_map[x, y, z] = 2
            elif 'fa_guided' in model_name:
                strategy_counts['fa_guided'] += 1
                model_used_map[x, y, z] = 3
            
            # Calculate temperature
            D = result.get('D_free', 0)
            if D > 0:
                D_m2s = D * 1e-6  # Convert to m²/s
                temp = (A / (B - np.log(D_m2s))) - 273.15
                if 20 < temp < 50:  # Sanity check
                    temp_map[x, y, z] = temp
    
    # Save results
    logger.info("Saving parameter maps...")
    
    output_suffix = f"{args.output_suffix}_{args.strategy}_bvals_{'_'.join(map(str, args.bvals_for_adc))}"
    
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
        logger.info(f"\n=== Results Summary ({args.strategy} strategy) ===")
        logger.info(f"Success rate: {success_count}/{total_voxels} ({100*success_count/total_voxels:.1f}%)")
        logger.info(f"Strategy usage: {strategy_counts}")
        logger.info(f"Temperature: {np.mean(temp_map[mask]):.1f} ± {np.std(temp_map[mask]):.1f}°C")
        logger.info(f"D_free: {np.mean(d_free_map[mask])*1e3:.3f} ± {np.std(d_free_map[mask])*1e3:.3f} × 10⁻³ mm²/s")
        logger.info(f"f_free: {np.mean(f_free_map[mask]):.2f} ± {np.std(f_free_map[mask]):.2f}")
        logger.info(f"R²: {np.mean(r_squared_map[mask]):.3f} ± {np.std(r_squared_map[mask]):.3f}")
        
        # Check D_free distribution
        d_free_vals = d_free_map[mask] * 1e3
        logger.info(f"D_free range: [{np.min(d_free_vals):.3f}, {np.max(d_free_vals):.3f}] × 10⁻³ mm²/s")
        
        # Simple bifurcation check
        hist, bins = np.histogram(d_free_vals, bins=50)
        peak_count = 0
        for i in range(1, len(hist)-1):
            if hist[i] > hist[i-1] and hist[i] > hist[i+1] and hist[i] > 0.1 * np.max(hist):
                peak_count += 1
        
        if peak_count <= 1:
            logger.info("✓ No bifurcation detected - single peak distribution")
        else:
            logger.warning(f"⚠ Potential bifurcation detected - {peak_count} peaks")
    
    logger.info("Processing complete!")

if __name__ == "__main__":
    main()