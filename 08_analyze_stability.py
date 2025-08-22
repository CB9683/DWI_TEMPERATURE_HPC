#!/usr/bin/env python3
"""
analyze_temperature_stability.py

Analyzes temperature maps from different b-value combinations to identify
voxels with stable temperature measurements across analyses.
"""

import os
import sys
import argparse
import numpy as np
import nibabel as nib
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.gridspec import GridSpec
import subprocess
import glob
import json
from scipy import stats

def run_mrconvert(input_path, output_path):
    """Convert MRtrix format to NIfTI"""
    subprocess.run(['mrconvert', input_path, output_path, '-force', '-quiet'], check=True)
    return nib.load(output_path)

def load_temperature_maps(subject_dir):
    """Load all temperature maps and their metadata"""
    temp_map_pattern = os.path.join(subject_dir, 'temperature_map_*.mif')
    temp_map_files = sorted(glob.glob(temp_map_pattern))
    
    if not temp_map_files:
        raise FileNotFoundError(f"No temperature maps found in {subject_dir}")
    
    maps_data = {}
    for temp_file in temp_map_files:
        # Extract suffix (b-value combination)
        suffix = os.path.basename(temp_file).replace('temperature_map_', '').replace('.mif', '')
        
        # Convert to NIfTI and load
        nii_path = os.path.join(subject_dir, f'temp_{suffix}_for_stability.nii.gz')
        temp_img = run_mrconvert(temp_file, nii_path)
        temp_data = temp_img.get_fdata()
        
        # Also load the corresponding CSF mask
        mask_file = os.path.join(subject_dir, f'csf_mask_cleaned_{suffix}.mif')
        if os.path.exists(mask_file):
            mask_nii_path = os.path.join(subject_dir, f'mask_{suffix}_for_stability.nii.gz')
            mask_img = run_mrconvert(mask_file, mask_nii_path)
            mask_data = mask_img.get_fdata()
        else:
            mask_data = temp_data > 0  # Use non-zero values as mask
        
        maps_data[suffix] = {
            'data': temp_data,
            'mask': mask_data,
            'affine': temp_img.affine,
            'shape': temp_data.shape
        }
    
    return maps_data

def calculate_stability_metrics(maps_data, min_valid_analyses=3):
    """Calculate temperature stability metrics across all voxels"""
    
    # Get reference shape from first map
    ref_shape = list(maps_data.values())[0]['shape']
    n_analyses = len(maps_data)
    
    # Initialize arrays to store metrics
    temp_mean = np.zeros(ref_shape)
    temp_std = np.zeros(ref_shape)
    temp_range = np.zeros(ref_shape)
    temp_cv = np.zeros(ref_shape)  # Coefficient of variation
    n_valid = np.zeros(ref_shape, dtype=int)  # Number of analyses with valid temp
    all_temps = np.zeros(ref_shape + (n_analyses,))
    
    # Stack all temperature data
    for i, (suffix, data) in enumerate(maps_data.items()):
        # Only include voxels that are in the CSF mask
        valid_mask = data['mask'] > 0
        all_temps[..., i] = np.where(valid_mask, data['data'], np.nan)
    
    # Calculate metrics for each voxel
    for i in range(ref_shape[0]):
        for j in range(ref_shape[1]):
            for k in range(ref_shape[2]):
                voxel_temps = all_temps[i, j, k, :]
                valid_temps = voxel_temps[~np.isnan(voxel_temps) & (voxel_temps > 0)]
                
                if len(valid_temps) >= min_valid_analyses:
                    temp_mean[i, j, k] = np.mean(valid_temps)
                    temp_std[i, j, k] = np.std(valid_temps)
                    temp_range[i, j, k] = np.max(valid_temps) - np.min(valid_temps)
                    temp_cv[i, j, k] = temp_std[i, j, k] / temp_mean[i, j, k] if temp_mean[i, j, k] > 0 else 0
                    n_valid[i, j, k] = len(valid_temps)
    
    return {
        'mean': temp_mean,
        'std': temp_std,
        'range': temp_range,
        'cv': temp_cv,
        'n_valid': n_valid,
        'all_temps': all_temps
    }

def identify_stable_voxels(stability_metrics, stability_threshold=2.0, min_analyses=5):
    """Identify voxels with stable temperature measurements"""
    
    # Stable voxels have low std deviation and sufficient measurements
    stable_mask = (
        (stability_metrics['std'] > 0) &  # Valid voxels
        (stability_metrics['std'] < stability_threshold) &  # Low variability
        (stability_metrics['n_valid'] >= min_analyses) &  # Enough measurements
        (stability_metrics['mean'] > 30) &  # Reasonable temperature
        (stability_metrics['mean'] < 50)
    )
    
    # Get voxel coordinates and values
    stable_coords = np.where(stable_mask)
    stable_voxels = []
    
    for i in range(len(stable_coords[0])):
        x, y, z = stable_coords[0][i], stable_coords[1][i], stable_coords[2][i]
        stable_voxels.append({
            'x': int(x),  # Ensure it's a Python int
            'y': int(y),
            'z': int(z),
            'mean_temp': float(stability_metrics['mean'][x, y, z]),  # Convert to Python float
            'std_temp': float(stability_metrics['std'][x, y, z]),
            'range_temp': float(stability_metrics['range'][x, y, z]),
            'cv': float(stability_metrics['cv'][x, y, z]),
            'n_analyses': int(stability_metrics['n_valid'][x, y, z])  # Fixed: ensure scalar
        })
    
    return stable_mask, pd.DataFrame(stable_voxels)

def create_stability_visualization(maps_data, stability_metrics, stable_mask, stable_df, 
                                 output_dir, subject_id, stability_threshold):
    """Create comprehensive visualization of temperature stability"""
    
    fig = plt.figure(figsize=(20, 16))
    gs = GridSpec(4, 3, figure=fig, hspace=0.5, wspace=0.5)
    
    # Get middle slice for visualization
    mid_slice = stability_metrics['mean'].shape[2] // 2
    
    # Load a background image (use first temperature map)
    first_suffix = list(maps_data.keys())[0]
    bg_data = maps_data[first_suffix]['data']
    
    # 1. Mean temperature map
    ax1 = fig.add_subplot(gs[0, 0])
    mean_slice = stability_metrics['mean'][:, :, mid_slice]
    im1 = ax1.imshow(np.rot90(mean_slice), cmap='hot', vmin=0, vmax=50)
    ax1.set_title('Mean Temperature Across Analyses', fontsize=12)
    ax1.axis('off')
    plt.colorbar(im1, ax=ax1, label='Temperature (°C)')
    
    # 2. Standard deviation map
    ax2 = fig.add_subplot(gs[0, 1])
    std_slice = stability_metrics['std'][:, :, mid_slice]
    im2 = ax2.imshow(np.rot90(std_slice), cmap='viridis', vmin=0, vmax=5)
    ax2.set_title('Temperature Std Dev Across Analyses', fontsize=12)
    ax2.axis('off')
    plt.colorbar(im2, ax=ax2, label='Std Dev (°C)')
    
    # 3. Stable voxels map
    ax3 = fig.add_subplot(gs[0, 2])
    stable_slice = stable_mask[:, :, mid_slice]
    # Show background with stable voxels overlay
    ax3.imshow(np.rot90(bg_data[:, :, mid_slice, 0]), cmap='gray', alpha=0.7)
    stable_overlay = np.ma.masked_where(~np.rot90(stable_slice), np.ones_like(stable_slice))
    ax3.imshow(stable_overlay, cmap='spring', alpha=0.8)
    ax3.set_title(f'Stable Voxels (std < {stability_threshold}°C)', fontsize=12)
    ax3.axis('off')
    
    # 4. Distribution of temperature variability
    ax4 = fig.add_subplot(gs[1, :])
    all_stds = stability_metrics['std'][stability_metrics['std'] > 0].flatten()
    ax4.hist(all_stds, bins=60, alpha=0.7, color='blue', edgecolor='black')
    ax4.axvline(stability_threshold, color='red', linestyle='--', 
                label=f'Stability threshold: {stability_threshold}°C')
    ax4.set_xlabel('Temperature Std Dev (°C)')
    ax4.set_ylabel('Number of Voxels')
    ax4.set_title('Distribution of Temperature Variability')
    ax4.legend()
    ax4.set_xlim(0, 60)
    
    # 5. Scatter plot: Mean vs Std Dev
    ax5 = fig.add_subplot(gs[2, 0])
    valid_mask = stability_metrics['mean'] > -25
    ax5.scatter(stability_metrics['mean'][valid_mask], 
                stability_metrics['std'][valid_mask], 
                alpha=0.5, s=1)
    if len(stable_df) > 0:
        ax5.scatter(stable_df['mean_temp'], stable_df['std_temp'], 
                    color='red', alpha=0.1, s=1, label='Stable voxels')
    ax5.set_xlabel('Mean Temperature (°C)')
    ax5.set_ylabel('Std Dev (°C)')
    ax5.set_title('Temperature Stability')
    ax5.legend()
    ax5.set_xlim(-25, 100)
    ax5.set_ylim(0, 50)
    
    # 6. Top stable voxels table
    ax6 = fig.add_subplot(gs[2, 1:])
    ax6.axis('tight')
    ax6.axis('off')
    
    if len(stable_df) > 0:
        # Get top 10 most stable voxels
        top_stable = stable_df.nsmallest(10, 'std_temp')[['x', 'y', 'z', 'mean_temp', 'std_temp', 'cv']]
        
        table_data = []
        for _, row in top_stable.iterrows():
            table_data.append([f"({int(row['x'])}, {int(row['y'])}, {int(row['z'])})",
                              f"{row['mean_temp']:.2f}",
                              f"{row['std_temp']:.3f}",
                              f"{row['cv']:.3f}"])
        
        table = ax6.table(cellText=table_data,
                         colLabels=['Voxel (x,y,z)', 'Mean T (°C)', 'Std (°C)', 'CV'],
                         cellLoc='center',
                         loc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 1.5)
        ax6.set_title('Top 10 Most Stable Voxels', pad=20)
    else:
        ax6.text(0.5, 0.5, 'No stable voxels found', ha='center', va='center')
    
    # 7. Temperature correlation between different b-value sets
    ax7 = fig.add_subplot(gs[3, :])
    
    # Create correlation matrix
    suffixes = list(maps_data.keys())
    n_suffixes = len(suffixes)
    correlation_matrix = np.zeros((n_suffixes, n_suffixes))
    
    for i, suffix1 in enumerate(suffixes):
        for j, suffix2 in enumerate(suffixes):
            if i <= j:
                mask1 = maps_data[suffix1]['mask'] > 0
                mask2 = maps_data[suffix2]['mask'] > 0
                common_mask = mask1 & mask2
                
                if np.sum(common_mask) > 100:
                    temp1 = maps_data[suffix1]['data'][common_mask]
                    temp2 = maps_data[suffix2]['data'][common_mask]
                    correlation_matrix[i, j] = np.corrcoef(temp1, temp2)[0, 1]
                    correlation_matrix[j, i] = correlation_matrix[i, j]
    
    # Plot correlation heatmap
    sns.heatmap(correlation_matrix, annot=True, fmt='.3f', cmap='coolwarm',
                xticklabels=suffixes, yticklabels=suffixes, ax=ax7,
                vmin=-1.0, vmax=1.0, cbar_kws={'label': 'Correlation'})
    ax7.set_title('Temperature Correlation Between B-value Combinations')
    
    plt.suptitle(f'Temperature Stability Analysis - {subject_id}', fontsize=16)
    plt.tight_layout()
    
    output_path = os.path.join(output_dir, 'temperature_stability_analysis.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    return output_path

def save_stable_voxel_data(stable_df, stability_metrics, maps_data, output_dir):
    """Save detailed data about stable voxels"""
    
    # Save stable voxel statistics
    stable_stats_path = os.path.join(output_dir, 'stable_voxels_statistics.csv')
    stable_df.to_csv(stable_stats_path, index=False)
    
    # Save temperature values for each stable voxel across all analyses
    if len(stable_df) > 0:
        stable_temps_detail = []
        
        for _, voxel in stable_df.iterrows():
            x, y, z = int(voxel['x']), int(voxel['y']), int(voxel['z'])
            row_data = {
                'voxel_coord': f"({x},{y},{z})",
                'mean_temp': voxel['mean_temp'],
                'std_temp': voxel['std_temp']
            }
            
            # Add temperature from each analysis
            for suffix, data in maps_data.items():
                if data['mask'][x, y, z] > 0:
                    row_data[f'temp_{suffix}'] = float(data['data'][x, y, z])
                else:
                    row_data[f'temp_{suffix}'] = np.nan
            
            stable_temps_detail.append(row_data)
        
        detail_df = pd.DataFrame(stable_temps_detail)
        detail_path = os.path.join(output_dir, 'stable_voxels_temperature_details.csv')
        detail_df.to_csv(detail_path, index=False)
    
    # Save stability map as NIfTI
    ref_data = list(maps_data.values())[0]
    stability_img = nib.Nifti1Image(stability_metrics['std'], ref_data['affine'])
    stability_path = os.path.join(output_dir, 'temperature_stability_map.nii.gz')
    nib.save(stability_img, stability_path)
    
    print(f"\nSaved outputs:")
    print(f"- Stable voxel statistics: {stable_stats_path}")
    if len(stable_df) > 0:
        print(f"- Detailed temperature values: {os.path.join(output_dir, 'stable_voxels_temperature_details.csv')}")
    print(f"- Stability map (NIfTI): {stability_path}")

def main():
    parser = argparse.ArgumentParser(description="Analyze temperature stability across b-value combinations")
    parser.add_argument("subject_id", help="Subject ID")
    parser.add_argument("output_dir", help="Pipeline output directory")
    parser.add_argument("--stability_threshold", type=float, default=2.0,
                       help="Maximum std dev for stable voxels (°C)")
    parser.add_argument("--min_analyses", type=int, default=5,
                       help="Minimum number of analyses for stability")
    parser.add_argument("--min_valid_analyses", type=int, default=3,
                       help="Minimum analyses with valid temperature for a voxel")
    
    args = parser.parse_args()
    
    subject_dir = os.path.join(args.output_dir, args.subject_id)
    
    print(f"=== Temperature Stability Analysis ===")
    print(f"Subject: {args.subject_id}")
    print(f"Directory: {subject_dir}")
    print(f"Stability threshold: {args.stability_threshold}°C")
    
    # Load all temperature maps
    print("\nLoading temperature maps...")
    maps_data = load_temperature_maps(subject_dir)
    print(f"Found {len(maps_data)} temperature maps: {list(maps_data.keys())}")
    
    # Calculate stability metrics
    print("\nCalculating stability metrics...")
    stability_metrics = calculate_stability_metrics(maps_data, args.min_valid_analyses)
    
    # Identify stable voxels
    print("\nIdentifying stable voxels...")
    stable_mask, stable_df = identify_stable_voxels(
        stability_metrics, args.stability_threshold, args.min_analyses
    )
    
    print(f"\nFound {len(stable_df)} stable voxels")
    if len(stable_df) > 0:
        # Fixed: Convert numpy values to Python scalars
        mean_temp = float(stable_df['mean_temp'].mean())
        std_temp = float(stable_df['mean_temp'].std())
        avg_std = float(stable_df['std_temp'].mean())
        
        print(f"Mean temperature of stable voxels: {mean_temp:.2f} ± {std_temp:.2f}°C")
        print(f"Average std dev of stable voxels: {avg_std:.3f}°C")
        
        # Show distribution of stable voxel temperatures
        print("\nTemperature distribution of stable voxels:")
        print(stable_df['mean_temp'].describe())
    
    # Create visualizations
    print("\nCreating visualizations...")
    viz_path = create_stability_visualization(
        maps_data, stability_metrics, stable_mask, stable_df,
        subject_dir, args.subject_id, args.stability_threshold
    )
    print(f"Saved visualization: {viz_path}")
    
    # Save detailed data
    print("\nSaving stable voxel data...")
    save_stable_voxel_data(stable_df, stability_metrics, maps_data, subject_dir)
    
    # Summary statistics
    total_csf_voxels = int(np.sum(stability_metrics['n_valid'] > 0))
    stable_percentage = (len(stable_df) / total_csf_voxels * 100) if total_csf_voxels > 0 else 0
    
    print(f"\n=== Summary ===")
    print(f"Total CSF voxels analyzed: {total_csf_voxels}")
    print(f"Stable voxels: {len(stable_df)} ({stable_percentage:.1f}%)")
    if len(stable_df) > 0:
        most_stable = stable_df.loc[stable_df['std_temp'].idxmin()]
        print(f"Most stable voxel: ({most_stable['x']}, {most_stable['y']}, {most_stable['z']}) "
              f"with temp {most_stable['mean_temp']:.2f} ± {most_stable['std_temp']:.3f}°C")

if __name__ == "__main__":
    main()