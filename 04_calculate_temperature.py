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
    logger.info(f"RUNNING: {cmd_str}")
    
    with open(log_file, 'a') as f:
        f.write(f"\n--- RUNNING: {cmd_str}\n")
        # FIXED: Properly handle list vs string commands
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

def create_csf_mask_3tissue(csf_norm_map, threshold, csf_mask_raw, csf_mask_cleaned, log_file, logger):
    """Create CSF mask using 3-tissue decomposition approach"""
    logger.info("Creating CSF mask using 3-tissue decomposition method")
    logger.info(f"Using CSF threshold: {threshold}")
    
    # Threshold the normalized CSF map
    run_command(['mrthreshold', csf_norm_map, '-abs', str(threshold), csf_mask_raw, '-force'], 
                log_file, logger)
    
    # Clean up the mask with morphological operations
    run_command(f"maskfilter {csf_mask_raw} erode - | maskfilter - dilate {csf_mask_cleaned} -force", 
                log_file, logger)

def create_csf_mask_adc(adc_map, adc_min, adc_max, csf_mask_cleaned, log_file, logger):
    """Create CSF mask using ADC thresholding approach"""
    logger.info("Creating CSF mask using ADC threshold method")
    logger.info(f"ADC range for CSF: {adc_min} - {adc_max} mm²/s")
    
    # Create mask based on ADC values
    # ADC values in CSF are typically between 0.0025 and 0.004 mm²/s
    mask_cmd = (f"mrcalc {adc_map} {adc_min} -gt {adc_map} {adc_max} -lt -mult "
                f"{csf_mask_cleaned} -force")
    run_command(mask_cmd, log_file, logger)
    
    # Optional: clean up isolated voxels
    run_command(f"maskfilter {csf_mask_cleaned} median {csf_mask_cleaned} -force", 
                log_file, logger)

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
        'temp_physiological_fraction': np.sum((temp_values > 30) & (temp_values < 42)) / len(temp_values) if len(temp_values) > 0 else 0,
        'temp_below_35': np.sum(temp_values < 30) if len(temp_values) > 0 else 0,
        'temp_above_39': np.sum(temp_values > 42) if len(temp_values) > 0 else 0,
        'csf_volume_ml': np.sum(csf_mask > 0) * 1.5**3 / 1000  # assuming 1.5mm isotropic
    }
    
    logger.info(f"Quality metrics calculated: {len(temp_values)} valid voxels")
    return metrics

def fit_biexponential_model(signal, b_values, fa_value, config, logger):
    """
    Fit bi-exponential diffusion model with physical constraints
    
    Model: S(b) = S0 * (f_free * exp(-b * D_free) + (1 - f_free) * exp(-b * D_tissue))
    
    Args:
        signal: DWI signal values
        b_values: b-values corresponding to signal
        fa_value: FA value for this voxel (used for validation)
        config: configuration dictionary
        logger: logger instance
    
    Returns:
        dict: Fitted parameters or None if fitting failed
    """
    from scipy.optimize import curve_fit, OptimizeWarning
    import warnings
    
    # Suppress optimization warnings for cleaner logs
    warnings.filterwarnings('ignore', category=OptimizeWarning)
    
    # Get configuration parameters
    biexp_config = config['processing']['biexponential_model']
    d_free_bounds = biexp_config['d_free_bounds']
    d_tissue_bounds = biexp_config['d_tissue_bounds']
    initial_guess = biexp_config['initial_guess']
    
    def biexponential_signal(b, S0, f_free, D_free, D_tissue):
        """Bi-exponential signal model"""
        return S0 * (f_free * np.exp(-b * D_free) + (1 - f_free) * np.exp(-b * D_tissue))
    
    try:
        # Initial parameter guess
        S0_init = signal[0] if signal[0] > 0 else np.max(signal)
        p0 = [S0_init, initial_guess['f_free'], initial_guess['d_free'], initial_guess['d_tissue']]
        
        # Parameter bounds: [S0, f_free, D_free, D_tissue]
        lower_bounds = [0, 0, d_free_bounds[0], d_tissue_bounds[0]]
        upper_bounds = [np.inf, 1, d_free_bounds[1], d_tissue_bounds[1]]
        bounds = (lower_bounds, upper_bounds)
        
        # Perform fitting
        popt, pcov = curve_fit(biexponential_signal, b_values, signal, 
                              p0=p0, bounds=bounds, maxfev=1000)
        
        S0_fit, f_free_fit, D_free_fit, D_tissue_fit = popt
        
        # Calculate R-squared for goodness of fit
        y_pred = biexponential_signal(b_values, *popt)
        ss_res = np.sum((signal - y_pred) ** 2)
        ss_tot = np.sum((signal - np.mean(signal)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        # Calculate parameter uncertainties
        param_errors = np.sqrt(np.diag(pcov)) if pcov is not None else [0, 0, 0, 0]
        
        return {
            'S0': S0_fit,
            'f_free': f_free_fit,
            'D_free': D_free_fit,
            'D_tissue': D_tissue_fit,
            'r_squared': r_squared,
            'param_errors': param_errors,
            'fa_value': fa_value,
            'fitting_success': True
        }
        
    except Exception as e:
        logger.debug(f"Bi-exponential fitting failed: {str(e)}")
        return {
            'S0': 0,
            'f_free': 0,
            'D_free': 0,
            'D_tissue': 0,
            'r_squared': 0,
            'param_errors': [0, 0, 0, 0],
            'fa_value': fa_value,
            'fitting_success': False
        }

def fit_monoexponential_model(signal, b_values):
    """
    Fit mono-exponential diffusion model (standard ADC)
    
    Model: S(b) = S0 * exp(-b * ADC)
    """
    from scipy.optimize import curve_fit
    
    def monoexponential_signal(b, S0, ADC):
        """Mono-exponential signal model"""
        return S0 * np.exp(-b * ADC)
    
    try:
        # Initial parameter guess
        S0_init = signal[0] if signal[0] > 0 else np.max(signal)
        p0 = [S0_init, 2.5e-3]  # Initial ADC guess
        
        # Parameter bounds: [S0, ADC]
        bounds = ([0, 0.5e-3], [np.inf, 5e-3])
        
        # Perform fitting
        popt, pcov = curve_fit(monoexponential_signal, b_values, signal, 
                              p0=p0, bounds=bounds, maxfev=1000)
        
        S0_fit, ADC_fit = popt
        
        # Calculate R-squared
        y_pred = monoexponential_signal(b_values, *popt)
        ss_res = np.sum((signal - y_pred) ** 2)
        ss_tot = np.sum((signal - np.mean(signal)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        return {
            'S0': S0_fit,
            'ADC': ADC_fit,
            'r_squared': r_squared,
            'fitting_success': True
        }
        
    except Exception as e:
        return {
            'S0': 0,
            'ADC': 0,
            'r_squared': 0,
            'fitting_success': False
        }

def process_voxel_with_model_selection(signal, b_values, fa_value, config, logger):
    """
    Process a single voxel with model selection between mono- and bi-exponential
    
    Returns:
        dict: Results from the selected model
    """
    temperature_model = config['processing']['temperature_model']
    
    if temperature_model == 'biexponential':
        # Try bi-exponential first
        biexp_result = fit_biexponential_model(signal, b_values, fa_value, config, logger)
        
        if biexp_result['fitting_success'] and biexp_result['r_squared'] > 0.7:
            # Use D_free for temperature calculation
            biexp_result['model_used'] = 'biexponential'
            biexp_result['D_for_temperature'] = biexp_result['D_free']
            return biexp_result
        else:
            # Fall back to mono-exponential
            logger.debug("Bi-exponential fitting failed, falling back to mono-exponential")
            mono_result = fit_monoexponential_model(signal, b_values)
            mono_result['model_used'] = 'monoexponential_fallback'
            mono_result['D_for_temperature'] = mono_result.get('ADC', 0)
            mono_result['fa_value'] = fa_value
            return mono_result
    
    else:  # temperature_model == 'monoexponential'
        mono_result = fit_monoexponential_model(signal, b_values)
        mono_result['model_used'] = 'monoexponential'
        mono_result['D_for_temperature'] = mono_result.get('ADC', 0)
        mono_result['fa_value'] = fa_value
        return mono_result

def main():
    parser = argparse.ArgumentParser(description="Enhanced temperature calculation with flexible CSF masking.")
    parser.add_argument("subject_id")
    parser.add_argument("output_dir")
    parser.add_argument("bids_root")
    parser.add_argument("--bvals_for_adc", type=int, nargs='+')
    parser.add_argument("--output_suffix", type=str, required=True)
    parser.add_argument("--config_file", type=str, required=True)
    parser.add_argument("--mask_method", type=str, choices=['3tissue', 'adc_threshold'], 
                       help="Override CSF mask method from config")
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
    
    # Determine mask method
    mask_method = args.mask_method if args.mask_method else config['processing'].get('csf_mask_method', '3tissue')
    logger.info(f"Using CSF mask method: {mask_method}")
    
    # Define file paths
    dwi_upsampled = os.path.join(sub_out_dir, 'dwi_upsampled.mif')
    csf_norm_map = os.path.join(sub_out_dir, 'csf_norm.mif')
    dwi_ap_bval = os.path.join(args.bids_root, args.subject_id, 'ses-02', 'dwi', 
                               f'{args.subject_id}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.bval')
    
    # Check if required files exist
    required_files = [dwi_upsampled, dwi_ap_bval]
    if mask_method == '3tissue':
        required_files.append(csf_norm_map)
    
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
    
    # Create mask based on selected method
    if mask_method == '3tissue':
        csf_threshold = config['processing']['csf_threshold']
        create_csf_mask_3tissue(csf_norm_map, csf_threshold, csf_mask_raw, 
                               csf_mask_cleaned, log_file, logger)
    else:  # adc_threshold
        adc_min = config['processing'].get('adc_threshold_min', 0.0025)
        adc_max = config['processing'].get('adc_threshold_max', 0.004)
        create_csf_mask_adc(adc_map_full, adc_min, adc_max, 
                           csf_mask_cleaned, log_file, logger)

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
            'mask_method': mask_method,
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
            'mask_method': mask_method,
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
    ax.set_title(f'Temperature Map - {args.output_suffix} ({mask_method})', color='white', fontsize=12)
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

CSF Mask Method: {mask_method}
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