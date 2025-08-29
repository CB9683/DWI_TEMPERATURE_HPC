#!/usr/bin/env python3
import numpy as np

# The Le Bihan (2007) formula relates diffusion and temperature
# We know that at body temperature (~37°C), CSF diffusion is approximately 3.0 × 10^-3 mm²/s

print("Finding the correct temperature formula and units")
print("=" * 70)

# Known reference point
D_ref_mm2s = 0.003  # mm²/s at ~37°C
T_ref_celsius = 37.0
T_ref_kelvin = T_ref_celsius + 273.15

# Constants from config
A = 2256.74
B = 4.39221

print(f"Reference: D = {D_ref_mm2s} mm²/s at T = {T_ref_celsius}°C ({T_ref_kelvin}K)")
print(f"Constants: A = {A}, B = {B}")
print()

# Test all combinations of formula and units
print("Testing different formula variations:")
print("-" * 70)

formulas = [
    ("A / (B + ln(D))", lambda D: A / (B + np.log(D))),
    ("A / (B - ln(D))", lambda D: A / (B - np.log(D))),
    ("A / (ln(D) + B)", lambda D: A / (np.log(D) + B)),
    ("A / (ln(D) - B)", lambda D: A / (np.log(D) - B)),
    ("A * (B + ln(D))", lambda D: A * (B + np.log(D))),
    ("A * (B - ln(D))", lambda D: A * (B - np.log(D))),
]

unit_conversions = [
    ("mm²/s (as is)", 1.0),
    ("m²/s (× 10^-6)", 1e-6),
    ("cm²/s (× 10^-2)", 1e-2),
    ("µm²/s (× 10^3)", 1e3),
    ("× 10^-9", 1e-9),
    ("× 10^-12", 1e-12),
]

best_match = None
best_error = float('inf')

for formula_name, formula_func in formulas:
    for unit_name, conversion in unit_conversions:
        D_converted = D_ref_mm2s * conversion
        try:
            T_kelvin = formula_func(D_converted)
            T_celsius = T_kelvin - 273.15
            error = abs(T_celsius - T_ref_celsius)
            
            if error < 5:  # Within 5°C of expected
                print(f"✓ {formula_name:20s} with D in {unit_name:20s}: T = {T_celsius:6.1f}°C (error: {error:.1f}°C)")
                if error < best_error:
                    best_error = error
                    best_match = (formula_name, unit_name, conversion, T_celsius)
        except:
            pass

print("\n" + "=" * 70)

if best_match:
    formula_name, unit_name, conversion, T_celsius = best_match
    print(f"BEST MATCH: {formula_name} with D in {unit_name}")
    print(f"Gives T = {T_celsius:.1f}°C (target: {T_ref_celsius}°C)")
    print(f"\nConversion factor: multiply mm²/s by {conversion}")
    
    # Test with a range of values
    print("\nVerification with typical CSF diffusion values:")
    print("-" * 50)
    D_test_values = [0.0028, 0.0030, 0.0032, 0.0034]  # mm²/s
    
    # Determine which formula to use based on best match
    if "B - ln" in formula_name:
        formula = lambda D: A / (B - np.log(D))
    elif "B + ln" in formula_name:
        formula = lambda D: A / (B + np.log(D))
    elif "ln(D) - B" in formula_name:
        formula = lambda D: A / (np.log(D) - B)
    else:
        formula = lambda D: A / (np.log(D) + B)
    
    for D_mm2s in D_test_values:
        D_converted = D_mm2s * conversion
        T = formula(D_converted) - 273.15
        print(f"D = {D_mm2s:.4f} mm²/s → T = {T:.1f}°C")
else:
    print("No reasonable match found with the given constants!")
    print("\nThe constants A and B might be incorrect for the Le Bihan formula.")
    print("Let's derive the correct constants...")
    print()
    
    # Try to derive correct constants
    # Assuming formula: T = A / (B - ln(D))
    # At 37°C, D = 3.0 × 10^-9 m²/s
    D_37_m2s = 3.0e-9
    T_37_K = 310.15
    
    # At 25°C, D ≈ 2.3 × 10^-9 m²/s (from literature)
    D_25_m2s = 2.3e-9
    T_25_K = 298.15
    
    # Solve for A and B
    # T1 = A / (B - ln(D1))
    # T2 = A / (B - ln(D2))
    
    ln_D1 = np.log(D_37_m2s)
    ln_D2 = np.log(D_25_m2s)
    
    # From the two equations:
    # B = (T2*ln_D2 - T1*ln_D1) / (T2 - T1)
    # A = T1 * (B - ln_D1)
    
    B_derived = (T_25_K * ln_D2 - T_37_K * ln_D1) / (T_25_K - T_37_K)
    A_derived = T_37_K * (B_derived - ln_D1)
    
    print(f"Derived constants for T = A / (B - ln(D)) with D in m²/s:")
    print(f"A = {A_derived:.2f}")
    print(f"B = {B_derived:.2f}")
    
    # Test the derived constants
    print("\nTesting derived constants:")
    for D_mm2s in [0.0028, 0.0030, 0.0032, 0.0034]:
        D_m2s = D_mm2s * 1e-6
        T = A_derived / (B_derived - np.log(D_m2s)) - 273.15
        print(f"D = {D_mm2s:.4f} mm²/s → T = {T:.1f}°C")