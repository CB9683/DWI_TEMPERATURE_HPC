#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import json
import logging
import warnings
from datetime import datetime
import re

import numpy as np
import pandas as pd
import nibabel as nib
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore')

def setup_logging(log_file):
    if os.path.exists(log_file):
        os.remove(log_file)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger(__name__)

def run_command(cmd, logger):
    cmd_str = ' '.join(cmd) if isinstance(cmd, list) else cmd
    logger.info(f"RUNNING: {cmd_str}")
    use_shell = isinstance(cmd, str)
    result = subprocess.run(cmd, shell=use_shell, capture_output=True, text=True)
    if result.stdout:
        logger.info(f"STDOUT:\n{result.stdout.strip()}")
    if result.stderr:
        logger.warning(f"STDERR:\n{result.stderr.strip()}")
    if result.returncode != 0:
        logger.error(f"Command failed with exit code {result.returncode}")
        sys.exit(1)
    logger.info("SUCCESS")
    return result

def main():
    parser = argparse.ArgumentParser(
        description="Create a highly stable temperature map by comparing two different b-value analyses.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("subject_id")
    parser.add_argument("output_dir")
    parser.add_argument("analysis_suffix1")
    parser.add_argument("analysis_suffix2")
    parser.add_argument("--threshold", type=float, default=2.0)
    args = parser.parse_args()

    sub_out_dir = os.path.join(args.output_dir, args.subject_id)
    stable_analysis_dir = os.path.join(sub_out_dir, f'stable_analysis_{args.analysis_suffix1}_vs_{args.analysis_suffix2}')
    os.makedirs(stable_analysis_dir, exist_ok=True)
    log_file = os.path.join(stable_analysis_dir, 'log_stable_analysis.txt')
    logger = setup_logging(log_file)
    
    logger.info("======================================================")
    logger.info("      Creating Stable Temperature Analysis (v6 - Final Fix)")
    logger.info("======================================================")

    map1_path = os.path.join(sub_out_dir, f'tmp_{args.analysis_suffix1}', 'temp_map_masked.nii.gz')
    map2_path = os.path.join(sub_out_dir, f'tmp_{args.analysis_suffix2}', 'temp_map_masked.nii.gz')
    bg_image_path = os.path.join(sub_out_dir, 'dwi_upsampled.mif')

    for path in [map1_path, map2_path, bg_image_path]:
        if not os.path.exists(path):
            logger.error(f"Required input file not found: {path}")
            sys.exit(1)
    logger.info("All required input files found.")

    diff_map = os.path.join(stable_analysis_dir, 'temp_difference.mif')
    stable_mask = os.path.join(stable_analysis_dir, 'stable_voxels_mask.mif')
    stable_temp_map = os.path.join(stable_analysis_dir, 'stable_temperature_map.mif')
    stats_csv = os.path.join(stable_analysis_dir, 'stable_analysis_stats.csv')
    vis_png = os.path.join(stable_analysis_dir, 'stable_analysis_visualization.png')
    
    union_mask = os.path.join(stable_analysis_dir, 'tmp_union_mask.mif')
    masked_diff_map = os.path.join(stable_analysis_dir, 'tmp_masked_diff_map.mif')

    # --- CORE LOGIC - CORRECTED COMMAND ---
    logger.info("Step 1: Creating a union mask of all analyzed voxels.")
    # The erroneous '-' after '-add' has been REMOVED.
    run_command(['mrcalc', map1_path, map2_path, '-add', '-abs', '0.0001', '-gt', union_mask, '-force'], logger)

    logger.info("Step 2: Calculating absolute temperature difference between maps.")
    run_command(['mrcalc', map1_path, map2_path, '-sub', '-abs', diff_map, '-force'], logger)
    
    logger.info("Step 3: Masking the difference map to exclude background.")
    run_command(['mrcalc', diff_map, union_mask, '-mult', masked_diff_map, '-force'], logger)

    logger.info(f"Step 4: Creating stable voxel mask (difference < {args.threshold}°C).")
    run_command(['mrthreshold', masked_diff_map, '-abs', str(args.threshold), '-invert', stable_mask, '-force'], logger)

    logger.info("Step 5: Applying stable mask to create the final temperature map.")
    run_command(['mrcalc', map1_path, stable_mask, '-mult', stable_temp_map, '-force'], logger)
    # --- END OF CORE LOGIC ---
    
    logger.info("Step 6: Calculating statistics for the stable temperature map.")
    stats_result = run_command(['mrstats', stable_temp_map, '-mask', stable_mask], logger)
    
    output_lines = stats_result.stdout.strip().split('\n')
    stats_dict = {}
    if len(output_lines) < 2:
        logger.warning("mrstats did not produce a table. No stable voxels found.")
        keys = ['volume', 'count', 'mean', 'median', 'std', 'min', 'max']
        stats_dict = {key: 0 for key in keys}
    else:
        header = re.findall(r'\S+', output_lines[0])
        values = re.findall(r'\S+', output_lines[1])
        if '[' in values and ']' in values:
            start_index, end_index = values.index('['), values.index(']')
            if end_index == start_index + 2:
                values = values[:start_index] + [values[start_index+1]] + values[end_index+1:]
        if len(header) == len(values):
            stats_dict = dict(zip(header, values))
        else:
            logger.error("Mismatch between header and values from mrstats.")
            keys = ['volume', 'count', 'mean', 'median', 'std', 'min', 'max']
            stats_dict = {key: 0 for key in keys}
    
    voxel_vol_mm3 = 1.5 * 1.5 * 1.5
    num_voxels = int(float(stats_dict.get('count', 0)))
    calculated_volume_ml = (num_voxels * voxel_vol_mm3) / 1000.0

    final_stats = {
        'subject_id': args.subject_id,
        'comparison': f"{args.analysis_suffix1}_vs_{args.analysis_suffix2}",
        'threshold_C': args.threshold,
        'num_stable_voxels': num_voxels,
        'stable_volume_ml': calculated_volume_ml,
        'temp_mean_C': float(stats_dict.get('mean', 0)),
        'temp_median_C': float(stats_dict.get('median', 0)),
        'temp_std_C': float(stats_dict.get('std', 0)),
        'temp_min_C': float(stats_dict.get('min', 0)),
        'temp_max_C': float(stats_dict.get('max', 0))
    }
    
    pd.DataFrame([final_stats]).to_csv(stats_csv, index=False)
    logger.info(f"Statistics saved to: {stats_csv}")

    logger.info("Step 7: Generating visualization with corrected colorbar placement.")
    temp_nii_path = os.path.join(stable_analysis_dir, 'stable_temp_map.nii.gz')
    bg_nii_path = os.path.join(stable_analysis_dir, 'bg_image.nii.gz')
    run_command(['mrconvert', stable_temp_map, temp_nii_path, '-force', '-quiet'], logger)
    run_command(['mrconvert', bg_image_path, bg_nii_path, '-coord', '3', '0', '-force', '-quiet'], logger)

    stable_temp_data = nib.load(temp_nii_path).get_fdata()
    map1_data = nib.load(map1_path).get_fdata()
    map2_data = nib.load(map2_path).get_fdata()
    bg_data = nib.load(bg_nii_path).get_fdata()

    slice_idx = bg_data.shape[2] // 2
    plausible_temps = stable_temp_data[stable_temp_data > 0]

    fig, axes = plt.subplots(2, 2, figsize=(14, 12), facecolor='black')
    fig.suptitle(f'Stable Temperature Analysis: {args.subject_id}', fontsize=16, color='white')
    
    cmap, vmin, vmax = 'hot', 30, 45

    ax = axes[0, 0]
    ax.imshow(np.rot90(bg_data[:, :, slice_idx]), cmap='gray')
    map1_slice = np.ma.masked_where(map1_data[:, :, slice_idx] == 0, np.rot90(map1_data[:, :, slice_idx]))
    im = ax.imshow(map1_slice, cmap=cmap, alpha=0.7, vmin=vmin, vmax=vmax)
    ax.set_title(f'Original Map 1 ({args.analysis_suffix1})', color='white')
    ax.axis('off')

    ax = axes[0, 1]
    ax.imshow(np.rot90(bg_data[:, :, slice_idx]), cmap='gray')
    map2_slice = np.ma.masked_where(map2_data[:, :, slice_idx] == 0, np.rot90(map2_data[:, :, slice_idx]))
    ax.imshow(map2_slice, cmap=cmap, alpha=0.7, vmin=vmin, vmax=vmax)
    ax.set_title(f'Original Map 2 ({args.analysis_suffix2})', color='white')
    ax.axis('off')

    ax = axes[1, 0]
    ax.imshow(np.rot90(bg_data[:, :, slice_idx]), cmap='gray')
    stable_slice = np.ma.masked_where(stable_temp_data[:, :, slice_idx] == 0, np.rot90(stable_temp_data[:, :, slice_idx]))
    ax.imshow(stable_slice, cmap=cmap, alpha=0.8, vmin=vmin, vmax=vmax)
    ax.set_title(f'Final Stable Map (Diff < {args.threshold}°C)', color='white')
    ax.axis('off')

    ax = axes[1, 1]
    if plausible_temps.size > 0:
        ax.hist(plausible_temps, bins=40, color='cyan', alpha=0.8, edgecolor='white', range=(10, 45))
        ax.axvline(final_stats['temp_mean_C'], color='red', linestyle='--', label=f"Mean: {final_stats['temp_mean_C']:.2f}°C")
        ax.axvline(final_stats['temp_median_C'], color='yellow', linestyle='--', label=f"Median: {final_stats['temp_median_C']:.2f}°C")
        ax.set_title('Distribution of Stable Temperatures', color='white')
        ax.set_xlabel('Temperature (°C)', color='white')
        ax.set_ylabel('Voxel Count', color='white')
        ax.legend()
        ax.tick_params(colors='white')
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
    else:
        ax.text(0.5, 0.5, 'No stable voxels found', ha='center', va='center', color='red')
    
    plt.subplots_adjust(right=0.88)
    cbar_ax = fig.add_axes([0.9, 0.15, 0.03, 0.7])
    cbar = fig.colorbar(im, cax=cbar_ax)
    cbar.set_label('Temperature (°C)', color='white')
    cbar.ax.tick_params(colors='white')

    plt.savefig(vis_png, dpi=150, bbox_inches='tight', facecolor='black')
    plt.close()
    logger.info(f"Visualization saved to: {vis_png}")
    
    logger.info("\n=== Stable Analysis Complete! ===")

if __name__ == "__main__":
    main()