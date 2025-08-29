#!/usr/bin/env python3
"""
Directional bi-exponential fitting module for DWI temperature estimation.

This module implements a bi-exponential model that accounts for tissue anisotropy
by using gradient directions and DTI-derived metrics (FA, eigenvectors).

Author: DWI Temperature Pipeline
Date: 2024
"""

import numpy as np
from scipy.optimize import minimize, differential_evolution
from scipy.optimize import curve_fit
import warnings


def calculate_tissue_diffusion(gradient_dir, v1, FA, MD):
    """
    Calculate directional tissue diffusion based on fiber orientation.
    
    Args:
        gradient_dir: Unit gradient direction vector (3,)
        v1: Principal eigenvector from DTI (3,)
        FA: Fractional anisotropy (scalar)
        MD: Mean diffusivity (scalar) in mm²/s
    
    Returns:
        D_tissue: Tissue diffusion coefficient in gradient direction (mm²/s)
    """
    # Handle edge cases
    if FA < 0.05:  # Nearly isotropic
        return MD
    
    # Calculate parallel and perpendicular diffusivities from FA and MD
    # Using the relationship: FA = sqrt(3/2) * sqrt((λ1-MD)² + (λ2-MD)² + (λ3-MD)²) / sqrt(λ1² + λ2² + λ3²)
    # For axially symmetric tensor: λ1 = D_parallel, λ2 = λ3 = D_perpendicular
    
    # Simplified model based on FA and MD
    D_parallel = MD * (1 + 2 * FA / np.sqrt(3))
    D_perpendicular = MD * (1 - FA / np.sqrt(3))
    
    # Ensure physical bounds
    D_parallel = np.clip(D_parallel, 0.1e-3, 2.0e-3)
    D_perpendicular = np.clip(D_perpendicular, 0.1e-3, 1.5e-3)
    
    # Calculate angle between gradient and fiber direction
    # Ensure both are 1D arrays
    gradient_dir = np.squeeze(gradient_dir)
    v1 = np.squeeze(v1)
    cos_theta = np.abs(np.dot(gradient_dir, v1))  # Use absolute value for symmetry
    
    # Directional diffusion using tensor model
    D_tissue = D_parallel * cos_theta**2 + D_perpendicular * (1 - cos_theta**2)
    
    return D_tissue


def directional_biexponential_signal(b_values, gradient_dirs, S0, f_free, D_free, 
                                    tissue_scale, v1, FA, MD):
    """
    Calculate bi-exponential signal with directional tissue component.
    
    Args:
        b_values: Array of b-values (N,)
        gradient_dirs: Array of gradient directions (N, 3)
        S0: Baseline signal intensity
        f_free: Free water fraction [0, 1]
        D_free: Free water diffusion coefficient (mm²/s)
        tissue_scale: Scaling factor for tissue diffusion
        v1: Principal eigenvector from DTI (3,)
        FA: Fractional anisotropy
        MD: Mean diffusivity (mm²/s)
    
    Returns:
        signals: Predicted signal intensities (N,)
    """
    signals = np.zeros(len(b_values))
    
    for i, (b, g) in enumerate(zip(b_values, gradient_dirs)):
        # Free water component (isotropic)
        free_signal = f_free * np.exp(-b * D_free)
        
        # Tissue component (anisotropic)
        D_tissue = tissue_scale * calculate_tissue_diffusion(g, v1, FA, MD)
        tissue_signal = (1 - f_free) * np.exp(-b * D_tissue)
        
        # Combined signal
        signals[i] = S0 * (free_signal + tissue_signal)
    
    return signals


def fit_directional_biexponential(signal, b_values, gradient_dirs, FA, v1, MD, 
                                 config=None, logger=None):
    """
    Fit directional bi-exponential model to DWI signal.
    
    Args:
        signal: Observed DWI signal intensities (N,)
        b_values: Array of b-values (N,)
        gradient_dirs: Array of gradient directions (N, 3)
        FA: Fractional anisotropy for this voxel
        v1: Principal eigenvector from DTI (3,)
        MD: Mean diffusivity (mm²/s)
        config: Configuration dictionary (optional)
        logger: Logger instance (optional)
    
    Returns:
        dict: Fitted parameters and quality metrics
    """
    
    # Default configuration
    if config is None:
        config = {
            'processing': {
                'biexponential_model': {
                    'd_free_bounds': [2.5e-3, 3.5e-3],  # Tighter bounds for D_free
                    'initial_guess': {
                        'd_free': 3.0e-3,
                        'f_free': 0.7
                    }
                }
            }
        }
    
    biexp_config = config['processing']['biexponential_model']
    d_free_bounds = biexp_config['d_free_bounds']
    
    # Normalize gradient directions
    gradient_dirs = gradient_dirs / np.linalg.norm(gradient_dirs, axis=1, keepdims=True)
    
    # Initial parameter estimation
    S0_init = signal[b_values == 0].mean() if np.any(b_values == 0) else signal[0]
    
    # Use FA to guide initial f_free estimate
    # High FA → more tissue → lower f_free
    f_free_init = np.clip(1.0 - 2.0 * FA, 0.3, 0.95)
    
    # Define objective function for optimization
    def objective(params):
        S0, f_free, D_free, tissue_scale = params
        
        # Predict signal
        predicted = directional_biexponential_signal(
            b_values, gradient_dirs, S0, f_free, D_free, 
            tissue_scale, v1, FA, MD
        )
        
        # Calculate residual sum of squares
        residual = np.sum((signal - predicted) ** 2)
        
        # Add regularization to prefer D_free near 3.0e-3
        d_free_penalty = 0.1 * (D_free - 3.0e-3) ** 2
        
        return residual + d_free_penalty
    
    # Parameter bounds
    bounds = [
        (0.5 * S0_init, 2.0 * S0_init),  # S0
        (0.0, 1.0),                        # f_free
        (d_free_bounds[0], d_free_bounds[1]),  # D_free (tighter bounds)
        (0.3, 1.5)                         # tissue_scale
    ]
    
    # Initial guess
    x0 = [S0_init, f_free_init, 3.0e-3, 1.0]
    
    try:
        # Try local optimization first (faster)
        result = minimize(objective, x0, bounds=bounds, method='L-BFGS-B')
        
        # If local optimization fails or gives poor fit, try global optimization
        if not result.success or result.fun > 0.1 * np.sum(signal ** 2):
            if logger:
                logger.debug("Local optimization failed, trying global optimization")
            result = differential_evolution(objective, bounds, maxiter=500, seed=42)
        
        if result.success:
            S0_fit, f_free_fit, D_free_fit, tissue_scale_fit = result.x
            
            # Calculate fitted signal for R² computation
            fitted_signal = directional_biexponential_signal(
                b_values, gradient_dirs, S0_fit, f_free_fit, D_free_fit,
                tissue_scale_fit, v1, FA, MD
            )
            
            # Calculate R-squared
            ss_res = np.sum((signal - fitted_signal) ** 2)
            ss_tot = np.sum((signal - np.mean(signal)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            
            # Calculate effective tissue diffusion (average across directions)
            tissue_diffusions = [
                tissue_scale_fit * calculate_tissue_diffusion(g, v1, FA, MD)
                for g in gradient_dirs
            ]
            D_tissue_mean = np.mean(tissue_diffusions)
            
            return {
                'S0': S0_fit,
                'f_free': f_free_fit,
                'D_free': D_free_fit,
                'D_tissue': D_tissue_mean,
                'tissue_scale': tissue_scale_fit,
                'r_squared': r_squared,
                'fa_value': FA,
                'fitting_success': True,
                'model_used': 'directional_biexponential'
            }
        else:
            if logger:
                logger.debug(f"Directional bi-exponential fitting failed: {result.message}")
            return {'fitting_success': False}
            
    except Exception as e:
        if logger:
            logger.debug(f"Error in directional bi-exponential fitting: {str(e)}")
        return {'fitting_success': False}


def fit_constrained_biexponential(signal, b_values, D_free_fixed=3.0e-3):
    """
    Fit bi-exponential model with fixed D_free (simpler alternative).
    
    This is a fallback method that fixes D_free to the physiological value
    and only fits f_free and D_tissue.
    
    Args:
        signal: Observed DWI signal intensities (N,)
        b_values: Array of b-values (N,)
        D_free_fixed: Fixed free water diffusion coefficient (default: 3.0e-3 mm²/s)
    
    Returns:
        dict: Fitted parameters
    """
    
    def biexp_constrained(b, S0, f_free, D_tissue):
        return S0 * (f_free * np.exp(-b * D_free_fixed) + 
                    (1 - f_free) * np.exp(-b * D_tissue))
    
    try:
        # Initial guess
        S0_init = signal[0] if signal[0] > 0 else np.max(signal)
        p0 = [S0_init, 0.7, 0.7e-3]
        
        # Bounds
        bounds = ([0, 0, 0.1e-3], [np.inf, 1, 1.5e-3])
        
        # Fit
        popt, _ = curve_fit(biexp_constrained, b_values, signal, 
                           p0=p0, bounds=bounds, maxfev=2000)
        
        S0_fit, f_free_fit, D_tissue_fit = popt
        
        # Calculate R-squared
        y_pred = biexp_constrained(b_values, *popt)
        ss_res = np.sum((signal - y_pred) ** 2)
        ss_tot = np.sum((signal - np.mean(signal)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        return {
            'S0': S0_fit,
            'f_free': f_free_fit,
            'D_free': D_free_fixed,
            'D_tissue': D_tissue_fit,
            'r_squared': r_squared,
            'fitting_success': True,
            'model_used': 'constrained_biexponential'
        }
        
    except Exception:
        return {'fitting_success': False}


def select_optimal_directions(gradient_dirs, n_directions=12):
    """
    Select a subset of gradient directions with maximum angular coverage.
    
    Uses a greedy algorithm to select directions that are maximally separated.
    
    Args:
        gradient_dirs: Array of all gradient directions (N, 3)
        n_directions: Number of directions to select
    
    Returns:
        indices: Indices of selected directions
    """
    if len(gradient_dirs) <= n_directions:
        return np.arange(len(gradient_dirs))
    
    # Normalize directions
    dirs_norm = gradient_dirs / np.linalg.norm(gradient_dirs, axis=1, keepdims=True)
    
    # Start with a random direction
    selected = [0]
    remaining = list(range(1, len(gradient_dirs)))
    
    # Greedily add directions that are maximally separated from already selected ones
    while len(selected) < n_directions and remaining:
        max_min_angle = -1
        best_idx = None
        
        for idx in remaining:
            # Calculate minimum angle to all selected directions
            min_angle = np.min([
                np.arccos(np.clip(np.abs(np.dot(dirs_norm[idx], dirs_norm[s])), 0, 1))
                for s in selected
            ])
            
            if min_angle > max_min_angle:
                max_min_angle = min_angle
                best_idx = idx
        
        if best_idx is not None:
            selected.append(best_idx)
            remaining.remove(best_idx)
    
    return np.array(selected)