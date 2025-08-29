#!/usr/bin/env python3
"""Diagnose shape issues in directional fitting"""

import numpy as np
import nibabel as nib
import os

# Paths
output_dir = "/g/data/hl36/cb4095/WAND/derivatives/temp_pipeline_2025-08-27_11-27-08/sub-01945"
bids_root = "/g/data/hl36/cb4095/WAND/WAND"
subject = "sub-01945"

# Load bvecs
bvec_file = os.path.join(bids_root, subject, 'ses-02', 'dwi',
                        f'{subject}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.bvec')
bval_file = os.path.join(bids_root, subject, 'ses-02', 'dwi',
                        f'{subject}_ses-02_acq-CHARMED_dir-AP_part-mag_dwi.bval')

print("Loading b-values and b-vectors...")
bvals = np.loadtxt(bval_file)
bvecs = np.loadtxt(bvec_file)

print(f"bvals shape: {bvals.shape}")
print(f"bvecs shape: {bvecs.shape}")
print(f"First 5 b-values: {bvals[:5]}")

# Select indices for b=0 and b=1200
bvalue_tolerance = 20
indices_b0_1200 = [i for i, b in enumerate(bvals) 
                   if np.isclose(b, 0, atol=bvalue_tolerance) or 
                      np.isclose(b, 1200, atol=bvalue_tolerance)]

print(f"\nSelected {len(indices_b0_1200)} volumes for b=0 and b=1200")
print(f"Indices: {indices_b0_1200[:10]}...")

# Extract gradient directions
if bvecs.shape[0] == 3:
    gradient_dirs = bvecs[:, indices_b0_1200].T
else:
    gradient_dirs = bvecs[indices_b0_1200, :]

print(f"\nGradient directions shape: {gradient_dirs.shape}")
print(f"First gradient direction: {gradient_dirs[0]}")
print(f"Gradient direction type: {type(gradient_dirs[0])}")

# Load DTI metrics
dti_dir = os.path.join(output_dir, 'dti')
if os.path.exists(os.path.join(dti_dir, 'eigenvector1.mif')):
    print("\nConverting eigenvector1 to check shape...")
    os.system(f"mrconvert {os.path.join(dti_dir, 'eigenvector1.mif')} /tmp/v1_test.nii.gz -force -quiet")
    v1_data = nib.load('/tmp/v1_test.nii.gz').get_fdata()
    print(f"Eigenvector1 shape: {v1_data.shape}")
    print(f"Single voxel eigenvector shape: {v1_data[100, 100, 50, :].shape}")
    print(f"Single voxel eigenvector: {v1_data[100, 100, 50, :]}")
    
    # Test dot product
    test_grad = gradient_dirs[10]  # A non-zero b-value direction
    test_v1 = v1_data[100, 100, 50, :]
    
    print(f"\nTest gradient shape: {test_grad.shape}")
    print(f"Test v1 shape: {test_v1.shape}")
    
    # Try different reshaping
    test_grad_reshaped = np.squeeze(test_grad)
    test_v1_reshaped = np.squeeze(test_v1)
    
    print(f"After squeeze - gradient: {test_grad_reshaped.shape}, v1: {test_v1_reshaped.shape}")
    
    try:
        dot_product = np.dot(test_grad_reshaped, test_v1_reshaped)
        print(f"Dot product successful: {dot_product}")
    except Exception as e:
        print(f"Dot product failed: {e}")
else:
    print("\nNo DTI eigenvector file found")

# Check for 4D vs 3D issue
print("\n=== Checking dimensionality issues ===")
if gradient_dirs.ndim == 2:
    print(f"Gradient dirs is 2D: {gradient_dirs.shape}")
    single_grad = gradient_dirs[10]
    print(f"Single gradient is: {single_grad.shape}")
    
    if single_grad.ndim == 1:
        print("Single gradient is 1D (correct)")
    else:
        print("Single gradient is not 1D - needs fixing")
        print(f"Content: {single_grad}")