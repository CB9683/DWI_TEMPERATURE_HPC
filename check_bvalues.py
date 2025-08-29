#!/usr/bin/env python3
"""
Check what b-values are available in the BIDS data
"""
import numpy as np
import json
import os
import sys

def main():
    # Load configuration
    config_file = "pipeline_config.json"
    if not os.path.exists(config_file):
        print("ERROR: pipeline_config.json not found")
        sys.exit(1)
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    bids_root = config['paths']['bids_root']
    subjects = config['subjects']
    
    print("=== B-VALUE ANALYSIS ===")
    print(f"BIDS root: {bids_root}")
    print(f"Subjects: {subjects}")
    print()
    
    for subject in subjects:
        print(f"Subject: {subject}")
        
        # Path to b-value file
        bval_file = os.path.join(bids_root, subject, 'ses-02', 'dwi',
                                f'{subject}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.bval')
        
        if os.path.exists(bval_file):
            print(f"  B-value file: {bval_file}")
            
            # Load b-values
            bvals = np.loadtxt(bval_file)
            unique_bvals = np.unique(bvals)
            
            print(f"  Total volumes: {len(bvals)}")
            print(f"  Unique b-values: {unique_bvals}")
            print(f"  B-value distribution:")
            
            for bval in unique_bvals:
                count = np.sum(np.isclose(bvals, bval, atol=20))
                print(f"    b={bval:4.0f}: {count:3d} volumes")
            
            print(f"  Full b-value array (first 20): {bvals[:20]}")
            if len(bvals) > 20:
                print(f"  ... and {len(bvals)-20} more volumes")
                
        else:
            print(f"  ERROR: B-value file not found: {bval_file}")
        
        print()
    
    # Show what DTI uses vs temperature analysis
    print("=== USAGE COMPARISON ===")
    print("DTI tensor fitting (03_fit_tensor.py):")
    print("  - Uses: ALL b-values from dwi_upsampled.mif")
    print("  - Command: dwi2tensor dwi_upsampled.mif dt.mif")
    print("  - Purpose: Fit diffusion tensor across full b-value range")
    print()
    
    print("Temperature analysis (05_calculate_temperature.py):")
    bvalue_sets = config.get('bvalue_sets', [])
    print(f"  - Uses: Selected b-value subsets from config")
    print(f"  - Current config sets: {bvalue_sets}")
    print("  - Purpose: Calculate temperature from specific b-value combinations")
    print()
    
    print("=== IMPLICATIONS ===")
    print("1. DTI tensor fitting uses the FULL b-value range for optimal tensor estimation")
    print("2. Temperature analysis uses SPECIFIC b-value subsets defined in config")
    print("3. For bi-exponential model: DTI provides FA maps for validation/analysis")
    print("4. FA maps reflect tissue microstructure from all available diffusion data")

if __name__ == "__main__":
    main()