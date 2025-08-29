#!/usr/bin/env python3
"""
Test script to compare standard and directional bi-exponential models.
"""

import numpy as np
import nibabel as nib
import matplotlib.pyplot as plt
import os
import sys
import subprocess

def run_directional_model():
    """Run the directional bi-exponential model"""
    
    subject = "sub-01945"
    output_dir = "/g/data/hl36/cb4095/WAND/derivatives/temp_pipeline_2025-08-27_11-27-08"
    bids_root = "/g/data/hl36/cb4095/WAND/WAND"
    config_file = "/g/data/vp06/Christian/dwi-temperature_updated/pipeline_config.json"
    
    # Activate conda environment and run
    cmd = [
        "python", 
        "05_calculate_temperature_directional.py",
        subject,
        output_dir,
        bids_root,
        "--bvals_for_adc", "0", "1200",
        "--output_suffix", "directional_test",
        "--config_file", config_file
    ]
    
    print(f"Running: {' '.join(cmd)}")
    
    # Set up environment
    env = os.environ.copy()
    env['PATH'] = f"/g/data/vp06/Christian/software/Envs/miniconda3/envs/dwi_temperature/bin:{env['PATH']}"
    
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    
    print(result.stdout)
    return True

def compare_results():
    """Compare results between standard and directional models"""
    
    output_dir = "/g/data/hl36/cb4095/WAND/derivatives/temp_pipeline_2025-08-27_11-27-08/sub-01945"
    
    # Load standard model results
    standard_d_free = os.path.join(output_dir, "d_free_map_b0_1200.nii.gz")
    standard_f_free = os.path.join(output_dir, "f_free_map_b0_1200.nii.gz")
    
    # Load directional model results
    directional_d_free = os.path.join(output_dir, "d_free_map_directional_test_bvals_0_1200.nii.gz")
    directional_f_free = os.path.join(output_dir, "f_free_map_directional_test_bvals_0_1200.nii.gz")
    
    if not os.path.exists(directional_d_free):
        print("Directional results not found. Run the model first.")
        return
    
    # Load data
    std_d = nib.load(standard_d_free).get_fdata()
    std_f = nib.load(standard_f_free).get_fdata()
    dir_d = nib.load(directional_d_free).get_fdata()
    dir_f = nib.load(directional_f_free).get_fdata()
    
    # Create mask for valid voxels
    mask_std = (std_d > 0) & (std_f > 0)
    mask_dir = (dir_d > 0) & (dir_f > 0)
    
    # Extract values
    std_d_vals = std_d[mask_std] * 1e3  # Convert to 10^-3 mm^2/s
    std_f_vals = std_f[mask_std]
    dir_d_vals = dir_d[mask_dir] * 1e3
    dir_f_vals = dir_f[mask_dir]
    
    # Create comparison plots
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # Plot 1: Standard model D_free vs f_free
    ax = axes[0, 0]
    scatter = ax.scatter(std_f_vals, std_d_vals, c=std_d_vals, 
                        cmap='viridis', alpha=0.5, s=1)
    ax.set_xlabel('f_free')
    ax.set_ylabel('D_free (×10⁻³ mm²/s)')
    ax.set_title('Standard Bi-exponential Model')
    ax.set_xlim([0, 1])
    ax.set_ylim([2.0, 4.0])
    plt.colorbar(scatter, ax=ax, label='D_free')
    
    # Plot 2: Directional model D_free vs f_free
    ax = axes[0, 1]
    scatter = ax.scatter(dir_f_vals, dir_d_vals, c=dir_d_vals, 
                        cmap='viridis', alpha=0.5, s=1)
    ax.set_xlabel('f_free')
    ax.set_ylabel('D_free (×10⁻³ mm²/s)')
    ax.set_title('Directional Bi-exponential Model')
    ax.set_xlim([0, 1])
    ax.set_ylim([2.0, 4.0])
    plt.colorbar(scatter, ax=ax, label='D_free')
    
    # Plot 3: D_free histogram comparison
    ax = axes[1, 0]
    ax.hist(std_d_vals, bins=50, alpha=0.5, label='Standard', color='blue')
    ax.hist(dir_d_vals, bins=50, alpha=0.5, label='Directional', color='red')
    ax.set_xlabel('D_free (×10⁻³ mm²/s)')
    ax.set_ylabel('Count')
    ax.set_title('D_free Distribution Comparison')
    ax.legend()
    ax.axvline(3.0, color='black', linestyle='--', label='Expected (37°C)')
    
    # Plot 4: f_free histogram comparison
    ax = axes[1, 1]
    ax.hist(std_f_vals, bins=50, alpha=0.5, label='Standard', color='blue')
    ax.hist(dir_f_vals, bins=50, alpha=0.5, label='Directional', color='red')
    ax.set_xlabel('f_free')
    ax.set_ylabel('Count')
    ax.set_title('Free Water Fraction Distribution')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig('directional_model_comparison.png', dpi=150)
    print("Saved comparison plot: directional_model_comparison.png")
    
    # Print statistics
    print("\n=== Model Comparison ===")
    print(f"Standard Model:")
    print(f"  D_free: {np.mean(std_d_vals):.3f} ± {np.std(std_d_vals):.3f} × 10⁻³ mm²/s")
    print(f"  f_free: {np.mean(std_f_vals):.3f} ± {np.std(std_f_vals):.3f}")
    print(f"  Bifurcation check: {check_bifurcation(std_d_vals)}")
    
    print(f"\nDirectional Model:")
    print(f"  D_free: {np.mean(dir_d_vals):.3f} ± {np.std(dir_d_vals):.3f} × 10⁻³ mm²/s")
    print(f"  f_free: {np.mean(dir_f_vals):.3f} ± {np.std(dir_f_vals):.3f}")
    print(f"  Bifurcation check: {check_bifurcation(dir_d_vals)}")

def check_bifurcation(values):
    """Check for bifurcation in the distribution"""
    from scipy.stats import gaussian_kde
    
    # Create KDE
    kde = gaussian_kde(values)
    x = np.linspace(values.min(), values.max(), 100)
    density = kde(x)
    
    # Find peaks
    peaks = []
    for i in range(1, len(density)-1):
        if density[i] > density[i-1] and density[i] > density[i+1]:
            peaks.append(x[i])
    
    if len(peaks) > 1:
        return f"Bifurcated (peaks at {[f'{p:.3f}' for p in peaks]})"
    else:
        return "Single peak (no bifurcation)"

if __name__ == "__main__":
    print("Testing Directional Bi-exponential Model")
    print("=" * 50)
    
    # Check if we should run the model or just compare
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Run the directional model")
    parser.add_argument("--compare", action="store_true", help="Compare results")
    args = parser.parse_args()
    
    if args.run:
        print("\nRunning directional model...")
        success = run_directional_model()
        if not success:
            print("Failed to run directional model")
            sys.exit(1)
    
    if args.compare or (not args.run and not args.compare):
        print("\nComparing results...")
        compare_results()