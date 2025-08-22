# DWI Temperature Estimation Pipeline - Project Documentation

## Project Overview
This pipeline estimates brain temperature from diffusion-weighted imaging (DWI) data by analyzing cerebrospinal fluid (CSF). The project has been enhanced with a bi-exponential diffusion model to address partial volume effects.

## Repository Information
- **GitHub URL**: https://github.com/CB9683/DWI_TEMPERATURE_HPC.git
- **Main Branch**: `main` (original monoexponential implementation)
- **Development Branch**: `develop-biexponential` (enhanced with bi-exponential model)
- **Version Tag**: `v1.0-monoexponential` (original stable version)

## Key Problem Addressed
**Partial Volume Effects**: In CSF regions, contamination from surrounding tissue (gray/white matter) leads to:
- Reduced apparent diffusion coefficients (ADC)
- Overestimated temperatures
- Systematic bias in temperature measurements

## Solution: Bi-Exponential Diffusion Model
The enhanced pipeline implements a two-compartment model:
```
S(b) = S₀ * (f_free * exp(-b * D_free) + (1-f_free) * exp(-b * D_tissue))
```
Where:
- `f_free`: Free water fraction
- `D_free`: Free water diffusion coefficient (temperature-dependent)
- `D_tissue`: Restricted diffusion in tissue

## Environment Configuration
- **Conda Environment**: `mrtrix_full`
- **Path**: `/g/data/vp06/Christian/software/Envs/miniconda3/envs/mrtrix_full`
- **Key Dependencies**: MRtrix3, FSL, Python with scipy/numpy/nibabel

## Pipeline Architecture

### Core Scripts
1. **00_pipeline_manager.sh**: Orchestrates the entire pipeline
2. **01_run_preprocessing.sh**: Launches preprocessing
3. **02_preprocess_subject.py**: DWI preprocessing (denoising, distortion correction, etc.)
4. **03_run_bvalue_sweep.sh**: Runs temperature calculation for different b-value sets
5. **04_calculate_temperature.py**: Temperature estimation (now with bi-exponential support)
6. **05_fit_tensor.py**: NEW - DTI analysis for FA calculation
7. **06_comprehensive_analysis.py**: Aggregates results and creates reports

### Key Enhancements in v2.0 (Bi-exponential)

#### Configuration (`pipeline_config.json`)
```json
{
    "processing": {
        "temperature_model": "biexponential",  // or "monoexponential"
        "biexponential_model": {
            "fit_dti": true,
            "fa_range_for_fitting": [0.0, 0.4],
            "fa_tissue_threshold": 0.5,
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

#### Model Selection Logic
1. If `temperature_model = "biexponential"`:
   - Attempts bi-exponential fitting with constrained optimization
   - Uses D_free for temperature calculation
   - Falls back to monoexponential if R² < 0.7
2. FA is used for validation, NOT as a constraint
3. All parameters are fitted directly from the data

## Important Commands

### Running the Pipeline
```bash
# Full pipeline from scratch
bash 00_pipeline_manager.sh

# Skip preprocessing (if already done)
bash 00_pipeline_manager.sh --skip-preprocessing --output-dir /path/to/previous/output
```

### Git Operations
```bash
# Switch to original version
git checkout v1.0-monoexponential

# Switch to development branch
git checkout develop-biexponential

# Check current branch
git branch
```

### Testing Bi-exponential Model
1. Edit `pipeline_config.json`
2. Set `"temperature_model": "biexponential"`
3. Run pipeline as normal

## Quality Control Checks

### For Bi-exponential Fitting
- **R² threshold**: 0.7 (below this, falls back to monoexponential)
- **D_free bounds**: 2.0-4.0 × 10⁻³ mm²/s (physiologically plausible at body temperature)
- **FA validation**: Results stored for post-hoc analysis

### Output Files (New in Bi-exponential)
- `dti/fa.mif`: Fractional anisotropy map
- `dti/dti_stats.csv`: DTI quality metrics
- `temperature_model_comparison.csv`: When both models are run

## Troubleshooting

### Common Issues
1. **Module loading errors**: Ensure FSL and MRtrix3 paths are correct in config
2. **Fitting convergence**: Check b-value distribution (need good sampling)
3. **Memory issues**: Bi-exponential fitting is more memory-intensive

### Debugging
- Check logs in `logs/` directory
- Use `--temperature_model monoexponential` to test without bi-exponential
- FA maps help identify problematic regions

## Scientific Rationale

### Why Bi-exponential?
- CSF voxels contain both free water and tissue due to limited resolution
- Monoexponential model averages these components → biased temperature
- Bi-exponential separates components → accurate free water diffusion → better temperature

### Key Insight
**FA is NOT used to pre-estimate fractions**. Instead:
1. Fit bi-exponential model directly to DWI signal
2. Let data determine optimal water fraction
3. Use FA only for post-hoc validation

## Future Enhancements
- [ ] Implement voxel-wise model selection based on AIC/BIC
- [ ] Add bootstrap confidence intervals for temperature
- [ ] Create comparison plots between mono/bi-exponential results
- [ ] Optimize fitting for speed (parallel processing)

## References
- Le Bihan (2007): Temperature estimation from diffusion
- Original pipeline: Monoexponential ADC approach
- This enhancement: Addresses partial volume via bi-exponential model

---
Last Updated: 2025-08-22
Pipeline Version: 2.0-biexponential (development)