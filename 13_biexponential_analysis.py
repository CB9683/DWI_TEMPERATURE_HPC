#!/usr/bin/env python3
import os, sys, argparse, glob, numpy as np, pandas as pd, matplotlib.pyplot as plt
import seaborn as sns, json, nibabel as nib
from matplotlib.gridspec import GridSpec
from matplotlib.colors import Normalize
import matplotlib.cm as cm

def load_parameter_maps(sub_out_dir, suffix, logger=None):
    """Load all bi-exponential parameter maps"""
    if logger:
        logger.info(f"Loading parameter maps for {suffix}")
    
    maps = {}
    map_files = {
        'd_free': f'd_free_map_{suffix}.nii.gz',
        'd_tissue': f'd_tissue_map_{suffix}.nii.gz',
        'f_free': f'f_free_map_{suffix}.nii.gz',
        'r_squared': f'r_squared_map_{suffix}.nii.gz',
        'model_used': f'model_used_map_{suffix}.nii.gz',
        'temperature': f'temperature_map_{suffix}.mif',
        'csf_mask': f'csf_mask_cleaned_{suffix}.mif'
    }
    
    for key, filename in map_files.items():
        filepath = os.path.join(sub_out_dir, filename)
        if os.path.exists(filepath):
            if filename.endswith('.mif'):
                # Convert MIF to NIfTI first
                nii_path = filepath.replace('.mif', '.nii.gz')
                if not os.path.exists(nii_path):
                    os.system(f'mrconvert {filepath} {nii_path} -quiet -force')
                maps[key] = nib.load(nii_path).get_fdata()
            else:
                maps[key] = nib.load(filepath).get_fdata()
        else:
            if logger:
                logger.warning(f"File not found: {filepath}")
            maps[key] = None
    
    # Also try to load FA if available
    fa_path = os.path.join(sub_out_dir, 'dti', 'fa.nii.gz')
    if os.path.exists(fa_path):
        maps['fa'] = nib.load(fa_path).get_fdata()
    else:
        maps['fa'] = None
    
    return maps

def create_parameter_visualization(maps, output_file, subject_id, suffix):
    """Create comprehensive visualization of bi-exponential parameters"""
    
    # Create figure with multiple panels
    fig = plt.figure(figsize=(20, 16), facecolor='white')
    gs = GridSpec(4, 4, figure=fig, hspace=0.3, wspace=0.3)
    
    # Get slice indices
    if maps['csf_mask'] is not None:
        mask = maps['csf_mask']
        slice_idx = mask.shape[2] // 2
    else:
        slice_idx = maps['d_free'].shape[2] // 2 if maps['d_free'] is not None else 30
    
    # Panel 1: D_free map
    ax1 = fig.add_subplot(gs[0, 0])
    if maps['d_free'] is not None:
        d_free_slice = maps['d_free'][:, :, slice_idx] * 1000  # Convert to ×10⁻³ mm²/s
        im1 = ax1.imshow(np.rot90(d_free_slice), cmap='hot', vmin=2.0, vmax=4.0)
        ax1.set_title('D_free (×10⁻³ mm²/s)', fontsize=12)
        plt.colorbar(im1, ax=ax1, fraction=0.046)
    ax1.axis('off')
    
    # Panel 2: D_tissue map
    ax2 = fig.add_subplot(gs[0, 1])
    if maps['d_tissue'] is not None:
        d_tissue_slice = maps['d_tissue'][:, :, slice_idx] * 1000
        im2 = ax2.imshow(np.rot90(d_tissue_slice), cmap='viridis', vmin=0.0, vmax=1.5)
        ax2.set_title('D_tissue (×10⁻³ mm²/s)', fontsize=12)
        plt.colorbar(im2, ax=ax2, fraction=0.046)
    ax2.axis('off')
    
    # Panel 3: Free water fraction
    ax3 = fig.add_subplot(gs[0, 2])
    if maps['f_free'] is not None:
        f_free_slice = maps['f_free'][:, :, slice_idx]
        im3 = ax3.imshow(np.rot90(f_free_slice), cmap='Blues', vmin=0, vmax=1)
        ax3.set_title('Free Water Fraction', fontsize=12)
        plt.colorbar(im3, ax=ax3, fraction=0.046)
    ax3.axis('off')
    
    # Panel 4: R² map
    ax4 = fig.add_subplot(gs[0, 3])
    if maps['r_squared'] is not None:
        r2_slice = maps['r_squared'][:, :, slice_idx]
        im4 = ax4.imshow(np.rot90(r2_slice), cmap='RdYlGn', vmin=0.5, vmax=1.0)
        ax4.set_title('Fitting Quality (R²)', fontsize=12)
        plt.colorbar(im4, ax=ax4, fraction=0.046)
    ax4.axis('off')
    
    # Panel 5: Model used map
    ax5 = fig.add_subplot(gs[1, 0])
    if maps['model_used'] is not None:
        model_slice = maps['model_used'][:, :, slice_idx]
        im5 = ax5.imshow(np.rot90(model_slice), cmap='tab10', vmin=0, vmax=2)
        ax5.set_title('Model Used\n(0=none, 1=mono, 2=biexp)', fontsize=12)
        cbar = plt.colorbar(im5, ax=ax5, fraction=0.046, ticks=[0, 1, 2])
        cbar.set_ticklabels(['None', 'Mono', 'Biexp'])
    ax5.axis('off')
    
    # Panel 6: Temperature map
    ax6 = fig.add_subplot(gs[1, 1])
    if maps['temperature'] is not None:
        temp_slice = maps['temperature'][:, :, slice_idx]
        im6 = ax6.imshow(np.rot90(temp_slice), cmap='hot', vmin=30, vmax=42)
        ax6.set_title('Temperature (°C)', fontsize=12)
        plt.colorbar(im6, ax=ax6, fraction=0.046)
    ax6.axis('off')
    
    # Panel 7: FA overlay (if available)
    ax7 = fig.add_subplot(gs[1, 2])
    if maps['fa'] is not None:
        fa_slice = maps['fa'][:, :, slice_idx]
        im7 = ax7.imshow(np.rot90(fa_slice), cmap='gray', vmin=0, vmax=0.5)
        # Overlay CSF mask
        if maps['csf_mask'] is not None:
            mask_slice = maps['csf_mask'][:, :, slice_idx]
            masked = np.ma.masked_where(mask_slice == 0, mask_slice)
            ax7.imshow(np.rot90(masked), cmap='Reds', alpha=0.3)
        ax7.set_title('FA with CSF overlay', fontsize=12)
        plt.colorbar(im7, ax=ax7, fraction=0.046)
    ax7.axis('off')
    
    # Panel 8: D_free vs f_free scatter
    ax8 = fig.add_subplot(gs[1, 3])
    if maps['d_free'] is not None and maps['f_free'] is not None and maps['csf_mask'] is not None:
        mask_bool = maps['csf_mask'] > 0
        biexp_bool = maps['model_used'] == 2
        valid = mask_bool & biexp_bool & (maps['d_free'] > 0)
        
        if np.any(valid):
            d_free_vals = maps['d_free'][valid] * 1000
            f_free_vals = maps['f_free'][valid]
            
            scatter = ax8.scatter(f_free_vals, d_free_vals, c=maps['temperature'][valid], 
                                 cmap='hot', alpha=0.5, s=1)
            ax8.set_xlabel('Free Water Fraction')
            ax8.set_ylabel('D_free (×10⁻³ mm²/s)')
            ax8.set_title('D_free vs Free Water Fraction')
            ax8.grid(True, alpha=0.3)
            plt.colorbar(scatter, ax=ax8, label='Temp (°C)')
    
    # Panel 9-10: Parameter distributions
    ax9 = fig.add_subplot(gs[2, :2])
    if maps['d_free'] is not None and maps['csf_mask'] is not None:
        mask_bool = maps['csf_mask'] > 0
        biexp_bool = maps['model_used'] == 2
        valid = mask_bool & biexp_bool & (maps['d_free'] > 0)
        
        if np.any(valid):
            d_free_vals = maps['d_free'][valid] * 1000
            ax9.hist(d_free_vals, bins=50, alpha=0.7, color='red', edgecolor='black')
            ax9.axvline(np.mean(d_free_vals), color='darkred', linestyle='--', 
                       label=f'Mean: {np.mean(d_free_vals):.3f}')
            ax9.axvline(3.0, color='green', linestyle=':', 
                       label='Expected at 37°C: 3.0')
            ax9.set_xlabel('D_free (×10⁻³ mm²/s)')
            ax9.set_ylabel('Frequency')
            ax9.set_title('D_free Distribution')
            ax9.legend()
            ax9.grid(True, alpha=0.3)
    
    # Panel 11-12: Free water fraction distribution
    ax10 = fig.add_subplot(gs[2, 2:])
    if maps['f_free'] is not None and maps['csf_mask'] is not None:
        mask_bool = maps['csf_mask'] > 0
        biexp_bool = maps['model_used'] == 2
        valid = mask_bool & biexp_bool
        
        if np.any(valid):
            f_free_vals = maps['f_free'][valid]
            ax10.hist(f_free_vals, bins=50, alpha=0.7, color='blue', edgecolor='black')
            ax10.axvline(np.mean(f_free_vals), color='darkblue', linestyle='--', 
                        label=f'Mean: {np.mean(f_free_vals):.3f}')
            ax10.set_xlabel('Free Water Fraction')
            ax10.set_ylabel('Frequency')
            ax10.set_title('Free Water Fraction Distribution')
            ax10.legend()
            ax10.grid(True, alpha=0.3)
    
    # Panel 13-16: Statistics summary
    ax11 = fig.add_subplot(gs[3, :])
    ax11.axis('off')
    
    # Calculate statistics
    stats_text = f"Bi-exponential Analysis Summary - {subject_id} - {suffix}\n\n"
    
    if maps['model_used'] is not None and maps['csf_mask'] is not None:
        total_csf = np.sum(maps['csf_mask'] > 0)
        biexp_voxels = np.sum(maps['model_used'] == 2)
        mono_voxels = np.sum(maps['model_used'] == 1)
        
        stats_text += f"Total CSF voxels: {total_csf}\n"
        stats_text += f"Bi-exponential fits: {biexp_voxels} ({biexp_voxels/total_csf*100:.1f}%)\n"
        stats_text += f"Mono-exponential fits: {mono_voxels} ({mono_voxels/total_csf*100:.1f}%)\n\n"
        
        if biexp_voxels > 0:
            valid = (maps['model_used'] == 2) & (maps['csf_mask'] > 0)
            stats_text += f"D_free: {np.mean(maps['d_free'][valid])*1000:.3f} ± {np.std(maps['d_free'][valid])*1000:.3f} ×10⁻³ mm²/s\n"
            stats_text += f"D_tissue: {np.mean(maps['d_tissue'][valid])*1000:.3f} ± {np.std(maps['d_tissue'][valid])*1000:.3f} ×10⁻³ mm²/s\n"
            stats_text += f"Free water fraction: {np.mean(maps['f_free'][valid]):.3f} ± {np.std(maps['f_free'][valid]):.3f}\n"
            stats_text += f"Mean R²: {np.mean(maps['r_squared'][valid]):.3f}\n"
            
            if maps['fa'] is not None:
                # Ensure FA has same shape as other maps
                if maps['fa'].shape == valid.shape:
                    fa_vals = maps['fa'][valid]
                    stats_text += f"FA in bi-exp voxels: {np.mean(fa_vals):.3f} ± {np.std(fa_vals):.3f}\n"
                else:
                    stats_text += f"FA shape mismatch: {maps['fa'].shape} vs {valid.shape}\n"
    
    ax11.text(0.05, 0.95, stats_text, transform=ax11.transAxes, 
             fontsize=11, verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.suptitle(f'Bi-exponential Diffusion Analysis - {subject_id}', fontsize=16)
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Saved bi-exponential analysis to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Analyze bi-exponential fitting results.")
    parser.add_argument("subject_id")
    parser.add_argument("output_dir")
    parser.add_argument("--analysis_suffix", type=str, help="Specific analysis to visualize")
    args = parser.parse_args()
    
    sub_out_dir = os.path.join(args.output_dir, args.subject_id)
    biexp_dir = os.path.join(sub_out_dir, 'biexponential_analysis')
    os.makedirs(biexp_dir, exist_ok=True)
    
    print(f"=== Bi-exponential Analysis for Subject: {args.subject_id} ===")
    
    # Find all available analyses
    if args.analysis_suffix:
        suffixes = [args.analysis_suffix]
    else:
        # Find all d_free maps to identify analyses
        d_free_files = glob.glob(os.path.join(sub_out_dir, 'd_free_map_*.nii.gz'))
        suffixes = [os.path.basename(f).replace('d_free_map_', '').replace('.nii.gz', '') 
                   for f in d_free_files]
    
    if not suffixes:
        print("No bi-exponential analyses found!")
        return
    
    print(f"Found {len(suffixes)} analyses to process")
    
    # Process each analysis
    all_stats = []
    for suffix in suffixes:
        print(f"\nProcessing analysis: {suffix}")
        
        # Load parameter maps
        maps = load_parameter_maps(sub_out_dir, suffix)
        
        # Create visualization
        vis_file = os.path.join(biexp_dir, f'biexp_visualization_{suffix}.png')
        create_parameter_visualization(maps, vis_file, args.subject_id, suffix)
        
        # Collect statistics
        if maps['model_used'] is not None and maps['csf_mask'] is not None:
            total_csf = np.sum(maps['csf_mask'] > 0)
            biexp_voxels = np.sum(maps['model_used'] == 2)
            
            if biexp_voxels > 0:
                valid = (maps['model_used'] == 2) & (maps['csf_mask'] > 0)
                
                stats = {
                    'subject_id': args.subject_id,
                    'analysis': suffix,
                    'total_csf_voxels': total_csf,
                    'biexp_voxels': biexp_voxels,
                    'biexp_fraction': biexp_voxels / total_csf,
                    'd_free_mean': np.mean(maps['d_free'][valid]),
                    'd_free_std': np.std(maps['d_free'][valid]),
                    'd_tissue_mean': np.mean(maps['d_tissue'][valid]),
                    'd_tissue_std': np.std(maps['d_tissue'][valid]),
                    'f_free_mean': np.mean(maps['f_free'][valid]),
                    'f_free_std': np.std(maps['f_free'][valid]),
                    'r_squared_mean': np.mean(maps['r_squared'][valid])
                }
                
                if maps['fa'] is not None:
                    # Ensure FA has same shape as other maps
                    if maps['fa'].shape == valid.shape:
                        stats['fa_mean'] = np.mean(maps['fa'][valid])
                        stats['fa_std'] = np.std(maps['fa'][valid])
                    else:
                        print(f"Warning: FA shape mismatch for {suffix}: {maps['fa'].shape} vs {valid.shape}")
                
                all_stats.append(stats)
    
    # Save combined statistics
    if all_stats:
        stats_df = pd.DataFrame(all_stats)
        stats_file = os.path.join(biexp_dir, 'biexponential_statistics.csv')
        stats_df.to_csv(stats_file, index=False)
        print(f"\nSaved statistics to: {stats_file}")
    
    print("\n=== Bi-exponential analysis complete! ===")

if __name__ == "__main__":
    main()