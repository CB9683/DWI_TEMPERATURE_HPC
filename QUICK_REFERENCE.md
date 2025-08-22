# DWI Temperature Pipeline - Quick Reference

## 🚀 Quick Start
```bash
# Activate environment
conda activate mrtrix_full

# Run full pipeline
bash 00_pipeline_manager.sh

# Run with bi-exponential model
# Edit pipeline_config.json: "temperature_model": "biexponential"
bash 00_pipeline_manager.sh
```

## 📁 Key Files
- **Config**: `pipeline_config.json`
- **Main script**: `00_pipeline_manager.sh`
- **Temperature calc**: `04_calculate_temperature.py`
- **DTI/FA analysis**: `05_fit_tensor.py`

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

## 🐛 Debug Commands
```bash
# Test single subject
python 04_calculate_temperature.py sub-01187 ./output /path/to/bids \
    --bvals_for_adc 0 200 --output_suffix b0_200 --config_file pipeline_config.json

# Check if DTI ran
ls derivatives/sub-*/dti/fa.mif

# View FA visualization
display derivatives/sub-*/dti/fa_visualization.png
```

## 📈 Temperature Formula
```
T(°C) = (A / (B + ln(D))) - 273.15

Where:
- A = 2256.74
- B = 4.39221
- D = D_free (from bi-exponential) or ADC (from mono-exponential)
```