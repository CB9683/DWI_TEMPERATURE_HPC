#!/usr/bin/env python3
import numpy as np

print("Sanity check for temperature formula")
print("=" * 70)
print()

# According to the METHODS_SECTION.md, the formula is:
# T(°C) = (A / (B + ln(D))) - 273.15
# where D is in mm²/s

A = 2256.74
B = 4.39221

# But this formula seems wrong because ln(D) with D in mm²/s gives negative values
# Let's check what units make sense

# Typical CSF diffusion values
D_mm2s = 0.003  # mm²/s at body temperature

print("Testing the documented formula: T = (A / (B + ln(D))) - 273.15")
print(f"With A = {A}, B = {B}")
print()

# Test with different unit interpretations
print("1. If D is in mm²/s (as documented):")
print(f"   D = {D_mm2s} mm²/s")
print(f"   ln(D) = {np.log(D_mm2s):.3f}")
print(f"   B + ln(D) = {B + np.log(D_mm2s):.3f}") 
print(f"   T = {A} / {B + np.log(D_mm2s):.3f} - 273.15")
T1 = A / (B + np.log(D_mm2s)) - 273.15
print(f"   T = {T1:.1f}°C  ← Clearly wrong!\n")

print("2. If D is in µm²/s (micrometers squared per second):")
D_um2s = D_mm2s * 1000  # Convert mm²/s to µm²/s
print(f"   D = {D_um2s} µm²/s")
print(f"   ln(D) = {np.log(D_um2s):.3f}")
print(f"   B + ln(D) = {B + np.log(D_um2s):.3f}")
print(f"   T = {A} / {B + np.log(D_um2s):.3f} - 273.15")
T2 = A / (B + np.log(D_um2s)) - 273.15
print(f"   T = {T2:.1f}°C  ← Still wrong!\n")

print("3. Perhaps the formula or constants are from a different paper?")
print("   Let me try to reverse engineer what would give 37°C...\n")

# What value of D would give 37°C with the current formula?
T_target = 37.0  # °C
T_kelvin = T_target + 273.15
# T_kelvin = A / (B + ln(D))
# B + ln(D) = A / T_kelvin
# ln(D) = A/T_kelvin - B
D_needed = np.exp(A/T_kelvin - B)
print(f"   To get T = 37°C with formula T = (A / (B + ln(D))) - 273.15:")
print(f"   We need D = exp({A/T_kelvin:.3f} - {B:.3f}) = exp({A/T_kelvin - B:.3f})")
print(f"   D = {D_needed:.6f}")
print(f"   This is {D_needed:.2e} which doesn't match any reasonable unit\n")

print("=" * 70)
print("HYPOTHESIS: The constants might be wrong or from a different formula")
print()

# Let's try the more standard Arrhenius form
# D(T) = D0 * exp(-Ea/(R*T))
# Taking natural log: ln(D) = ln(D0) - Ea/(R*T)
# Rearranging: T = -Ea / (R * (ln(D) - ln(D0)))
# Or: T = A / (ln(D0) - ln(D)) where A = Ea/R

print("Standard Arrhenius equation form:")
print("T = Ea / (R * (ln(D0) - ln(D)))")
print()

# For water, typical values:
# Ea ≈ 15-20 kJ/mol
# R = 8.314 J/(mol·K)
# D0 is the pre-exponential factor

# If A = 2256.74, this suggests Ea/R = 2256.74
# So Ea = 2256.74 * 8.314 = 18.76 kJ/mol (reasonable!)

# The B term would be related to ln(D0)
# Let's calculate what D0 would be
Ea_over_R = A  # This is A from the config
D_37C_m2s = 3.0e-9  # Typical CSF diffusion at 37°C in m²/s
T_37_K = 310.15

# From D = D0 * exp(-Ea/(R*T))
# D0 = D / exp(-Ea/(R*T)) = D * exp(Ea/(R*T))
ln_D0 = np.log(D_37C_m2s) + Ea_over_R / T_37_K
D0 = np.exp(ln_D0)

print(f"If the formula is based on Arrhenius equation:")
print(f"  Ea/R = {Ea_over_R:.2f} K")
print(f"  At 37°C, D = {D_37C_m2s:.2e} m²/s")
print(f"  This gives ln(D0) = {ln_D0:.3f}")
print(f"  So D0 = {D0:.2e} m²/s")
print()
print(f"The formula should be: T = {Ea_over_R:.2f} / ({ln_D0:.3f} - ln(D))")
print(f"With D in m²/s")
print()

# Test this formula
print("Testing corrected Arrhenius-based formula:")
print("-" * 50)
test_D_mm2s = [0.0025, 0.0028, 0.0030, 0.0032, 0.0035]
for D_mm in test_D_mm2s:
    D_m = D_mm * 1e-6  # Convert to m²/s
    T = Ea_over_R / (ln_D0 - np.log(D_m))
    T_celsius = T - 273.15
    print(f"D = {D_mm:.4f} mm²/s → T = {T_celsius:.1f}°C")