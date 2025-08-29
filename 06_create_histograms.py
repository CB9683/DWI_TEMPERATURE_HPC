#!/usr/bin/env python3
import os, sys, argparse, glob, numpy as np, nibabel as nib, matplotlib.pyplot as plt
import seaborn as sns, subprocess, json, pandas as pd
from matplotlib.gridspec import GridSpec

def run_mrconvert(input_path, output_path):
    subprocess.run(['mrconvert', input_path, output_path, '-force', '-quiet'], check=True)
    return nib.load(output_path)

def main():
    parser = argparse.ArgumentParser(description="Generate enhanced histograms for temperature analysis.")
    parser.add_argument("subject_id")
    parser.add_argument("output_dir")
    args = parser.parse_args()

    sub_out_dir = os.path.join(args.output_dir, args.subject_id)
    histogram_dir = os.path.join(sub_out_dir, 'histograms')
    os.makedirs(histogram_dir, exist_ok=True)
    
    # Load configuration
    config_path = os.path.join(args.output_dir, 'pipeline_config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    sns.set_style("whitegrid")
    
    print(f"=== Generating Enhanced Histograms for Subject: {args.subject_id} ===")
    
    # Find all temperature maps
    search_pattern = os.path.join(sub_out_dir, 'temperature_map_*.mif')
    temp_map_files = sorted(glob.glob(search_pattern))
    
    if not temp_map_files:
        print(f"!!! ERROR: No temperature maps found matching pattern: {search_pattern}")
        sys.exit(1)
    
    print(f"Found {len(temp_map_files)} analysis runs to plot.")
    
    # Load all statistics for comparison
    all_stats = []
    for stats_file in glob.glob(os.path.join(sub_out_dir, 'temperature_stats_*.csv')):
        df = pd.read_csv(stats_file)
        all_stats.append(df.iloc[0].to_dict())
    
    # Dictionary to store temperature values for comparison
    all_temps = {}
    
    # Create individual histograms
    for temp_map_path in temp_map_files:
        try:
            suffix = os.path.basename(temp_map_path).replace('temperature_map_', '').replace('.mif', '')
            print(f"\n--- Creating individual plot for analysis: {suffix} ---")
            
            csf_mask_path = os.path.join(sub_out_dir, f'csf_mask_cleaned_{suffix}.mif')
            if not os.path.exists(csf_mask_path):
                print(f"!!! WARNING: CSF mask not found, skipping: {csf_mask_path}")
                continue

            tmp_dir = os.path.join(sub_out_dir, f'tmp_{suffix}')
            os.makedirs(tmp_dir, exist_ok=True)
            
            # Convert to NIfTI
            temp_nii_path = os.path.join(tmp_dir, 'temp_map.nii.gz')
            temp_data = run_mrconvert(temp_map_path, temp_nii_path).get_fdata()
            mask_nii_path = os.path.join(tmp_dir, 'csf_mask.nii.gz')
            mask_data = run_mrconvert(csf_mask_path, mask_nii_path).get_fdata()

            plausible_temps = temp_data[(mask_data > 0) & np.isfinite(temp_data) & (temp_data > 0)]
            
            if plausible_temps.size == 0:
                print("!!! WARNING: No plausible temperature values found. Skipping plot.")
                continue
            
            # Store temperatures for comparison plot
            all_temps[suffix] = plausible_temps

            # Create enhanced histogram
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), gridspec_kw={'height_ratios': [3, 1]})
            
            # Main histogram
            counts, bins, _ = ax1.hist(plausible_temps, bins=50, alpha=0.7, color='steelblue', 
                                       edgecolor='black', density=True)
            
            # Add KDE
            from scipy import stats
            kde = stats.gaussian_kde(plausible_temps)
            x_range = np.linspace(plausible_temps.min(), plausible_temps.max(), 200)
            ax1.plot(x_range, kde(x_range), 'r-', linewidth=2, label='KDE')
            
            # Add statistics
            mean_temp = np.mean(plausible_temps)
            median_temp = np.median(plausible_temps)
            std_temp = np.std(plausible_temps)
            
            ax1.axvline(mean_temp, color='green', linestyle='--', linewidth=2, 
                       label=f'Mean: {mean_temp:.1f}°C')
            ax1.axvline(median_temp, color='orange', linestyle='--', linewidth=2, 
                       label=f'Median: {median_temp:.1f}°C')
            
            # Add shaded regions for physiological range
            ax1.axvspan(30, 42, alpha=0.2, color='green', label='Physiological range')
            
            ax1.set_xlabel('Temperature (°C)', fontsize=12)
            ax1.set_ylabel('Density', fontsize=12)
            ax1.set_title(f'Temperature Distribution - {args.subject_id}\nAnalysis: {suffix}', fontsize=14)
            ax1.legend(loc='upper right')
            ax1.set_xlim(20, 50)
            
            # Box plot below
            ax2.boxplot(plausible_temps, vert=False, widths=0.7, patch_artist=True,
                       boxprops=dict(facecolor='lightblue'),
                       medianprops=dict(color='red', linewidth=2))
            ax2.set_xlabel('Temperature (°C)', fontsize=12)
            ax2.set_xlim(20, 50)
            ax2.set_yticks([])
            
            plt.tight_layout()
            output_plot_path = os.path.join(histogram_dir, f'histogram_{suffix}.png')
            plt.savefig(output_plot_path, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"Saved histogram to: {output_plot_path}")
            
        except Exception as e:
            print(f"!!! ERROR processing file {temp_map_path}: {e}")
            import traceback
            traceback.print_exc()

    # Create comparison plot if multiple analyses exist
    if len(temp_map_files) > 1:
        print("\n--- Creating comparison plot across all b-value combinations ---")
        
        # Adjusted figure size for vertical layout
        fig = plt.figure(figsize=(12, 18)) 
        # Changed GridSpec to 3 rows, 1 column; adjusted hspace
        gs = GridSpec(3, 1, figure=fig, hspace=0.4, wspace=0.3) 
        
        # Plot 1: Overlaid distributions (top plot)
        ax1 = fig.add_subplot(gs[0, 0])
        for suffix, temps in all_temps.items(): # Using 'all_temps' as defined in your original snippet
            ax1.hist(temps, bins=30, alpha=0.3, density=True, label=suffix)
        ax1.set_xlabel('Temperature (°C)')
        ax1.set_ylabel('Density')
        ax1.set_title('Temperature Distributions - All B-value Combinations')
        ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        
        # Plot 2: Box plots comparison (middle plot)
        ax2 = fig.add_subplot(gs[1, 0])
        data_for_box = [temps for temps in all_temps.values()] # Using 'all_temps'
        labels_for_box = list(all_temps.keys())
        bp = ax2.boxplot(data_for_box, labels=labels_for_box, patch_artist=True)
        for patch in bp['boxes']:
            patch.set_facecolor('lightblue')
        ax2.set_ylabel('Temperature (°C)')
        ax2.set_title('Temperature Ranges by B-value Combination')
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Plot 3: Mean temperature trends (bottom plot)
        if all_stats: # This check ensures this plot is only made if stats are available
            ax3 = fig.add_subplot(gs[2, 0])
            df_stats = pd.DataFrame(all_stats)
            df_stats['num_b_values'] = df_stats['num_b_values'].astype(int)
            df_sorted = df_stats.sort_values('num_b_values')
            
            ax3.plot(df_sorted['num_b_values'], df_sorted['temp_mean_C'], 'o-', markersize=8)
            ax3.errorbar(df_sorted['num_b_values'], df_sorted['temp_mean_C'], 
                        yerr=df_sorted['temp_std_C'], fmt='none', capsize=5)
            ax3.set_xlabel('Number of B-values')
            ax3.set_ylabel('Mean Temperature (°C)')
            ax3.set_title('Mean Temperature vs Number of B-values')
            ax3.grid(True, alpha=0.3)
            ax3.set_xticks(sorted(df_sorted['num_b_values'].unique())) # Set specific ticks for clarity

        plt.tight_layout() # This is crucial for good spacing
        comparison_path = os.path.join(histogram_dir, 'comparison_all_analyses_improved.png')
        plt.savefig(comparison_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Saved improved comparison plot to: {comparison_path}")
    
    print("\n=== All histograms generated successfully! ===")

if __name__ == "__main__":
    main()