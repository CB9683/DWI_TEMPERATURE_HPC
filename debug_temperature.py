#!/usr/bin/env python3
import numpy as np

# Constants from config
A = 2256.74
B = 4.39221

# Test diffusion coefficient values
D_values_mm2_s = [0.003, 0.0031, 0.0032, 0.0033]  # mm²/s (typical CSF values)

print("Temperature calculation debug:")
print("=" * 50)
print(f"Using constants: A={A}, B={B}")
print()

for D in D_values_mm2_s:
    print(f"\nD = {D} mm²/s")
    print(f"  log(D) = {np.log(D)}")
    print(f"  B + log(D) = {B + np.log(D)}")
    print(f"  A / (B + log(D)) = {A / (B + np.log(D))}")
    temp_kelvin = A / (B + np.log(D))
    temp_celsius = temp_kelvin - 273.15
    print(f"  Temperature (K) = {temp_kelvin:.2f}")
    print(f"  Temperature (°C) = {temp_celsius:.2f}")
    
print("\n" + "=" * 50)
print("\nThe problem is likely that D should be in m²/s, not mm²/s!")
print("\nConverting to m²/s (multiply by 1e-6):")
print("=" * 50)

for D_mm in D_values_mm2_s:
    D_m = D_mm * 1e-6  # Convert to m²/s
    print(f"\nD = {D_mm} mm²/s = {D_m} m²/s")
    print(f"  log(D) = {np.log(D_m)}")
    print(f"  B + log(D) = {B + np.log(D_m)}")
    print(f"  A / (B + log(D)) = {A / (B + np.log(D_m))}")
    temp_kelvin = A / (B + np.log(D_m))
    temp_celsius = temp_kelvin - 273.15
    print(f"  Temperature (K) = {temp_kelvin:.2f}")
    print(f"  Temperature (°C) = {temp_celsius:.2f}")

print("\n" + "=" * 50)
print("CONCLUSION: The diffusion coefficient needs to be converted from mm²/s to m²/s!")
print("The formula expects D in m²/s, but the code is providing it in mm²/s")