#!/usr/bin/env python3
import os, sys, argparse, glob, numpy as np, pandas as pd, matplotlib.pyplot as plt
import seaborn as sns, json
from scipy import stats
from matplotlib.gridspec import GridSpec

def main():
    parser = argparse.ArgumentParser(description="Generate comprehensive analysis report.")
    parser.add_argument("subject_id")
    parser.add_argument("output_dir")
    args = parser.parse_args()

    sub_out_dir = os.path.join(args.output_dir, args.subject_id)
    report_dir = os.path.join(sub_out_dir, 'comprehensive_report')
    os.makedirs(report_dir, exist_ok=True)
    
    print(f"=== Generating Comprehensive Analysis for Subject: {args.subject_id} ===")
    
    # Load all statistics
    stats_files = glob.glob(os.path.join(sub_out_dir, 'temperature_stats_*.csv'))
    if not stats_files:
        print("ERROR: No statistics files found!")
        sys.exit(1)
    
    # Combine all statistics
    all_stats = []
    for f in stats_files:
        df = pd.read_csv(f)
        all_stats.append(df)
    
    combined_stats = pd.concat(all_stats, ignore_index=True)
    combined_stats['max_b_value'] = combined_stats['b_values'].apply(
        lambda x: max(map(int, x.split('_')))
    )
    
    # Create comprehensive figure
    fig = plt.figure(figsize=(24, 16))
    gs = GridSpec(4, 3, figure=fig, hspace=1.5, wspace=1)
    
    # 1. Temperature vs B-value
    ax1 = fig.add_subplot(gs[0, :2])
    unique_b_max = combined_stats['max_b_value'].unique()
    for b_max in sorted(unique_b_max):
        subset = combined_stats[combined_stats['max_b_value'] == b_max]
        ax1.scatter(subset['num_b_values'], subset['temp_mean_C'], 
                   label=f'Max b={b_max}', s=100, alpha=0.7)
    ax1.set_xlabel('Number of B-values Used')
    ax1.set_ylabel('Mean Temperature (°C)')
    ax1.set_title('Temperature Dependence on B-value Selection')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. ADC statistics
    ax2 = fig.add_subplot(gs[0, 2])
    ax2.scatter(combined_stats['adc_mean']*1000, combined_stats['temp_mean_C'])
    ax2.set_xlabel('Mean ADC (×10⁻³ mm²/s)')
    ax2.set_ylabel('Mean Temperature (°C)')
    ax2.set_title('Temperature vs ADC')
    ax2.grid(True, alpha=0.3)
    
    # 3. Temperature variability
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.bar(range(len(combined_stats)), combined_stats['temp_std_C'])
    ax3.set_xlabel('Analysis Index')
    ax3.set_ylabel('Temperature Std Dev (°C)')
    ax3.set_title('Temperature Variability')
    ax3.set_xticks(range(len(combined_stats)))
    ax3.set_xticklabels(combined_stats['analysis'], rotation=45, ha='right')
    
    # 4. CSF volume consistency
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.plot(combined_stats['csf_volume_ml'], 'o-')
    ax4.set_xlabel('Analysis Index')
    ax4.set_ylabel('CSF Volume (mL)')
    ax4.set_title('CSF Segmentation Consistency')
    ax4.set_xticks(range(len(combined_stats)))
    ax4.set_xticklabels(combined_stats['analysis'], rotation=45, ha='right')
    
    # 5. Quality control metrics
    ax5 = fig.add_subplot(gs[1, 2])
    quality_data = combined_stats[['temp_physiological_fraction', 'analysis']].copy()
    quality_data['physiological_pct'] = quality_data['temp_physiological_fraction'] * 100
    ax5.barh(quality_data['analysis'], quality_data['physiological_pct'])
    ax5.set_xlabel('Physiological Temperature Fraction (%)')
    ax5.set_title('Data Quality by Analysis')
    ax5.axvline(90, color='green', linestyle='--', alpha=0.5, label='90% threshold')
    
    # 6. Temperature distributions comparison
    ax6 = fig.add_subplot(gs[2, :])
    positions = []
    data_to_plot = []
    labels = []
    
    for i, (_, row) in enumerate(combined_stats.iterrows()):
        values_file = os.path.join(sub_out_dir, f'temperature_values_{row["analysis"]}.txt')
        if os.path.exists(values_file):
            temps = np.loadtxt(values_file)
            data_to_plot.append(temps)
            labels.append(row['analysis'])
            positions.append(i)
    
    if data_to_plot:
        parts = ax6.violinplot(data_to_plot, positions=positions, showmeans=True, showmedians=True)
        ax6.set_xticks(positions)
        ax6.set_xticklabels(labels, rotation=45, ha='right')
        ax6.set_ylabel('Temperature (°C)')
        ax6.set_title('Temperature Distributions - Violin Plots')
        ax6.grid(True, axis='y', alpha=0.3)
    
    # 7. ADC outliers analysis
    ax7 = fig.add_subplot(gs[3, 0])
    combined_stats['total_outliers'] = combined_stats['adc_outliers_low'] + combined_stats['adc_outliers_high']
    ax7.bar(range(len(combined_stats)), combined_stats['adc_outliers_low'], label='Low ADC')
    ax7.bar(range(len(combined_stats)), combined_stats['adc_outliers_high'], 
            bottom=combined_stats['adc_outliers_low'], label='High ADC')
    ax7.set_xlabel('Analysis Index')
    ax7.set_ylabel('Number of Outlier Voxels')
    ax7.set_title('ADC Outliers')
    ax7.set_xticks(range(len(combined_stats)))
    ax7.set_xticklabels(combined_stats['analysis'], rotation=45, ha='right')
    ax7.legend()
    
    # 8. Summary statistics table
    ax8 = fig.add_subplot(gs[3, 1:])
    ax8.axis('tight')
    ax8.axis('off')
    
    # Create summary table
    summary_data = combined_stats[['analysis', 'temp_mean_C', 'temp_std_C', 
                                   'csf_volume_ml', 'temp_physiological_fraction']].copy()
    summary_data['temp_mean_C'] = summary_data['temp_mean_C'].round(2)
    summary_data['temp_std_C'] = summary_data['temp_std_C'].round(2)
    summary_data['csf_volume_ml'] = summary_data['csf_volume_ml'].round(1)
    summary_data['temp_physiological_fraction'] = (summary_data['temp_physiological_fraction'] * 100).round(1)
    
    table = ax8.table(cellText=summary_data.values,
                     colLabels=['Analysis', 'Mean T (°C)', 'Std T (°C)', 'CSF Vol (mL)', 'Phys. Frac (%)'],
                     cellLoc='center',
                     loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.2, 1.5)
    ax8.set_title('Summary Statistics', pad=20)
    
    plt.suptitle(f'Comprehensive Temperature Analysis Report - {args.subject_id}', fontsize=16)
    plt.tight_layout()
    
    # Save comprehensive plot
    comprehensive_plot_path = os.path.join(report_dir, 'comprehensive_analysis.png')
    plt.savefig(comprehensive_plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved comprehensive analysis plot to: {comprehensive_plot_path}")
    
    # Save combined statistics
    stats_output_path = os.path.join(report_dir, 'all_statistics_combined.csv')
    combined_stats.to_csv(stats_output_path, index=False)
    print(f"Saved combined statistics to: {stats_output_path}")
    
    # Generate HTML report
    print("Generating HTML report...")
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>CSF Temperature Analysis Report - {args.subject_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .warning {{ color: orange; }}
        .error {{ color: red; }}
        .good {{ color: green; }}
        img {{ max-width: 100%; height: auto; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>CSF Temperature Analysis Report</h1>
    <h2>Subject: {args.subject_id}</h2>
    <h3>Analysis Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</h3>
    
    <h2>Summary</h2>
    <p>Analyzed {len(combined_stats)} different b-value combinations for CSF temperature estimation.</p>
    
    <h2>Key Findings</h2>
    <ul>
        <li>Mean temperature across all analyses: {combined_stats['temp_mean_C'].mean():.2f} ± {combined_stats['temp_mean_C'].std():.2f} °C</li>
        <li>Most consistent result (lowest std): {combined_stats.loc[combined_stats['temp_std_C'].idxmin(), 'analysis']} 
            with std = {combined_stats['temp_std_C'].min():.2f} °C</li>
        <li>Highest physiological fraction: {combined_stats.loc[combined_stats['temp_physiological_fraction'].idxmax(), 'analysis']} 
            with {combined_stats['temp_physiological_fraction'].max()*100:.1f}%</li>
    </ul>
    
    <h2>Comprehensive Analysis</h2>
    <img src="comprehensive_analysis.png" alt="Comprehensive Analysis">
    
    <h2>Quality Control Summary</h2>
    <p>Analyses with potential issues:</p>
    <ul>
"""
    
    # Add warnings for problematic analyses
    for _, row in combined_stats.iterrows():
        warnings = []
        if row['temp_physiological_fraction'] < 0.8:
            warnings.append(f"Low physiological fraction: {row['temp_physiological_fraction']*100:.1f}%")
        if row['total_outliers'] > 100:
            warnings.append(f"High number of ADC outliers: {row['total_outliers']}")
        if row['temp_std_C'] > 5:
            warnings.append(f"High temperature variability: {row['temp_std_C']:.2f} °C")
        
        if warnings:
            html_content += f"        <li><span class='warning'>{row['analysis']}</span>: {'; '.join(warnings)}</li>\n"
    
    html_content += """
    </ul>
    
    <h2>Detailed Statistics</h2>
    <p>See <a href="all_statistics_combined.csv">all_statistics_combined.csv</a> for complete data.</p>
    
    <h2>Individual Histograms</h2>
    <p>Individual temperature distribution plots are available in the histograms directory.</p>
    
</body>
</html>
"""
    
    html_path = os.path.join(report_dir, 'report.html')
    with open(html_path, 'w') as f:
        f.write(html_content)
    print(f"Saved HTML report to: {html_path}")
    
    print("\n=== Comprehensive analysis complete! ===")

if __name__ == "__main__":
    main()
