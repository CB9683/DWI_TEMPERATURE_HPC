#!/bin/bash
#PBS -l ncpus=1,mem=4GB,walltime=00:05:00
#PBS -q normal
#PBS -P vp06
#PBS -l storage=gdata/vp06+scratch/vp06
#PBS -l wd
#PBS -N TestEnv
#PBS -o logs/test_environment.out
#PBS -e logs/test_environment.err

# Test script to verify conda environment setup

set -e

echo "=========================================="
echo "Environment Test Started at $(date)"
echo "=========================================="

# Load configuration
CONFIG_FILE="pipeline_config.json"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "ERROR: Configuration file ${CONFIG_FILE} not found!"
    exit 1
fi

# Get conda environment path
CONDA_ENV_PATH=$(python3 -c "import json; print(json.load(open('${CONFIG_FILE}'))['paths']['conda_env'])")
echo "Conda environment path: ${CONDA_ENV_PATH}"

# Check if the environment exists
if [ ! -d "${CONDA_ENV_PATH}" ]; then
    echo "ERROR: Conda environment not found at ${CONDA_ENV_PATH}"
    exit 1
fi

# Activate conda
echo "Activating conda..."
source "${CONDA_ENV_PATH%/*/*}/etc/profile.d/conda.sh"
conda activate "${CONDA_ENV_PATH}"

echo "Active conda environment: $CONDA_PREFIX"
echo "Python location: $(which python)"
echo "Python version: $(python --version)"

# Test package imports
echo ""
echo "Testing package imports..."
python << EOF
import sys
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print()

packages = ['numpy', 'pandas', 'scipy', 'matplotlib', 'seaborn', 'nibabel']
for pkg in packages:
    try:
        module = __import__(pkg)
        version = getattr(module, '__version__', 'version not available')
        print(f"✓ {pkg}: {version}")
    except ImportError as e:
        print(f"✗ {pkg}: FAILED - {e}")
        sys.exit(1)

print("\nAll packages imported successfully!")
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "Environment test PASSED!"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "Environment test FAILED!"
    echo "=========================================="
    exit 1
fi