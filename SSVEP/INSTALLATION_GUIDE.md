# Installation Guide - SSVEP 2-Choice BCI System

## Quick Setup (Recommended)

### 1. Automatic Setup Script

```bash
# Make setup script executable and run it
chmod +x setup_venv.sh
./setup_venv.sh
```

This script will:
- Check Python version (3.10+ required)
- Create virtual environment
- Install all dependencies
- Run verification tests

### 2. Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements-minimal.txt  # Core functionality only
# or: pip install -r requirements.txt     # Full installation (slower)

# Verify installation
python verify_installation.py
```

## Requirements Files

### `requirements-minimal.txt` (Recommended for testing)
- Core scientific computing (numpy, scipy, matplotlib)
- BrainFlow for OpenBCI hardware
- **Fast installation** (~2-3 minutes)
- **Core BCI functionality only** (no visual stimulus)

### `requirements.txt` (Full installation)
- Everything in minimal + PsychoPy for visual stimulus
- **Slow installation** (10-15 minutes)
- **Complete functionality**

## Verification

After installation, run the verification script:

```bash
source venv/bin/activate
python verify_installation.py
```

Expected output:
```
🎉 CORE SYSTEM: ✅ WORKING

Available features:
• Binary choice BCI with synthetic data
• Real-time SSVEP detection  
• Signal processing and filtering
• OpenBCI hardware support (when connected)
```

## Test Commands

Once installed, test the system:

```bash
# Activate virtual environment
source venv/bin/activate

# Test 1: Binary choice demo (no hardware needed)
python binary_choice_app.py --demo

# Test 2: SSVEP detection with synthetic data
python run_ssvep.py --synthetic 10.0 --duration 5

# Test 3: Visual stimulus (requires PsychoPy)
python run_binary_stimulus.py
```

## Troubleshooting

### Python Version Issues
- **Required**: Python 3.10 or higher
- **Check version**: `python3 --version`
- **macOS**: Use `python3` instead of `python`

### Installation Fails
1. **Try minimal installation first**:
   ```bash
   pip install -r requirements-minimal.txt
   ```

2. **Update pip**:
   ```bash
   pip install --upgrade pip
   ```

3. **Clear pip cache**:
   ```bash
   pip cache purge
   ```

### Import Errors
- **Activate virtual environment**: `source venv/bin/activate`
- **Add current directory to Python path**: `export PYTHONPATH=.:src:$PYTHONPATH`
- **Run from project root directory**

### PsychoPy Issues
- **Skip for now**: Core system works without PsychoPy
- **Alternative**: Install pygame for basic graphics
- **Full install**: Can take 15+ minutes due to dependencies

## Dependencies Overview

### Core Dependencies (minimal)
- **numpy** - Numerical computing
- **scipy** - Signal processing
- **matplotlib** - Plotting and visualization
- **brainflow** - OpenBCI hardware interface

### Optional Dependencies (full)
- **psychopy** - Professional stimulus presentation
- **pygame** - Simple graphics alternative
- **PyQt5** - GUI framework

### System Requirements
- **OS**: Windows, macOS, Linux
- **Python**: 3.10+
- **RAM**: 2GB+ (4GB+ recommended with PsychoPy)
- **Hardware**: OpenBCI Cyton/Cyton+Daisy (optional for testing)

## Next Steps

After successful installation:

1. **Read the guide**: `2_CHOICE_BCI_GUIDE.md`
2. **Run demos**: Test with synthetic data
3. **Hardware setup**: Connect OpenBCI if available
4. **Customize**: Modify frequencies and parameters for your needs

## Getting Help

- **Verification fails**: Run `python verify_installation.py` for diagnostics
- **Import errors**: Check virtual environment activation
- **Hardware issues**: See OpenBCI setup guide
- **Performance issues**: Try minimal installation first