# CSF Temperature Estimation Pipeline

This repository contains a comprehensive, automated pipeline for estimating brain temperature from diffusion-weighted imaging (DWI) data, with a focus on the cerebrospinal fluid (CSF). The pipeline leverages tools from MRtrix3, FSL, and custom Python scripts to perform preprocessing, analysis, and quality control reporting.

## 🆕 Version 2.0: Bi-exponential Diffusion Model
The pipeline now includes an advanced bi-exponential diffusion model to address partial volume effects in CSF regions. This enhancement separates free water diffusion from tissue-contaminated signals, providing more accurate temperature estimates. See [CLAUDE.md](CLAUDE.md) for detailed documentation.

It is designed to be run on a High-Performance Computing (HPC) cluster using the Portable Batch System (PBS) for job scheduling.

## Key Features

-   **Automated Workflow:** Orchestrates the entire process from raw BIDS data to final reports using a single command.
-   **Robust Preprocessing:** Implements a state-of-the-art preprocessing pipeline including denoising, Gibbs ringing removal, distortion correction, and bias field correction.
-   **Advanced DWI Modeling:** Uses multi-shell, multi-tissue constrained spherical deconvolution (MSMT-CSD) with the dhollander algorithm for accurate tissue response function estimation.
-   **Flexible Analysis:** Allows for easy testing of different b-value combinations to assess the stability of temperature estimates.
-   **Comprehensive Reporting:** Generates detailed figures, statistical summaries, quality control metrics, and a final HTML report for easy interpretation of results.
-   **Efficient Scheduling:** Uses PBS job dependencies to ensure a smooth, sequential execution of pipeline stages.
-   **Reproducibility:** All parameters and software versions are managed through a configuration file and conda environment.

## Pipeline Workflow

The pipeline is managed by `00_pipeline_manager.sh` and proceeds in three main stages, each submitted as a dependent PBS job:

1.  **Preprocessing (`01_run_preprocessing.sh` -> `02_preprocess_subject.py`)**
    -   Converts BIDS data to MRtrix format.
    -   Performs denoising and Gibbs ringing removal.
    -   Runs distortion and eddy-current correction using FSL's `eddy`.
    -   Performs ANTs-based bias field correction.
    -   Upsamples data to a standard voxel size (1.5mm isotropic).
    -   Estimates tissue response functions (WM, GM, CSF) using the dhollander algorithm.
    -   Performs MSMT-CSD and intensity normalization (`mtnormalise`).
    -   **Final Outputs:** Preprocessed DWI, tissue maps (`wmfod_norm.mif`, `gm_norm.mif`, `csf_norm.mif`), and brain masks.

2.  **Temperature Calculation (`03_run_bvalue_sweep.sh` -> `04_calculate_temperature.py`)**
    -   This stage runs *in parallel* for each b-value combination specified in the configuration file.
    -   For each combination:
        -   Calculates an Apparent Diffusion Coefficient (ADC) map.
        -   Generates a CSF mask using either the normalized CSF tissue map or ADC thresholding.
        -   Calculates a temperature map from the ADC values within the CSF mask.
        -   Generates statistics, quality control metrics, and a summary visualization.

3.  **Reporting & Visualization (`07_generate_reports.sh` -> `05_create_histograms.py` & `06_comprehensive_analysis.py`)**
    -   **Histograms:** Creates detailed histogram plots for each individual analysis run.
    -   **Comprehensive Report:** Aggregates results from all analysis runs, generates comparison plots (e.g., temperature vs. number of b-values), and creates a final summary HTML report.

## Prerequisites

1.  **HPC Environment:** A Linux-based system with a PBS job scheduler.
2.  **Software:**
    -   Miniconda or Anaconda
    -   MRtrix3 (and optionally the MRtrix3Tissue fork)
    -   FSL
3.  **Data:** DWI data organized according to the Brain Imaging Data Structure (BIDS) standard. The pipeline specifically expects DWI data with both AP and PA phase-encoding directions for distortion correction.

## Setup and Configuration

1.  **Clone the Repository:**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-name>
    ```

2.  **Create Conda Environment:**
    A `environment.yml` file should be created to ensure all Python dependencies are met.
    ```yaml
    # environment.yml
    name: csf-temp-env
    channels:
      - defaults
      - conda-forge
    dependencies:
      - python=3.9
      - numpy
      - pandas
      - nibabel
      - matplotlib
      - seaborn
      - scipy
    ```
    Create and activate the environment:
    ```bash
    conda env create -f environment.yml
    conda activate csf-temp-env
    ```

3.  **Configure the Pipeline:**
    Edit the `pipeline_config.json` file. This is the central control file for the pipeline.

    ```json
    {
        "subjects": [
            "sub-00395"
        ],
        "paths": {
            "base_output": "/g/data/hl36/cb4095/WAND/derivatives",
            "bids_root": "/g/data/hl36/cb4095/WAND/bids",
            "conda_env": "/path/to/your/miniconda3/envs/csf-temp-env",
            "fsl_dir": "/apps/fsl/6.0.5.1",
            "mrtrix3_bin": "/apps/mrtrix3/3.0.3/bin",
            "mrtrix3tissue_bin": "/path/to/mrtrix3tissue/bin"
        },
        "bvalue_sets": [
            [0, 200, 500, 1000],
            [0, 200, 500, 2000],
            [0, 500, 1000, 2000],
            [0, 200, 500, 1000, 2000]
        ],
        "processing": {
            "bvalue_tolerance": 50,
            "csf_mask_method": "3tissue",
            "csf_threshold": 0.07,
            "adc_threshold_min": 0.0025,
            "adc_threshold_max": 0.004,
            "temperature_constants": {
                "A": 2.2556,
                "B": -10.428
            }
        }
    }
    ```

## How to Run the Pipeline

The entire pipeline is launched using the `00_pipeline_manager.sh` script.

**Standard Run (from scratch):**
This will create a new timestamped output directory and run all stages from preprocessing to final reporting.


bash 00_pipeline_manager.sh

**Skipping Preprocessing**

# You must provide the path to the existing output directory
bash 00_pipeline_manager.sh --skip-preprocessing --output-dir /path/to/your/previous/output_dir

**Output Structure**

<output_dir>/
├── <subject_id>/
│   ├── dwi_preproc_unbiased.mif      # Main preprocessed DWI file
│   ├── dwi_upsampled.mif           # Upsampled DWI
│   ├── dwi_mask_upsampled.mif      # Final brain mask
│   ├── wmfod_norm.mif              # Normalized WM FODs
│   ├── gm_norm.mif                 # Normalized GM signal
│   ├── csf_norm.mif                # Normalized CSF signal
│   ├── adc_map_full_b_...mif       # ADC maps for each analysis
│   ├── temperature_map_b_...mif    # Temperature maps for each analysis
│   ├── temperature_stats_b_...csv  # Statistics for each analysis
│   ├── temperature_values_b_...txt # Raw temperature values for each analysis
│   ├── temperature_visualization_b_...png # Visualization for each analysis
│   ├── histograms/                 # Directory for histogram plots
│   │   ├── histogram_b_...png
│   │   └── comparison_all_analyses.png
│   └── comprehensive_report/       # Final aggregated report
│       ├── comprehensive_analysis.png
│       ├── all_statistics_combined.csv
│       └── report.html             # The main HTML report
├── pipeline_config.json            # A copy of the configuration used
└── pipeline_metadata.json          # Metadata about the pipeline run

**Parameter Finetuning**

- In pipeline_config.json:
bvalue_sets: This is the most important parameter for the analysis stage. Define different combinations of b-values to test their impact on the temperature estimate.
bvalue_tolerance: The tolerance (in s/mm²) for matching b-values. Useful if your scanner produces slightly inexact b-values (e.g., 998 instead of 1000).
csf_mask_method: Choose between '3tissue' (uses the normalized CSF map from MSMT-CSD) or 'adc_threshold' (uses a simple ADC value range).
csf_threshold: The threshold for the normalized CSF map when csf_mask_method is '3tissue'. See detailed explanation below.
adc_threshold_min/max: The ADC range (in mm²/s) for creating the CSF mask when csf_mask_method is 'adc_threshold'.
temperature_constants: The A and B constants for the Le Bihan temperature equation: T(°C) = (A / (B + ln(ADC))) - 273.15. These are derived from the physical properties of water diffusion.

- In 02_preprocess_subject.py:
Eddy Options (Line 167): eddy_options = ' --slm=linear --data_is_shelled'
--slm=linear: Assumes linear signal change for small head movements. Can be removed for more complex models if needed.
--data_is_shelled: Crucial for multi-shell data.
Upsampling Voxel Size (Line 173): '-voxel', '1.5'
The entire analysis is performed at 1.5mm isotropic resolution. You can change this value, but be aware it will significantly impact computation time and CSF partial voluming.
Mask Upsampling Interpolation (Line 174): -interp linear
Using linear interpolation for the mask before thresholding can provide a smoother result than nearest neighbor. You could change this to nearest.
Mask Filtering (Line 175): maskfilter - median
A median filter is applied to the upsampled mask to clean it up. You could add more erode or dilate steps here if your masks require more aggressive cleaning.
- In 05_create_histograms.py:
Physiological Range (Line 84): ax1.axvspan(35, 39, ...)
This defines the shaded "plausible" physiological temperature range on the histograms. You can adjust these values based on your assumptions.



"""
"bvalue_sets": [
        [0, 200],
        [0, 500],
        [0, 1200],
        [0, 2400],
        [0, 4000],
        [0, 6000],
        [0, 200, 500],
        [0, 200, 500, 1200],
        [0, 200, 500, 1200, 2400],
        [0, 200, 500, 1200, 2400]
    ]
"""