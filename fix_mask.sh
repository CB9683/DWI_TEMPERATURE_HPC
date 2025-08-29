#!/bin/bash

# Fix the missing dwi_mask_upsampled.mif file issue

OUTPUT_DIR="/g/data/hl36/cb4095/WAND/derivatives/temp_pipeline_2025-07-23_09-17-03/analysis_20250801_113554"
# Get subject from config file
SUBJECT=$(python3 -c "import json; print(json.load(open('pipeline_config.json'))['subjects'][0])")
SUBJECT_DIR="${OUTPUT_DIR}/${SUBJECT}"

echo "Creating missing dwi_mask_upsampled.mif file..."

# Load MRtrix
export PATH=/g/data/vp06/Christian/software/mrtrix3/bin:${PATH}

# Create a brain mask from the DWI data
if [ -f "${SUBJECT_DIR}/dwi_upsampled.mif" ]; then
    echo "Generating mask from dwi_upsampled.mif..."
    dwi2mask "${SUBJECT_DIR}/dwi_upsampled.mif" "${SUBJECT_DIR}/dwi_mask_upsampled.mif" -force
    
    if [ $? -eq 0 ]; then
        echo "Successfully created ${SUBJECT_DIR}/dwi_mask_upsampled.mif"
        ls -la "${SUBJECT_DIR}/dwi_mask_upsampled.mif"
    else
        echo "Failed to create mask"
        exit 1
    fi
else
    echo "ERROR: dwi_upsampled.mif not found!"
    exit 1
fi

echo "Done! You can now run test_biexponential.sh"