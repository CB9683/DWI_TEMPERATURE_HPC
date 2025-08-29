#!/usr/bin/env python3
"""
Pipeline Setup Validation Script
Checks that all requirements are met before running the pipeline
"""

import os
import json
import sys
from pathlib import Path
import subprocess

def check_file_exists(path, name):
    """Check if file exists and report status"""
    if os.path.exists(path):
        print(f"✅ {name}: {path}")
        return True
    else:
        print(f"❌ {name}: {path} (NOT FOUND)")
        return False

def check_command_available(cmd, name):
    """Check if command is available"""
    try:
        result = subprocess.run(['which', cmd], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {name}: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ {name}: command '{cmd}' not found")
            return False
    except:
        print(f"❌ {name}: command '{cmd}' not available")
        return False

def main():
    print("=== DWI Temperature Pipeline Setup Validation ===\n")
    
    all_good = True
    
    # Check configuration file
    print("1. Configuration File:")
    config_file = "pipeline_config.json"
    if not check_file_exists(config_file, "Configuration"):
        all_good = False
        print("   Create pipeline_config.json with your settings")
    else:
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Check subjects
            subjects = config.get('subjects', [])
            if not subjects:
                print("❌ No subjects specified in configuration")
                all_good = False
            else:
                print(f"✅ Subjects configured: {subjects}")
            
            # Check paths
            paths = config.get('paths', {})
            required_paths = ['bids_root', 'base_output', 'conda_env', 'mrtrix3_bin', 'fsl_dir']
            for path_key in required_paths:
                if path_key in paths:
                    path_value = paths[path_key]
                    if os.path.exists(path_value):
                        print(f"✅ {path_key}: {path_value}")
                    else:
                        print(f"❌ {path_key}: {path_value} (NOT FOUND)")
                        all_good = False
                else:
                    print(f"❌ {path_key}: missing from configuration")
                    all_good = False
                    
        except json.JSONDecodeError:
            print("❌ Configuration file has invalid JSON format")
            all_good = False
        except Exception as e:
            print(f"❌ Error reading configuration: {e}")
            all_good = False
    
    print("\n2. Core Pipeline Scripts:")
    core_scripts = [
        "00_pipeline_manager.sh",
        "01_run_preprocessing.sh", 
        "02_preprocess_subject.py",
        "03_run_dti.sh",
        "03_fit_tensor.py",
        "04_run_bvalue_sweep.sh",
        "05_calculate_temperature.py",
        "08_generate_reports.sh",
        "09_analyze_stability.sh"
    ]
    
    for script in core_scripts:
        if not check_file_exists(script, f"Script {script}"):
            all_good = False
    
    print("\n3. Stepwise Execution Scripts:")
    stepwise_scripts = [
        "run_preprocessing_only.sh",
        "run_dti_only.sh",
        "run_analysis_only.sh", 
        "run_reports_only.sh",
        "run_stability_only.sh"
    ]
    
    for script in stepwise_scripts:
        if not check_file_exists(script, f"Script {script}"):
            all_good = False
    
    print("\n4. Required Commands:")
    commands = [
        ("python", "Python"),
        ("qsub", "PBS job submission"),
        ("qstat", "PBS job status"),
        ("conda", "Conda environment manager")
    ]
    
    for cmd, name in commands:
        if not check_command_available(cmd, name):
            all_good = False
    
    print("\n5. Conda Environment:")
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            conda_env = config.get('paths', {}).get('conda_env', '')
            if conda_env:
                if os.path.exists(conda_env):
                    print(f"✅ Conda environment path: {conda_env}")
                    
                    # Try to activate and check key packages
                    try:
                        # Check if environment has key packages
                        env_name = os.path.basename(conda_env)
                        result = subprocess.run([
                            'bash', '-c', 
                            f'source {os.path.dirname(conda_env)}/../etc/profile.d/conda.sh && conda activate {conda_env} && python -c "import numpy, nibabel, matplotlib, pandas, scipy; print(\\"Key packages available\\")"'
                        ], capture_output=True, text=True, timeout=30)
                        
                        if result.returncode == 0:
                            print("✅ Key Python packages available in conda environment")
                        else:
                            print(f"⚠️  Warning: Could not verify Python packages in conda environment")
                            print(f"   Error: {result.stderr}")
                            
                    except subprocess.TimeoutExpired:
                        print("⚠️  Warning: Conda environment check timed out")
                    except Exception as e:
                        print(f"⚠️  Warning: Could not check conda environment: {e}")
                else:
                    print(f"❌ Conda environment not found: {conda_env}")
                    all_good = False
        except:
            pass
    
    print("\n6. BIDS Data Validation:")
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            bids_root = config.get('paths', {}).get('bids_root', '')
            subjects = config.get('subjects', [])
            
            if bids_root and subjects:
                print(f"Checking BIDS data in: {bids_root}")
                for subject in subjects:
                    print(f"\n  Subject: {subject}")
                    
                    # Expected DWI files
                    dwi_files = [
                        f"{bids_root}/{subject}/ses-02/dwi/{subject}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.nii.gz",
                        f"{bids_root}/{subject}/ses-02/dwi/{subject}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.bvec",
                        f"{bids_root}/{subject}/ses-02/dwi/{subject}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.bval",
                        f"{bids_root}/{subject}/ses-02/dwi/{subject}_ses-02_acq-CHARMED_dir-PA_part-mag_dwi.nii.gz",
                        f"{bids_root}/{subject}/ses-02/dwi/{subject}_ses-02_acq-CHARMED_dir-PA_part-mag_dwi.bvec",
                        f"{bids_root}/{subject}/ses-02/dwi/{subject}_ses-02_acq-CHARMED_dir-PA_part-mag_dwi.bval"
                    ]
                    
                    subject_ok = True
                    for dwi_file in dwi_files:
                        if os.path.exists(dwi_file):
                            print(f"    ✅ {os.path.basename(dwi_file)}")
                        else:
                            print(f"    ❌ {os.path.basename(dwi_file)} (NOT FOUND)")
                            subject_ok = False
                            all_good = False
                    
                    if subject_ok:
                        print(f"    ✅ All required files found for {subject}")
            else:
                print("Cannot validate BIDS data - missing configuration")
        except Exception as e:
            print(f"Error validating BIDS data: {e}")
    
    print(f"\n{'='*50}")
    if all_good:
        print("🎉 VALIDATION PASSED - Pipeline is ready to run!")
        print("\nNext steps:")
        print("1. Full pipeline: bash 00_pipeline_manager.sh")
        print("2. Stepwise: bash run_preprocessing_only.sh")
    else:
        print("❌ VALIDATION FAILED - Please fix the issues above")
        print("\nCommon solutions:")
        print("- Update paths in pipeline_config.json")
        print("- Activate conda environment: conda activate dwi_temperature") 
        print("- Check BIDS data organization")
        print("- Ensure all pipeline scripts are present")
    
    return 0 if all_good else 1

if __name__ == "__main__":
    sys.exit(main())