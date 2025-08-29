# DWI Temperature Pipeline - Quick Reference

## 🚀 Quick Start

### Full Pipeline (Automated)
```bash
# Activate environment
conda activate dwi_temperature

# Run full pipeline
bash 00_pipeline_manager.sh

# Run with bi-exponential model
# Edit pipeline_config.json: "temperature_model": "biexponential"
bash 00_pipeline_manager.sh

# Skip preprocessing (use existing output)
bash 00_pipeline_manager.sh --skip-preprocessing --output-dir /path/to/existing/output
```

### Stepwise Execution (For Testing)
```bash
# Step 1: Preprocessing only
bash run_preprocessing_only.sh

# Step 2a: DTI analysis (if using bi-exponential model)
bash run_dti_only.sh        # Auto-detects latest output dir

# Step 2b: Temperature analysis  
bash run_analysis_only.sh   # Auto-detects latest output dir

# Step 3: Generate reports
bash run_reports_only.sh    # Auto-detects latest output dir

# Step 4: Stability analysis (optional)
bash run_stability_only.sh  # Auto-detects latest output dir

# Or manually specify directory:
bash run_analysis_only.sh /path/to/specific/output/dir
```

## 📁 Key Files
- **Config**: `pipeline_config.json`
- **Main script**: `00_pipeline_manager.sh`
- **Temperature calc**: `05_calculate_temperature.py`
- **DTI/FA analysis**: `03_fit_tensor.py`
- **Output tracker**: `get_latest_output.py`

## 🔧 Output Directory Helper
```bash
# Find latest pipeline output
python3 get_latest_output.py

# List all pipeline outputs
python3 get_latest_output.py --list

# Use in scripts
OUTPUT_DIR=$(python3 get_latest_output.py)
echo "Latest: $OUTPUT_DIR"
```

## 🔧 Model Selection
```json
// In pipeline_config.json
"temperature_model": "monoexponential"  // Original
"temperature_model": "biexponential"    // New, addresses partial volume
```

## 📊 Key Parameters (Bi-exponential)
- **D_free bounds**: [2.0e-3, 4.0e-3] mm²/s
- **D_tissue bounds**: [0.1e-3, 1.5e-3] mm²/s
- **FA range**: [0.0, 0.4] for fitting
- **R² threshold**: 0.7 (fallback if below)

## 🔍 Check Results
```bash
# View temperature statistics
cat derivatives/sub-*/temperature_stats_*.csv

# View DTI metrics
cat derivatives/sub-*/dti/dti_stats.csv

# Check logs for errors
tail -f logs/*.out
```

## 🔄 Version Control
```bash
# Current branch
git branch

# Switch to original
git checkout v1.0-monoexponential

# Switch to bi-exponential
git checkout develop-biexponential

# Push changes
git push origin develop-biexponential
```

## ⚠️ Important Notes
1. **FA is for validation**, not constraint
2. **D_free** varies with temperature (that's what we measure!)
3. **Fallback**: Auto-switches to mono-exponential if bi-exp fails
4. **Backup**: Located at `../dwi-temperature_updated_backup_*`

## 🔧 Stepwise Execution Guide

### Prerequisites
1. **Validate setup**: Run `python validate_setup.py` to check everything
2. **Set up subjects**: Edit `pipeline_config.json` to include your subject(s)
3. **Environment**: Make sure `conda activate dwi_temperature` is active
4. **BIDS data**: Ensure DWI data is in correct BIDS format

### Typical Workflow
```bash
# 1. Start with preprocessing
bash run_preprocessing_only.sh
# Monitor: qstat -u $USER
# Check: tail -f logs/01_preproc.out

# 2. Following steps auto-detect the output directory:
# (No need to extract directory path manually!)

# 3a. If using bi-exponential model, run DTI first:
bash run_dti_only.sh
# Check: tail -f logs/03_dti.out

# 3b. Run temperature analysis:
bash run_analysis_only.sh
# Monitor: qstat -u $USER  
# Check: tail -f logs/04_bvalue_sweep.out

# 4. Generate reports:
bash run_reports_only.sh
# Check: tail -f logs/08_reports.out

# 5. Optional - stability analysis:
bash run_stability_only.sh
# Check: tail -f logs/09_stability_analysis.out

# Helper: List all available output directories
python3 get_latest_output.py --list
```

### Verification Between Steps
```bash
# After preprocessing - check required files:
ls $OUTPUT_DIR/sub-*/dwi_preproc_unbiased.mif
ls $OUTPUT_DIR/sub-*/csf_norm.mif
ls $OUTPUT_DIR/sub-*/dwi_mask_upsampled.mif

# After DTI - check FA maps (if bi-exponential):
ls $OUTPUT_DIR/sub-*/dti/fa.mif

# After analysis - check temperature maps:
ls $OUTPUT_DIR/sub-*/temperature_map_*.mif

# After reports - check final outputs:
ls $OUTPUT_DIR/sub-*/comprehensive_report/report.html
```

## 🐛 Debug Commands
```bash
# Validate setup before starting
python validate_setup.py

# Check pipeline status (after starting)
python pipeline_state.py /path/to/output --status

# Test single subject manually
python 05_calculate_temperature.py sub-01187 ./output /path/to/bids \
    --bvals_for_adc 0 200 --output_suffix b0_200 --config_file pipeline_config.json

# Check if DTI ran
ls derivatives/sub-*/dti/fa.mif

# View FA visualization
display derivatives/sub-*/dti/fa_visualization.png

# Monitor all jobs
watch -n 5 'qstat -u $USER'

# Check logs for errors
grep -i error logs/*.out logs/*.err

# Validate stage requirements
python pipeline_state.py /path/to/output --validate temperature_analysis sub-01187
```

## 📈 Temperature Formula
```
T(°C) = (A / (B + ln(D))) - 273.15

Where:
- A = 2256.74
- B = 4.39221
- D = D_free (from bi-exponential) or ADC (from mono-exponential)
```