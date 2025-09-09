#!/bin/bash
# Setup script for SSVEP 2-Choice BCI System

echo "==============================================="
echo "SSVEP 2-Choice BCI System Setup"
echo "==============================================="

# Check if Python 3.10+ is available
python_version=$(python3 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+' | head -1)
major_version=$(echo $python_version | cut -d. -f1)
minor_version=$(echo $python_version | cut -d. -f2)

if [[ $major_version -lt 3 ]] || [[ $major_version -eq 3 && $minor_version -lt 10 ]]; then
    echo "❌ Python 3.10 or higher is required. Found: $python_version"
    exit 1
fi

echo "✅ Python version: $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo "⚠️  Virtual environment already exists. Removing old one..."
    rm -rf venv
fi

python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "❌ Failed to create virtual environment"
    exit 1
fi

echo "✅ Virtual environment created"

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo ""
echo "Installing dependencies..."
echo "This may take a few minutes..."

# First try full requirements
if pip install -r requirements.txt; then
    echo "✅ Full installation successful"
    INSTALLATION_TYPE="full"
else
    echo "⚠️  Full installation failed, trying minimal installation..."
    if pip install -r requirements-minimal.txt; then
        echo "✅ Minimal installation successful"
        echo "⚠️  Visual stimulus features will not be available"
        INSTALLATION_TYPE="minimal"
    else
        echo "❌ Even minimal installation failed"
        exit 1
    fi
fi

# Test imports
echo ""
echo "Testing imports..."
python -c "
import sys
sys.path.append('src')
try:
    import numpy, scipy, matplotlib
    import brainflow
    from src import config, acquisition, filters, detector_psd, utils, synthetic
    print('✅ Core imports successful')
    core_success = True
except Exception as e:
    print(f'❌ Core imports failed: {e}')
    core_success = False

try:
    import psychopy
    print('✅ PsychoPy available')
    psychopy_available = True
except:
    print('⚠️  PsychoPy not available (visual stimulus disabled)')
    psychopy_available = False

print('')
if core_success:
    print('🎉 SETUP SUCCESSFUL!')
    print('')
    print('Quick test commands:')
    print('  python binary_choice_app.py --demo')
    print('  python run_ssvep.py --synthetic 10.0 --duration 10')
    if psychopy_available:
        print('  python run_binary_stimulus.py --test')
    print('')
    print('To activate this environment later:')
    print('  source venv/bin/activate')
else:
    print('❌ Setup incomplete - core functionality not working')
    sys.exit(1)
"

echo ""
echo "==============================================="
echo "Setup Complete!"
echo "==============================================="