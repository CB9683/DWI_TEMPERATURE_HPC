# Methods: Brain Temperature Estimation from Diffusion-Weighted Imaging

## 3.1 Overview

Brain temperature estimation was performed using a novel bi-exponential diffusion model applied to multi-shell diffusion-weighted imaging (DWI) data. The methodology addresses the fundamental limitation of traditional monoexponential approaches in cerebrospinal fluid (CSF) regions, where partial volume effects from surrounding tissue contamination lead to systematic underestimation of free water diffusivity and consequent overestimation of brain temperature.

## 3.2 Theoretical Framework

### 3.2.1 Temperature-Diffusion Relationship

Brain temperature estimation relies on the established relationship between water diffusivity and temperature, as described by the Arrhenius equation. Following Le Bihan (2007), the temperature-diffusion relationship for free water is given by:

```
T(°C) = (A / (B + ln(D))) - 273.15
```

where A = 2256.74 and B = 4.39221 are empirically determined constants, and D represents the diffusion coefficient of free water in mm²/s. This relationship forms the foundation for non-invasive temperature mapping using diffusion MRI.

### 3.2.2 Partial Volume Effects in CSF

In conventional monoexponential diffusion models, the apparent diffusion coefficient (ADC) represents an averaged measure across all water compartments within a voxel:

```
S(b) = S₀ × exp(-b × ADC)
```

However, in CSF-containing voxels, the measured signal comprises contributions from both free water and tissue compartments due to limited spatial resolution. This partial volume effect results in ADC values that are systematically lower than pure CSF diffusivity, leading to artificially elevated temperature estimates.

### 3.2.3 Bi-exponential Diffusion Model

To address partial volume contamination, a bi-exponential diffusion model was implemented that explicitly separates free water and tissue components:

```
S(b) = S₀ × [f_free × exp(-b × D_free) + (1 - f_free) × exp(-b × D_tissue)]
```

where:
- **f_free**: Volume fraction of free water (0 ≤ f_free ≤ 1)
- **D_free**: Diffusion coefficient of free water (temperature-dependent)
- **D_tissue**: Diffusion coefficient of restricted tissue water (temperature-independent)

This model enables direct estimation of D_free, which represents the true free water diffusivity uncontaminated by tissue contributions, thereby providing more accurate temperature measurements.

## 3.3 Data Acquisition Requirements

### 3.3.1 Imaging Protocol

Multi-shell diffusion-weighted imaging was performed with the following specifications:
- **B-values**: 0, 200, 500, 1200, 2400, 4000, 6000 s/mm²
- **Phase encoding directions**: Both anterior-posterior (AP) and posterior-anterior (PA) for distortion correction
- **Spatial resolution**: Native acquisition resolution maintained throughout preprocessing
- **Shell sampling**: Minimum 20 directions per shell for robust parameter estimation

The comprehensive b-value sampling was essential for bi-exponential model fitting, as low b-values (0-500 s/mm²) primarily reflect free water diffusion while higher b-values (>1000 s/mm²) provide sensitivity to tissue compartment characteristics.

### 3.3.2 BIDS Compliance

All imaging data were organized according to the Brain Imaging Data Structure (BIDS) specification to ensure reproducibility and standardized processing. This included proper naming conventions, metadata storage in JSON sidecars, and consistent directory structures.

## 3.4 Image Preprocessing

### 3.4.1 Quality Assurance and Conversion

Initial processing involved conversion from DICOM to NIfTI format using MRtrix3's `mrconvert`, with simultaneous import of gradient tables (b-values and b-vectors) to ensure proper geometric interpretation of diffusion data.

### 3.4.2 Denoising

Thermal noise reduction was performed using the Marchenko-Pastur PCA denoising algorithm implemented in `dwidenoise` (Veraart et al., 2016). This approach exploits the redundancy in multi-directional diffusion data to estimate and remove noise while preserving genuine signal variations. Denoising was applied as the first preprocessing step to maximize the signal-to-noise ratio for subsequent processing stages.

**Rationale**: Improved signal-to-noise ratio is critical for reliable bi-exponential model fitting, as the separation of free water and tissue components requires precise measurement of signal decay across b-values.

### 3.4.3 Gibbs Ringing Removal

Gibbs ringing artifacts, resulting from k-space truncation during image acquisition, were removed using `mrdegibbs` (Kellner et al., 2016). These artifacts manifest as oscillatory intensity patterns near tissue boundaries and can significantly impact diffusion parameter estimation, particularly in CSF regions adjacent to brain tissue.

**Rationale**: CSF-tissue interfaces are primary regions of interest for temperature estimation, making removal of boundary artifacts essential for accurate parameter mapping.

### 3.4.4 Motion and Distortion Correction

Correction for subject motion, eddy current distortions, and susceptibility-induced distortions was performed using FSL's `eddy` with the following configuration:
- **Slice-to-volume motion correction**: Enabled to account for inter-slice motion
- **Outlier detection and replacement**: Automatic detection and replacement of signal dropouts
- **GPU acceleration**: Utilized when available for computational efficiency

Susceptibility distortions were corrected using the reversed phase-encoding approach, where b=0 images acquired with opposing phase-encoding directions (AP and PA) were used to estimate the distortion field.

**Rationale**: Accurate spatial correspondence between DWI images is prerequisite for reliable diffusion parameter estimation. Geometric distortions can lead to partial volume effects and misalignment of CSF regions.

### 3.4.5 Bias Field Correction

Intensity inhomogeneity correction was performed using ANTs N4BiasFieldCorrection algorithm integrated through MRtrix3's `dwibiascorrect`. This step ensures uniform signal intensity across the imaging field of view, which is essential for accurate quantitative diffusion measurements.

**Rationale**: Bias fields can artificially alter signal intensities and affect the estimation of diffusion parameters, particularly in regions with low signal intensity such as CSF.

### 3.4.6 Spatial Normalization

Images were resampled to 1.5 mm isotropic resolution using `mrgrid` with sinc interpolation. This standardization facilitates consistent partial volume characteristics across subjects while maintaining sufficient resolution for CSF identification.

**Rationale**: Standardized voxel size enables consistent partial volume effects and facilitates inter-subject comparison of temperature measurements.

## 3.5 Multi-Tissue Analysis

### 3.5.1 Tissue Response Function Estimation

Tissue-specific response functions were estimated using the unsupervised Dhollander algorithm (Dhollander et al., 2016), which automatically identifies voxels representative of white matter, gray matter, and CSF based on their diffusion characteristics. This approach eliminates the need for manual region-of-interest selection and provides robust tissue classification.

**Rationale**: Accurate tissue segmentation is essential for identifying CSF regions and validating diffusion model parameters. The unsupervised approach reduces bias and improves reproducibility.

### 3.5.2 Multi-Shell Multi-Tissue Constrained Spherical Deconvolution

Multi-shell multi-tissue constrained spherical deconvolution (MSMT-CSD) was performed using `dwi2fod` to generate tissue-specific fiber orientation distributions (FODs) for white matter, gray matter, and CSF. The normalized CSF compartment (csf_norm.mif) served as a probabilistic mask for temperature analysis regions.

**Rationale**: MSMT-CSD provides principled separation of tissue compartments and generates probabilistic tissue maps that can be used to identify regions with high CSF content for temperature estimation.

## 3.6 Diffusion Tensor Imaging Analysis

### 3.6.1 Tensor Fitting

Diffusion tensor imaging (DTI) analysis was performed using the complete b-value range (0-6000 s/mm²) through `dwi2tensor`. The full multi-shell data were utilized to maximize the accuracy of tensor parameter estimation, particularly for fractional anisotropy (FA) calculation.

**Rationale**: FA maps provide complementary information about tissue microstructure that can be used to validate bi-exponential model results and identify regions suitable for temperature estimation.

### 3.6.2 Tensor Metrics Calculation

Standard DTI metrics were calculated using `tensor2metric`:
- **Fractional Anisotropy (FA)**: Measure of diffusion directionality
- **Mean Diffusivity (MD)**: Average diffusion across all directions
- **Axial Diffusivity (AD)**: Diffusion parallel to principal eigenvector
- **Radial Diffusivity (RD)**: Diffusion perpendicular to principal eigenvector

**Rationale**: These metrics provide context for interpreting bi-exponential model parameters and enable quality control through comparison of tissue characteristics.

## 3.7 Temperature Estimation

### 3.7.1 B-value Subset Selection

Temperature analysis was performed using specific b-value subsets defined in the configuration file. Typical combinations included [0, 200] and [0, 1200] s/mm², selected to optimize the sensitivity to free water diffusion while maintaining adequate signal-to-noise ratio.

**Rationale**: Lower b-values provide better sensitivity to free water diffusion, which is the temperature-sensitive component. Higher b-values add noise without substantially improving free water parameter estimation.

### 3.7.2 Bi-exponential Model Fitting

For each b-value subset, bi-exponential diffusion models were fitted using constrained non-linear optimization implemented in SciPy. The fitting procedure employed:

**Parameter Bounds**:
- D_free: [2.0×10⁻³, 4.0×10⁻³] mm²/s (physiologically plausible at body temperature)
- D_tissue: [0.1×10⁻³, 1.5×10⁻³] mm²/s (restricted diffusion range)
- f_free: [0.0, 1.0] (volume fraction)

**Initial Parameter Estimates**:
- D_free: 3.0×10⁻³ mm²/s
- D_tissue: 0.7×10⁻³ mm²/s
- f_free: 0.7

**Optimization Algorithm**: Trust Region Reflective algorithm with analytical Jacobian computation for computational efficiency.

**Rationale**: Constrained optimization ensures physiologically meaningful parameter estimates while preventing convergence to unrealistic solutions. Initial estimates based on literature values improve convergence reliability.

### 3.7.3 Model Selection and Quality Control

Bi-exponential model fits were evaluated using the coefficient of determination (R²). Voxels with R² < 0.7 were automatically reverted to monoexponential ADC estimation to ensure robust temperature mapping.

**Quality Control Criteria**:
- R² threshold: 0.7 (minimum acceptable fit quality)
- FA validation: Results cross-referenced with tissue microstructure
- Parameter bounds checking: Automatic rejection of non-physiological values

**Rationale**: Poor bi-exponential fits often indicate insufficient signal-to-noise ratio or inadequate b-value sampling. Fallback to monoexponential modeling ensures complete temperature maps while maintaining data quality.

### 3.7.4 CSF Mask Generation

CSF masks were generated using the normalized CSF probability maps from MSMT-CSD with a threshold of 0.07. This probabilistic approach accounts for partial volume effects and provides more robust region selection than binary segmentation approaches.

**Rationale**: Probabilistic masking better represents the continuous nature of tissue mixing in imaging voxels and provides more stable temperature measurements across subjects.

### 3.7.5 Temperature Calculation

Temperature maps were calculated using the temperature-diffusion relationship applied to D_free values from bi-exponential fitting:

```
T(°C) = (2256.74 / (4.39221 + ln(D_free))) - 273.15
```

For voxels where bi-exponential fitting failed (R² < 0.7), conventional ADC-based temperature calculation was used as fallback.

**Rationale**: The bi-exponential approach provides unbiased free water diffusivity estimates, leading to more accurate temperature measurements compared to ADC-based approaches in partial volume scenarios.

## 3.8 Statistical Analysis and Validation

### 3.8.1 Model Comparison

Direct comparison between bi-exponential and monoexponential temperature estimates was performed through:
- **Voxel-wise difference maps**: T_biexp - T_monoexp
- **Paired t-tests**: Statistical significance of temperature differences
- **Correlation analysis**: Relationship between FA and temperature improvement

**Rationale**: Systematic comparison validates the bi-exponential approach and quantifies the impact of partial volume correction on temperature estimation.

### 3.8.2 Stability Analysis

Temperature stability across different b-value combinations was assessed by:
- **Coefficient of variation**: Measure of consistency across analyses
- **Stable voxel identification**: Regions with CV < threshold (typically 2%)
- **Spatial stability mapping**: Visualization of measurement reliability

**Rationale**: Stable temperature measurements across b-value combinations indicate robust parameter estimation and provide confidence in the reliability of temperature estimates.

### 3.8.3 Quality Metrics

Comprehensive quality control metrics were calculated including:
- **Fitting quality**: R² distributions and parameter uncertainty
- **Physiological plausibility**: Parameter range validation
- **Spatial consistency**: Coherence of temperature patterns with anatomical structures

**Rationale**: Multi-faceted quality assessment ensures reliable temperature measurements and enables identification of potential artifacts or processing issues.

## 3.9 Computational Implementation

### 3.9.1 High-Performance Computing

All analyses were performed on a high-performance computing cluster using the Portable Batch System (PBS) job scheduler. Parallel processing was utilized for:
- **Multi-subject processing**: Independent subject-level analyses
- **Multi-analysis processing**: Parallel b-value subset analyses
- **GPU acceleration**: FSL eddy processing when available

**Rationale**: HPC resources enable efficient processing of computationally intensive bi-exponential fitting across large datasets while maintaining reproducible execution environments.

### 3.9.2 Software Environment

Processing was performed using a standardized Conda environment (dwi_temperature) containing:
- **MRtrix3**: Version 3.0+ for DWI processing
- **FSL**: Version 6.0+ for motion/distortion correction
- **Python**: Version 3.9 with SciPy, NumPy, and nibabel
- **ANTs**: For bias field correction

**Rationale**: Containerized software environments ensure reproducible results across different computing systems and facilitate validation of methodological approaches.

## 3.10 Output Generation and Reporting

### 3.10.1 Quantitative Outputs

For each subject and b-value combination, the following quantitative outputs were generated:
- **Parameter maps**: D_free, D_tissue, f_free, R² (MRtrix .mif format)
- **Temperature maps**: Voxel-wise temperature estimates (°C)
- **Statistical summaries**: Mean, median, standard deviation within CSF regions
- **Quality metrics**: Fit quality, parameter distributions, stability measures

### 3.10.2 Visualization and Reporting

Comprehensive visualization included:
- **Multi-planar temperature maps**: Axial, coronal, and sagittal views
- **Parameter distribution histograms**: D_free, temperature, and fit quality
- **Model comparison plots**: Bi-exponential vs. monoexponential differences
- **Quality control summaries**: FA validation and stability analysis
- **Interactive HTML reports**: Integrated results presentation

**Rationale**: Comprehensive visualization enables thorough evaluation of results, identification of potential artifacts, and communication of findings to diverse scientific audiences.

---

## References

- Dhollander, T., Raffelt, D., & Connelly, A. (2016). Unsupervised 3-tissue response function estimation from single-shell or multi-shell diffusion MR data without a co-registered T1 image. ISMRM Workshop on Breaking the Barriers of Diffusion MRI, 5.

- Kellner, E., Dhital, B., Kiselev, V. G., & Reisert, M. (2016). Gibbs‐ringing artifact removal based on local subvoxel‐shifts. Magnetic Resonance in Medicine, 76(5), 1574-1581.

- Le Bihan, D. (2007). The 'wet mind': water and functional neuroimaging. Physics in Medicine & Biology, 52(7), R57-R90.

- Veraart, J., Novikov, D. S., Christiaens, D., Ades-Aron, B., Sijbers, J., & Fieremans, E. (2016). Denoising of diffusion MRI using random matrix theory. NeuroImage, 142, 394-406.

---

*This methods section describes the computational pipeline developed for brain temperature estimation using bi-exponential diffusion modeling. The approach addresses fundamental limitations of conventional methods through principled separation of free water and tissue contributions in cerebrospinal fluid regions.*