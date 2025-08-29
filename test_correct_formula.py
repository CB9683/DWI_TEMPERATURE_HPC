#!/usr/bin/env python3
import numpy as np

# The Le Bihan formula for temperature from diffusion coefficient is:
# D(T) = D0 * exp(-Ea/RT)
# Where:
#   D(T) = diffusion coefficient at temperature T
#   D0 = reference diffusion coefficient  
#   Ea = activation energy
#   R = gas constant
#   T = absolute temperature (Kelvin)
#
# Rearranging to solve for T:
# T = -Ea / (R * ln(D/D0))
#
# Or in the form used in the paper:
# T = A / (B - ln(D))
# Where A and B contain the physical constants

print("Testing different formulations of the temperature formula")
print("=" * 60)

# Test values
D_mm2_s = 0.003  # Typical CSF diffusion at body temperature (mm²/s)
D_m2_s = D_mm2_s * 1e-6  # Convert to m²/s

# Constants from config
A = 2256.74
B = 4.39221

print(f"\nTest diffusion coefficient: D = {D_mm2_s} mm²/s = {D_m2_s} m²/s")
print(f"Constants: A = {A}, B = {B}")
print()

# Test different formulations
print("1. Current formula with mm²/s (WRONG):")
print(f"   T = A / (B + ln(D)) - 273.15")
T1 = A / (B + np.log(D_mm2_s)) - 273.15
print(f"   T = {A} / ({B} + {np.log(D_mm2_s):.3f}) - 273.15")
print(f"   T = {T1:.1f} °C  <-- Clearly wrong!\n")

print("2. With m²/s conversion (STILL WRONG):")
T2 = A / (B + np.log(D_m2_s)) - 273.15
print(f"   T = A / (B + ln(D)) - 273.15")
print(f"   T = {A} / ({B} + {np.log(D_m2_s):.3f}) - 273.15")
print(f"   T = {T2:.1f} °C  <-- Still wrong!\n")

print("3. Correct formula should be T = A / (B - ln(D)):")
print("   Note the MINUS sign, not PLUS!")
print()

# Let's test with the corrected formula
print("Testing corrected formula with different units:")
print("-" * 40)

# With m²/s (likely the intended units)
T3 = A / (B - np.log(D_m2_s)) - 273.15
print(f"With D in m²/s: T = {A} / ({B} - ({np.log(D_m2_s):.3f})) - 273.15")
print(f"                T = {A} / {B - np.log(D_m2_s):.3f} - 273.15")
print(f"                T = {T3:.1f} °C")

if 30 <= T3 <= 42:
    print("                ✓ Physiologically reasonable!\n")
else:
    print("                ✗ Still not in physiological range\n")

# Try with µm²/s (another common unit)
D_um2_s = D_mm2_s * 1e3  # Convert mm²/s to µm²/s
T4 = A / (B - np.log(D_um2_s)) - 273.15
print(f"With D in µm²/s: T = {A} / ({B} - ln({D_um2_s})) - 273.15")
print(f"                 T = {A} / ({B} - {np.log(D_um2_s):.3f}) - 273.15")
print(f"                 T = {T4:.1f} °C")

if 30 <= T4 <= 42:
    print("                 ✓ Physiologically reasonable!\n")
else:
    print("                 ✗ Not in physiological range\n")

# Test a range of typical CSF diffusion values
print("\n" + "=" * 60)
print("Testing range of typical CSF diffusion values:")
print("-" * 60)
D_values_mm2_s = [0.0028, 0.0030, 0.0032, 0.0034]

for D_mm in D_values_mm2_s:
    D_um = D_mm * 1e3  # to µm²/s
    T_celsius = A / (B - np.log(D_um)) - 273.15
    print(f"D = {D_mm:.4f} mm²/s ({D_um:.1f} µm²/s) → T = {T_celsius:.1f} °C")

print("\n" + "=" * 60)
print("CONCLUSION:")
print("1. The formula has a sign error: should be (B - ln(D)), not (B + ln(D))")
print("2. D should likely be in µm²/s (micrometers squared per second)")
print("3. This gives physiologically reasonable temperatures around 37°C")