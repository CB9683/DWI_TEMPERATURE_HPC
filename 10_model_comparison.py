#!/usr/bin/env python3
import os, sys, argparse, glob, numpy as np, pandas as pd, matplotlib.pyplot as plt
import seaborn as sns, json, nibabel as nib
from matplotlib.gridspec import GridSpec
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

def run_temperature_calculation(subject_id, output_dir, bids_root, bvals, suffix, config_file, model='monoexponential'):
    """Run temperature calculation with specified model"""
    import subprocess
    import tempfile
    import shutil
    
    # Create temporary config with desired model
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Create temporary config file
    temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    config['processing']['temperature_model'] = model
    json.dump(config, temp_config)
    temp_config.close()
    
    # Prepare command
    cmd = [
        'python', '04_calculate_temperature.py',
        subject_id, output_dir, bids_root,
        '--bvals_for_adc'] + [str(b) for b in bvals] + [
        '--output_suffix', f'{suffix}_{model}',
        '--config_file', temp_config.name
    ]
    
    # Run command
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Clean up temp file
    os.unlink(temp_config.name)
    
    if result.returncode != 0:
        print(f"Error running {model} model: {result.stderr}")
        return False
    
    return True

def load_temperature_maps(sub_out_dir, suffix_base):
    """Load temperature maps from both models"""
    maps = {}
    
    # Load monoexponential results
    mono_temp_file = os.path.join(sub_out_dir, f'temperature_map_{suffix_base}_monoexponential.mif')
    if os.path.exists(mono_temp_file):
        nii_path = mono_temp_file.replace('.mif', '.nii.gz')
        os.system(f'mrconvert {mono_temp_file} {nii_path} -quiet -force')
        maps['mono_temp'] = nib.load(nii_path).get_fdata()
    
    # Load bi-exponential results
    biexp_temp_file = os.path.join(sub_out_dir, f'temperature_map_{suffix_base}_biexponential.mif')
    if os.path.exists(biexp_temp_file):
        nii_path = biexp_temp_file.replace('.mif', '.nii.gz')
        os.system(f'mrconvert {biexp_temp_file} {nii_path} -quiet -force')
        maps['biexp_temp'] = nib.load(nii_path).get_fdata()
    
    # Load other relevant maps
    maps['model_used'] = None
    model_file = os.path.join(sub_out_dir, f'model_used_map_{suffix_base}_biexponential.nii.gz')
    if os.path.exists(model_file):
        maps['model_used'] = nib.load(model_file).get_fdata()
    
    maps['r_squared'] = None
    r2_file = os.path.join(sub_out_dir, f'r_squared_map_{suffix_base}_biexponential.nii.gz')
    if os.path.exists(r2_file):
        maps['r_squared'] = nib.load(r2_file).get_fdata()
    
    maps['fa'] = None
    fa_file = os.path.join(sub_out_dir, 'dti', 'fa.nii.gz')
    if os.path.exists(fa_file):
        maps['fa'] = nib.load(fa_file).get_fdata()
    
    # Load CSF mask
    mask_file = os.path.join(sub_out_dir, f'csf_mask_cleaned_{suffix_base}_monoexponential.mif')
    if os.path.exists(mask_file):
        nii_path = mask_file.replace('.mif', '.nii.gz')
        os.system(f'mrconvert {mask_file} {nii_path} -quiet -force')
        maps['csf_mask'] = nib.load(nii_path).get_fdata()
    
    return maps

def create_comparison_visualization(maps, output_file, subject_id, suffix):
    """Create comprehensive comparison between mono and bi-exponential models"""
    
    fig = plt.figure(figsize=(20, 16), facecolor='white')
    gs = GridSpec(4, 4, figure=fig, hspace=0.3, wspace=0.3)
    
    # Get slice index
    if maps['csf_mask'] is not None:
        slice_idx = maps['csf_mask'].shape[2] // 2
    else:
        slice_idx = 50
    
    # Panel 1: Monoexponential temperature
    ax1 = fig.add_subplot(gs[0, 0])
    if maps['mono_temp'] is not None:
        mono_slice = maps['mono_temp'][:, :, slice_idx]
        masked_mono = np.ma.masked_where(mono_slice == 0, mono_slice)
        im1 = ax1.imshow(np.rot90(masked_mono), cmap='hot', vmin=30, vmax=42)
        ax1.set_title('Monoexponential Temperature', fontsize=12)
        plt.colorbar(im1, ax=ax1, fraction=0.046)
    ax1.axis('off')
    
    # Panel 2: Bi-exponential temperature
    ax2 = fig.add_subplot(gs[0, 1])
    if maps['biexp_temp'] is not None:
        biexp_slice = maps['biexp_temp'][:, :, slice_idx]
        masked_biexp = np.ma.masked_where(biexp_slice == 0, biexp_slice)
        im2 = ax2.imshow(np.rot90(masked_biexp), cmap='hot', vmin=30, vmax=42)
        ax2.set_title('Bi-exponential Temperature', fontsize=12)
        plt.colorbar(im2, ax=ax2, fraction=0.046)
    ax2.axis('off')
    
    # Panel 3: Temperature difference
    ax3 = fig.add_subplot(gs[0, 2])
    if maps['mono_temp'] is not None and maps['biexp_temp'] is not None:
        diff_slice = maps['biexp_temp'][:, :, slice_idx] - maps['mono_temp'][:, :, slice_idx]
        mask = (maps['mono_temp'][:, :, slice_idx] > 0) & (maps['biexp_temp'][:, :, slice_idx] > 0)
        masked_diff = np.ma.masked_where(~mask, diff_slice)
        im3 = ax3.imshow(np.rot90(masked_diff), cmap='RdBu_r', vmin=-2, vmax=2)
        ax3.set_title('Temperature Difference\n(Biexp - Mono)', fontsize=12)
        plt.colorbar(im3, ax=ax3, fraction=0.046)
    ax3.axis('off')
    
    # Panel 4: Model used overlay
    ax4 = fig.add_subplot(gs[0, 3])
    if maps['model_used'] is not None:
        model_slice = maps['model_used'][:, :, slice_idx]
        im4 = ax4.imshow(np.rot90(model_slice), cmap='tab10', vmin=0, vmax=2)
        ax4.set_title('Model Used in Biexp Run\n(1=mono fallback, 2=biexp)', fontsize=12)
        cbar = plt.colorbar(im4, ax=ax4, fraction=0.046, ticks=[0, 1, 2])
        cbar.set_ticklabels(['None', 'Mono', 'Biexp'])
    ax4.axis('off')
    
    # Panel 5: Temperature scatter plot
    ax5 = fig.add_subplot(gs[1, :2])
    if maps['mono_temp'] is not None and maps['biexp_temp'] is not None and maps['csf_mask'] is not None:
        mask = maps['csf_mask'] > 0
        mono_vals = maps['mono_temp'][mask]
        biexp_vals = maps['biexp_temp'][mask]
        valid = (mono_vals > 0) & (biexp_vals > 0) & np.isfinite(mono_vals) & np.isfinite(biexp_vals)
        
        if np.sum(valid) > 0:
            mono_valid = mono_vals[valid]
            biexp_valid = biexp_vals[valid]
            
            # Color by model used
            if maps['model_used'] is not None:
                model_vals = maps['model_used'][mask][valid]
                scatter = ax5.scatter(mono_valid, biexp_valid, c=model_vals, 
                                    cmap='tab10', alpha=0.5, s=1)
                plt.colorbar(scatter, ax=ax5, label='Model', ticks=[1, 2])
            else:
                ax5.scatter(mono_valid, biexp_valid, alpha=0.5, s=1)
            
            # Add identity line
            min_val = min(mono_valid.min(), biexp_valid.min())
            max_val = max(mono_valid.max(), biexp_valid.max())
            ax5.plot([min_val, max_val], [min_val, max_val], 'k--', alpha=0.5)
            
            # Calculate correlation
            corr = np.corrcoef(mono_valid, biexp_valid)[0, 1]
            ax5.set_xlabel('Monoexponential Temperature (°C)')
            ax5.set_ylabel('Bi-exponential Temperature (°C)')
            ax5.set_title(f'Temperature Correlation (r={corr:.3f})')
            ax5.grid(True, alpha=0.3)
    
    # Panel 6: Temperature difference vs FA
    ax6 = fig.add_subplot(gs[1, 2:])
    if (maps['mono_temp'] is not None and maps['biexp_temp'] is not None and 
        maps['fa'] is not None and maps['csf_mask'] is not None):
        
        mask = maps['csf_mask'] > 0
        temp_diff = maps['biexp_temp'][mask] - maps['mono_temp'][mask]
        fa_vals = maps['fa'][mask]
        valid = np.isfinite(temp_diff) & np.isfinite(fa_vals) & (fa_vals < 0.5)
        
        if np.sum(valid) > 0:
            scatter = ax6.scatter(fa_vals[valid], temp_diff[valid], 
                                c=maps['biexp_temp'][mask][valid], 
                                cmap='hot', alpha=0.5, s=1)
            ax6.set_xlabel('Fractional Anisotropy')
            ax6.set_ylabel('Temperature Difference (°C)')
            ax6.set_title('Temperature Correction vs FA')
            ax6.grid(True, alpha=0.3)
            ax6.axhline(0, color='black', linestyle='--', alpha=0.5)
            plt.colorbar(scatter, ax=ax6, label='Biexp Temp (°C)')
    
    # Panel 7: Temperature distributions
    ax7 = fig.add_subplot(gs[2, :])
    if maps['mono_temp'] is not None and maps['biexp_temp'] is not None and maps['csf_mask'] is not None:
        mask = maps['csf_mask'] > 0
        mono_vals = maps['mono_temp'][mask]
        biexp_vals = maps['biexp_temp'][mask]
        
        valid_mono = mono_vals[(mono_vals > 25) & (mono_vals < 50)]
        valid_biexp = biexp_vals[(biexp_vals > 25) & (biexp_vals < 50)]
        
        if len(valid_mono) > 0 and len(valid_biexp) > 0:
            bins = np.linspace(30, 45, 50)
            ax7.hist(valid_mono, bins=bins, alpha=0.5, label='Monoexponential', 
                    color='blue', density=True)
            ax7.hist(valid_biexp, bins=bins, alpha=0.5, label='Bi-exponential', 
                    color='red', density=True)
            
            # Add statistics
            ax7.axvline(np.mean(valid_mono), color='blue', linestyle='--', 
                       label=f'Mono mean: {np.mean(valid_mono):.2f}°C')
            ax7.axvline(np.mean(valid_biexp), color='red', linestyle='--', 
                       label=f'Biexp mean: {np.mean(valid_biexp):.2f}°C')
            
            ax7.set_xlabel('Temperature (°C)')
            ax7.set_ylabel('Density')
            ax7.set_title('Temperature Distribution Comparison')
            ax7.legend()
            ax7.grid(True, alpha=0.3)
    
    # Panel 8: Summary statistics
    ax8 = fig.add_subplot(gs[3, :])
    ax8.axis('off')
    
    stats_text = f"Model Comparison Summary - {subject_id} - {suffix}\n\n"
    
    if maps['mono_temp'] is not None and maps['biexp_temp'] is not None and maps['csf_mask'] is not None:
        mask = maps['csf_mask'] > 0
        mono_vals = maps['mono_temp'][mask]
        biexp_vals = maps['biexp_temp'][mask]
        valid = (mono_vals > 25) & (mono_vals < 50) & (biexp_vals > 25) & (biexp_vals < 50)
        
        if np.sum(valid) > 0:
            mono_valid = mono_vals[valid]
            biexp_valid = biexp_vals[valid]
            diff_valid = biexp_valid - mono_valid
            
            stats_text += f"Monoexponential:\n"
            stats_text += f"  Mean: {np.mean(mono_valid):.2f} ± {np.std(mono_valid):.2f}°C\n"
            stats_text += f"  Median: {np.median(mono_valid):.2f}°C\n"
            stats_text += f"  Range: [{np.min(mono_valid):.2f}, {np.max(mono_valid):.2f}]°C\n\n"
            
            stats_text += f"Bi-exponential:\n"
            stats_text += f"  Mean: {np.mean(biexp_valid):.2f} ± {np.std(biexp_valid):.2f}°C\n"
            stats_text += f"  Median: {np.median(biexp_valid):.2f}°C\n"
            stats_text += f"  Range: [{np.min(biexp_valid):.2f}, {np.max(biexp_valid):.2f}]°C\n\n"
            
            stats_text += f"Difference (Biexp - Mono):\n"
            stats_text += f"  Mean: {np.mean(diff_valid):.3f}°C\n"
            stats_text += f"  Std: {np.std(diff_valid):.3f}°C\n"
            stats_text += f"  Range: [{np.min(diff_valid):.3f}, {np.max(diff_valid):.3f}]°C\n"
            
            # Paired t-test
            t_stat, p_val = stats.ttest_rel(biexp_valid, mono_valid)
            stats_text += f"  Paired t-test: t={t_stat:.3f}, p={p_val:.3e}\n"
            
            if maps['model_used'] is not None:
                model_vals = maps['model_used'][mask][valid]
                biexp_used = np.sum(model_vals == 2)
                stats_text += f"\nBi-exponential model used: {biexp_used}/{len(model_vals)} voxels ({biexp_used/len(model_vals)*100:.1f}%)\n"
    
    ax8.text(0.05, 0.95, stats_text, transform=ax8.transAxes, 
             fontsize=11, verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))
    
    plt.suptitle(f'Mono vs Bi-exponential Model Comparison - {subject_id}', fontsize=16)
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Saved comparison to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Compare mono and bi-exponential temperature models.")
    parser.add_argument("subject_id")
    parser.add_argument("output_dir")
    parser.add_argument("bids_root")
    parser.add_argument("--config_file", type=str, required=True)
    parser.add_argument("--bvals", type=int, nargs='+', help="B-values to use")
    parser.add_argument("--suffix", type=str, help="Analysis suffix")
    parser.add_argument("--skip_calculation", action='store_true', 
                       help="Skip calculation if results already exist")
    args = parser.parse_args()
    
    sub_out_dir = os.path.join(args.output_dir, args.subject_id)
    comparison_dir = os.path.join(sub_out_dir, 'model_comparison')
    os.makedirs(comparison_dir, exist_ok=True)
    
    print(f"=== Model Comparison for Subject: {args.subject_id} ===")
    
    # Determine analyses to compare
    if args.bvals and args.suffix:
        analyses = [(args.bvals, args.suffix)]
    else:
        # Find existing monoexponential analyses
        mono_files = glob.glob(os.path.join(sub_out_dir, 'temperature_map_b*_monoexponential.mif'))
        analyses = []
        for f in mono_files:
            suffix = os.path.basename(f).replace('temperature_map_', '').replace('_monoexponential.mif', '')
            if not suffix.endswith('_biexponential'):
                analyses.append((None, suffix))
    
    if not analyses:
        print("No analyses found to compare!")
        return
    
    print(f"Found {len(analyses)} analyses to compare")
    
    all_stats = []
    for bvals, suffix in analyses:
        print(f"\nProcessing comparison for: {suffix}")
        
        # Check if we need to run calculations
        mono_exists = os.path.exists(os.path.join(sub_out_dir, f'temperature_map_{suffix}_monoexponential.mif'))
        biexp_exists = os.path.exists(os.path.join(sub_out_dir, f'temperature_map_{suffix}_biexponential.mif'))
        
        if not args.skip_calculation and (not mono_exists or not biexp_exists):
            if bvals is None:
                print(f"Cannot determine b-values for {suffix}, skipping calculation")
                continue
            
            print("Running temperature calculations...")
            
            if not mono_exists:
                print("  Running monoexponential model...")
                run_temperature_calculation(args.subject_id, args.output_dir, 
                                          args.bids_root, bvals, suffix, 
                                          args.config_file, 'monoexponential')
            
            if not biexp_exists:
                print("  Running bi-exponential model...")
                run_temperature_calculation(args.subject_id, args.output_dir, 
                                          args.bids_root, bvals, suffix, 
                                          args.config_file, 'biexponential')
        
        # Load results
        maps = load_temperature_maps(sub_out_dir, suffix)
        
        if maps['mono_temp'] is None or maps['biexp_temp'] is None:
            print(f"Missing temperature maps for {suffix}, skipping...")
            continue
        
        # Create visualization
        vis_file = os.path.join(comparison_dir, f'model_comparison_{suffix}.png')
        create_comparison_visualization(maps, vis_file, args.subject_id, suffix)
        
        # Collect statistics
        if maps['csf_mask'] is not None:
            mask = maps['csf_mask'] > 0
            mono_vals = maps['mono_temp'][mask]
            biexp_vals = maps['biexp_temp'][mask]
            valid = (mono_vals > 25) & (mono_vals < 50) & (biexp_vals > 25) & (biexp_vals < 50)
            
            if np.sum(valid) > 0:
                stats_dict = {
                    'subject_id': args.subject_id,
                    'analysis': suffix,
                    'mono_mean': np.mean(mono_vals[valid]),
                    'mono_std': np.std(mono_vals[valid]),
                    'biexp_mean': np.mean(biexp_vals[valid]),
                    'biexp_std': np.std(biexp_vals[valid]),
                    'mean_difference': np.mean(biexp_vals[valid] - mono_vals[valid]),
                    'std_difference': np.std(biexp_vals[valid] - mono_vals[valid]),
                    'correlation': np.corrcoef(mono_vals[valid], biexp_vals[valid])[0, 1]
                }
                
                if maps['model_used'] is not None:
                    model_vals = maps['model_used'][mask][valid]
                    stats_dict['biexp_model_fraction'] = np.sum(model_vals == 2) / len(model_vals)
                
                all_stats.append(stats_dict)
    
    # Save comparison statistics
    if all_stats:
        stats_df = pd.DataFrame(all_stats)
        stats_file = os.path.join(comparison_dir, 'model_comparison_statistics.csv')
        stats_df.to_csv(stats_file, index=False)
        print(f"\nSaved statistics to: {stats_file}")
    
    print("\n=== Model comparison complete! ===")

if __name__ == "__main__":
    main()