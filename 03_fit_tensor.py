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

def calculate_tensor_metrics(dt_file, output_dir, logger):
    """Calculate DTI metrics from diffusion tensor"""
    logger.info("Calculating DTI metrics...")
    
    # Define output files
    fa_file = os.path.join(output_dir, 'fa.mif')
    md_file = os.path.join(output_dir, 'md.mif')
    ad_file = os.path.join(output_dir, 'ad.mif')
    rd_file = os.path.join(output_dir, 'rd.mif')
    eval_file = os.path.join(output_dir, 'eval.mif')
    evec_file = os.path.join(output_dir, 'evec.mif')
    
    # Calculate DTI metrics with correct MRtrix3 syntax
    metrics = {
        'fa': fa_file,
        'adc': md_file,  # MRtrix3 uses 'adc' instead of 'md' for mean diffusivity
        'ad': ad_file,
        'rd': rd_file,
        'value': eval_file,  # MRtrix3 uses 'value' instead of 'eval' for eigenvalues
        'vector': evec_file  # MRtrix3 uses 'vector' instead of 'evec' for eigenvectors
    }
    
    # Generate all metrics at once
    cmd = ['tensor2metric', dt_file]
    for metric, filename in metrics.items():
        cmd.extend([f'-{metric}', filename])
    cmd.append('-force')
    
    return cmd, metrics

def create_fa_visualization(fa_nii, output_file, slice_idx=None, logger=None):
    """Create FA visualization"""
    if logger:
        logger.info("Creating FA visualization...")
    
    fa_data = nib.load(fa_nii).get_fdata()
    
    if slice_idx is None:
        slice_idx = fa_data.shape[2] // 2
    
    # Create figure
    fig, axes = plt.subplots(2, 2, figsize=(12, 10), facecolor='black')
    
    # Axial slice
    ax = axes[0, 0]
    im = ax.imshow(np.rot90(fa_data[:, :, slice_idx]), cmap='hot', vmin=0, vmax=0.8)
    ax.set_title('FA - Axial', color='white', fontsize=12)
    ax.axis('off')
    
    # Coronal slice
    ax = axes[0, 1]
    coronal_idx = fa_data.shape[1] // 2
    im = ax.imshow(np.rot90(fa_data[:, coronal_idx, :]), cmap='hot', vmin=0, vmax=0.8)
    ax.set_title('FA - Coronal', color='white', fontsize=12)
    ax.axis('off')
    
    # Sagittal slice
    ax = axes[1, 0]
    sagittal_idx = fa_data.shape[0] // 2
    im = ax.imshow(np.rot90(fa_data[sagittal_idx, :, :]), cmap='hot', vmin=0, vmax=0.8)
    ax.set_title('FA - Sagittal', color='white', fontsize=12)
    ax.axis('off')
    
    # FA histogram
    ax = axes[1, 1]
    fa_values = fa_data[fa_data > 0]  # Exclude background
    ax.hist(fa_values, bins=50, color='orange', alpha=0.7, edgecolor='white')
    ax.axvline(np.mean(fa_values), color='red', linestyle='--', 
              label=f'Mean: {np.mean(fa_values):.3f}')
    ax.axvline(np.median(fa_values), color='blue', linestyle='--', 
              label=f'Median: {np.median(fa_values):.3f}')
    ax.set_xlabel('Fractional Anisotropy', color='white')
    ax.set_ylabel('Frequency', color='white')
    ax.set_title('FA Distribution', color='white')
    ax.legend()
    ax.tick_params(colors='white')
    ax.spines['bottom'].set_color('white')
    ax.spines['left'].set_color('white')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    # Add colorbar
    cbar = fig.colorbar(im, ax=axes[0, :], fraction=0.046, pad=0.04)
    cbar.set_label('FA', color='white')
    cbar.ax.tick_params(colors='white')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight', facecolor='black')
    plt.close()
    
    if logger:
        logger.info(f"FA visualization saved to: {output_file}")

def calculate_quality_metrics(fa_data, md_data, mask_data, logger):
    """Calculate quality control metrics for tensor fitting"""
    logger.info("Calculating tensor quality metrics...")
    
    # Get valid voxels
    valid_mask = (mask_data > 0) & np.isfinite(fa_data) & np.isfinite(md_data) & (fa_data > 0)
    fa_values = fa_data[valid_mask]
    md_values = md_data[valid_mask]
    
    metrics = {
        'fa_mean': float(np.mean(fa_values)) if len(fa_values) > 0 else 0,
        'fa_median': float(np.median(fa_values)) if len(fa_values) > 0 else 0,
        'fa_std': float(np.std(fa_values)) if len(fa_values) > 0 else 0,
        'fa_min': float(np.min(fa_values)) if len(fa_values) > 0 else 0,
        'fa_max': float(np.max(fa_values)) if len(fa_values) > 0 else 0,
        'md_mean': float(np.mean(md_values)) if len(md_values) > 0 else 0,
        'md_median': float(np.median(md_values)) if len(md_values) > 0 else 0,
        'md_std': float(np.std(md_values)) if len(md_values) > 0 else 0,
        'low_fa_fraction': float(np.sum(fa_values < 0.2) / len(fa_values)) if len(fa_values) > 0 else 0,
        'high_fa_fraction': float(np.sum(fa_values > 0.7) / len(fa_values)) if len(fa_values) > 0 else 0,
        'csf_like_voxels': int(np.sum((fa_values < 0.15) & (md_values > 2.5e-3))) if len(fa_values) > 0 else 0
    }
    
    logger.info(f"Tensor quality metrics calculated: {len(fa_values)} valid voxels")
    return metrics

def main():
    parser = argparse.ArgumentParser(description="Fit diffusion tensor and calculate DTI metrics.")
    parser.add_argument("subject_id")
    parser.add_argument("output_dir")
    parser.add_argument("--config_file", type=str, required=True)
    args = parser.parse_args()

    # Setup directories and logging
    sub_out_dir = os.path.join(args.output_dir, args.subject_id)
    dti_dir = os.path.join(sub_out_dir, 'dti')
    os.makedirs(dti_dir, exist_ok=True)
    
    log_file = os.path.join(sub_out_dir, 'log_05_tensor_fitting.txt')
    logger = setup_logging(log_file)
    
    logger.info(f"=== Starting DTI Analysis ===")
    logger.info(f"Subject: {args.subject_id}")
    logger.info(f"Start time: {datetime.now()}")
    
    # Load configuration
    with open(args.config_file, 'r') as f:
        config = json.load(f)
    
    # Check if DTI fitting is enabled
    if not config['processing']['biexponential_model'].get('fit_dti', False):
        logger.info("DTI fitting disabled in configuration. Skipping tensor analysis.")
        return
    
    # Define file paths
    dwi_upsampled = os.path.join(sub_out_dir, 'dwi_upsampled.mif')
    dwi_mask = os.path.join(sub_out_dir, 'dwi_mask_upsampled.mif')
    
    # Check if required files exist
    required_files = [dwi_upsampled, dwi_mask]
    for f in required_files:
        if not os.path.exists(f):
            logger.error(f"Required file not found: {f}")
            sys.exit(1)
    
    # Output files
    dt_file = os.path.join(dti_dir, 'dt.mif')
    
    logger.info("Step 1: Fitting diffusion tensor")
    run_command(['dwi2tensor', dwi_upsampled, dt_file, '-mask', dwi_mask, '-force'], 
                log_file, logger)

    logger.info("Step 2: Calculating DTI metrics")
    metrics_cmd, metric_files = calculate_tensor_metrics(dt_file, dti_dir, logger)
    run_command(metrics_cmd, log_file, logger)

    logger.info("Step 3: Converting key metrics to NIfTI for analysis")
    fa_nii = os.path.join(dti_dir, 'fa.nii.gz')
    md_nii = os.path.join(dti_dir, 'md.nii.gz')
    mask_nii = os.path.join(dti_dir, 'mask.nii.gz')
    
    run_command(['mrconvert', metric_files['fa'], fa_nii, '-force', '-quiet'], 
                log_file, logger)
    run_command(['mrconvert', metric_files['adc'], md_nii, '-force', '-quiet'], 
                log_file, logger)
    run_command(['mrconvert', dwi_mask, mask_nii, '-force', '-quiet'], 
                log_file, logger)
    
    logger.info("Step 4: Generating quality control metrics")
    
    # Load data for analysis
    fa_data = nib.load(fa_nii).get_fdata()
    md_data = nib.load(md_nii).get_fdata()
    mask_data = nib.load(mask_nii).get_fdata()
    
    # Calculate quality metrics
    qc_metrics = calculate_quality_metrics(fa_data, md_data, mask_data, logger)
    
    # Create summary statistics
    stats = {
        'subject_id': args.subject_id,
        'analysis_date': datetime.now().isoformat(),
        'tensor_fitting': 'completed'
    }
    stats.update(qc_metrics)
    
    # Save statistics
    stats_csv = os.path.join(dti_dir, 'dti_stats.csv')
    pd.DataFrame([stats]).to_csv(stats_csv, index=False)
    logger.info(f"DTI statistics saved to: {stats_csv}")

    logger.info("Step 5: Creating visualization")
    vis_png = os.path.join(dti_dir, 'fa_visualization.png')
    create_fa_visualization(fa_nii, vis_png, logger=logger)
    
    # Create summary
    summary = {
        'subject_id': args.subject_id,
        'dti_analysis_date': datetime.now().isoformat(),
        'output_directory': dti_dir,
        'files_generated': {
            'diffusion_tensor': 'dt.mif',
            'fractional_anisotropy': 'fa.mif',
            'mean_diffusivity': 'md.mif',
            'axial_diffusivity': 'ad.mif',
            'radial_diffusivity': 'rd.mif',
            'eigenvalues': 'eval.mif',
            'eigenvectors': 'evec.mif'
        },
        'quality_metrics': qc_metrics
    }
    
    with open(os.path.join(dti_dir, 'dti_summary.json'), 'w') as f:
        json.dump(summary, f, indent=4)
    
    logger.info(f"=== DTI analysis complete ===")
    logger.info(f"End time: {datetime.now()}")

if __name__ == "__main__":
    main()