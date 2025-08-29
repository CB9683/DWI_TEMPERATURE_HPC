# DWI Temperature Estimation Pipeline

This repository contains a comprehensive, automated pipeline for estimating brain temperature from diffusion-weighted imaging (DWI) data, with a focus on cerebrospinal fluid (CSF). The pipeline leverages MRtrix3, FSL, and custom Python scripts for preprocessing, analysis, and quality control reporting.

## 🆕 Version 2.0: Bi-exponential Diffusion Model
The pipeline now includes an advanced **bi-exponential diffusion model** to address partial volume effects in CSF regions. This enhancement separates free water diffusion from tissue-contaminated signals, providing more accurate temperature estimates.

**Key Innovation**: Addresses the fundamental issue where CSF voxels contain both free water and tissue contamination, leading to biased temperature measurements in traditional monoexponential approaches.

## 🚀 Quick Start
```bash
# Activate environment
conda activate dwi_temperature

# Full automated pipeline
bash 00_pipeline_manager.sh

# Stepwise execution (recommended for testing)
bash run_preprocessing_only.sh
bash run_dti_only.sh           # Auto-detects latest output
bash run_analysis_only.sh      # Auto-detects latest output  
bash run_reports_only.sh       # Auto-detects latest output
```

## Key Features

### 🔬 **Advanced Temperature Modeling**
- **Bi-exponential diffusion model**: Separates free water from tissue contamination
- **Automatic model selection**: Falls back to monoexponential if bi-exponential fails
- **DTI integration**: Uses fractional anisotropy (FA) for validation and tissue characterization

### 🔧 **Automated Workflow**
- **Single command execution**: Complete pipeline from BIDS data to final reports
- **Stepwise execution**: Individual stages for testing and debugging
- **Automatic output tracking**: No manual directory management required
- **Smart job dependencies**: PBS scheduling with proper dependency chains

### 📊 **Robust Analysis Pipeline**
- **State-of-the-art preprocessing**: Denoising, distortion correction, bias field correction
- **Multi-shell analysis**: MSMT-CSD with dhollander algorithm
- **Flexible b-value testing**: Multiple b-value combinations for stability assessment
- **Comprehensive quality control**: Detailed metrics and visualizations

### 📈 **Comprehensive Reporting**
- **HTML reports**: Interactive visualizations and statistical summaries
- **Model comparisons**: Side-by-side mono vs bi-exponential results
- **Quality metrics**: Fitting quality, parameter distributions, stability analysis

## Pipeline Architecture

### Core Scripts (Logical Numbering)
1. **00_pipeline_manager.sh** - Main orchestration script
2. **01_run_preprocessing.sh + 02_preprocess_subject.py** - DWI preprocessing
3. **03_run_dti.sh + 03_fit_tensor.py** - DTI analysis (for bi-exponential model)
4. **04_run_bvalue_sweep.sh + 05_calculate_temperature.py** - Temperature estimation
5. **08_generate_reports.sh + 06_comprehensive_analysis.py** - Report generation
6. **09_analyze_stability.sh** - Temperature stability analysis

### Stepwise Execution Scripts
- **run_preprocessing_only.sh** - Preprocessing stage only
- **run_dti_only.sh** - DTI analysis only (auto-detects output dir)
- **run_analysis_only.sh** - Temperature analysis only (auto-detects output dir)
- **run_reports_only.sh** - Report generation only (auto-detects output dir)
- **run_stability_only.sh** - Stability analysis only (auto-detects output dir)

### Utility Scripts
- **get_latest_output.py** - Automatically finds most recent pipeline output
- **validate_setup.py** - Validates pipeline configuration and environment
- **pipeline_state.py** - Tracks and manages pipeline execution state
- **check_bvalues.py** - Analyzes available b-values in BIDS data

## Temperature Models

### Bi-exponential Model (Recommended)
```
S(b) = S₀ × (f_free × exp(-b × D_free) + (1-f_free) × exp(-b × D_tissue))
```
- **D_free**: Free water diffusion (temperature-dependent)
- **D_tissue**: Tissue diffusion (restricted)
- **f_free**: Free water fraction

**Temperature Calculation**: T(°C) = (A / (B + ln(D_free))) - 273.15

### Monoexponential Model (Original)
```
S(b) = S₀ × exp(-b × ADC)
```
**Temperature Calculation**: T(°C) = (A / (B + ln(ADC))) - 273.15

## Configuration

The pipeline is controlled by `pipeline_config.json`:

```json
{
    "paths": {
        "bids_root": "/path/to/bids/data",
        "base_output": "/path/to/output",
        "conda_env": "/path/to/conda/envs/dwi_temperature"
    },
    "subjects": ["sub-01945"],
    "bvalue_sets": [
        [0, 200],
        [0, 1200]
    ],
    "processing": {
        "temperature_model": "biexponential",  // or "monoexponential"
        "biexponential_model": {
            "fit_dti": true,
            "fa_range_for_fitting": [0.0, 0.4],
            "d_free_bounds": [2.0e-3, 4.0e-3],
            "d_tissue_bounds": [0.1e-3, 1.5e-3],
            "initial_guess": {
                "d_free": 3.0e-3,
                "d_tissue": 0.7e-3,
                "f_free": 0.7
            }
        }
    }
}
```

## Prerequisites

### System Requirements
- **HPC Environment**: Linux-based system with PBS job scheduler
- **Memory**: 32+ GB RAM recommended for bi-exponential fitting
- **Storage**: ~10-20 GB per subject for full pipeline outputs

### Software Dependencies
```yaml
# environment.yml
name: dwi_temperature
dependencies:
  - python=3.9
  - numpy
  - scipy
  - pandas
  - nibabel
  - matplotlib
  - seaborn
```

### External Software
- **MRtrix3**: Latest version with MSMT-CSD support
- **FSL**: Version 6.0+ with eddy GPU support (recommended)
- **ANTs**: For bias field correction

### Data Requirements
- **BIDS format**: DWI data in Brain Imaging Data Structure format
- **Multi-shell**: Multiple b-values (recommended: 0, 200, 500, 1200, 2400+ s/mm²)
- **Phase encoding**: Both AP and PA directions for distortion correction

## Output Structure

```
output_directory/
├── sub-<ID>/
│   ├── dwi_preproc_unbiased.mif       # Preprocessed DWI
│   ├── dwi_upsampled.mif              # Upsampled to 1.5mm
│   ├── csf_norm.mif                   # CSF probability map
│   ├── dti/                           # DTI analysis results
│   │   ├── fa.mif                     # Fractional anisotropy
│   │   ├── dti_stats.csv              # DTI quality metrics
│   │   └── fa_visualization.png        # FA visualization
│   ├── temperature_map_*.mif          # Temperature maps (per b-value set)
│   ├── temperature_stats_*.csv        # Statistics (per analysis)
│   ├── biexponential_analysis/        # Bi-exponential parameters
│   │   ├── d_free_map.mif             # Free water diffusion
│   │   ├── f_free_map.mif             # Free water fraction
│   │   └── r_squared_map.mif          # Fitting quality
│   ├── model_comparison/              # Model comparison results
│   │   ├── temperature_difference.mif  # Bi-exp vs mono-exp
│   │   └── comparison_statistics.csv   # Statistical comparison
│   ├── histograms/                    # Individual analysis histograms
│   └── comprehensive_report/          # Final HTML report
│       ├── report.html                # Main interactive report
│       └── all_statistics_combined.csv # Aggregated statistics
├── logs/                              # Execution logs
└── pipeline_config.json               # Configuration used
```

## Usage Examples

### Standard Full Pipeline
```bash
# Configure subjects in pipeline_config.json
bash 00_pipeline_manager.sh
```

### Stepwise Testing Workflow
```bash
# 1. Preprocessing
bash run_preprocessing_only.sh

# 2. DTI analysis (if using bi-exponential)
bash run_dti_only.sh

# 3. Temperature analysis
bash run_analysis_only.sh

# 4. Generate reports
bash run_reports_only.sh

# Helper: Check latest output
python3 get_latest_output.py --list
```

### Model Comparison
```bash
# Run both models for comparison
# 1. Set "temperature_model": "biexponential" in config
bash 00_pipeline_manager.sh

# 2. Check model_comparison/ directory for results
```

## Quality Control

### Automatic Checks
- **R² thresholding**: Bi-exponential fits with R² < 0.7 fall back to monoexponential
- **Parameter bounds**: D_free and D_tissue constrained to physiological ranges
- **FA validation**: Results cross-validated against tissue microstructure

### Manual Inspection
- **FA visualization**: Check DTI quality in `dti/fa_visualization.png`
- **Temperature maps**: Inspect spatial patterns in temperature outputs
- **HTML reports**: Review comprehensive statistics and comparisons

## Scientific Background

### Temperature-Diffusion Relationship
Water diffusion coefficient varies with temperature according to:
```
T(°C) = (A / (B + ln(D))) - 273.15
```
Where A = 2256.74, B = 4.39221 (calibrated constants)

### Partial Volume Problem
In CSF voxels, signal contains:
- **Free water**: Temperature-dependent diffusion
- **Tissue contamination**: Temperature-independent restricted diffusion

**Solution**: Bi-exponential model separates these components for accurate temperature estimation.

## Troubleshooting

### Common Issues
1. **Environment errors**: Ensure `conda activate dwi_temperature`
2. **Memory issues**: Bi-exponential fitting requires substantial RAM
3. **Convergence failures**: Check b-value distribution and data quality

### Debug Commands
```bash
# Validate setup
python validate_setup.py

# Check b-values in data
python check_bvalues.py

# Monitor jobs
watch -n 5 'qstat -u $USER'

# Check logs
tail -f logs/*.out
```

## References

- Le Bihan D. (2007). The 'wet mind': water and functional neuroimaging. *Physics in Medicine & Biology*
- Tournier JD, et al. (2019). MRtrix3: A fast, flexible and open software framework for medical image processing and visualisation. *NeuroImage*
- This pipeline: Enhanced bi-exponential approach for partial volume correction

## Repository Information

- **GitHub**: https://github.com/CB9683/DWI_TEMPERATURE_HPC.git
- **Main Branch**: `main` (original monoexponential)
- **Development**: `develop-biexponential` (enhanced version)
- **Version**: 2.0-biexponential

---
*Last Updated: August 2024*  
*Pipeline Version: 2.0 (Bi-exponential Enhancement)*