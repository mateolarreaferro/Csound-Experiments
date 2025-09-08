# SSVEP BCI System

A modular Brain-Computer Interface system based on Steady-State Visual Evoked Potentials (SSVEP) for OpenBCI Cyton+Daisy (16 channels).

## Overview

This system implements a real-time SSVEP-based BCI that detects which visual stimulus a user is focusing on by analyzing their EEG signals. SSVEP occurs when the brain synchronizes with flickering visual stimuli at specific frequencies.

### Key Features

- **Real-time SSVEP Detection**: Multiple classification methods (CCA, FBCCA, PSDA)
- **16-Channel Support**: Optimized for OpenBCI Cyton+Daisy board
- **Flexible Stimulus Presentation**: Configurable frequencies (6-15 Hz) and layouts
- **High Performance**: Precise frequency control with vsync support
- **Modular Architecture**: Easy to extend and customize
- **Multiple Classification Methods**: CCA, Filter Bank CCA, Power Spectral Density Analysis
- **Real-time Processing**: Low-latency detection with configurable windows
- **Comprehensive Metrics**: ITR, accuracy, SNR, and frequency-specific performance

## Hardware Requirements

### OpenBCI Setup
- OpenBCI Cyton + Daisy board (16 channels)
- Wet or dry electrode EEG cap
- 16 electrodes positioned according to 10-20 system:
  - **Primary channels**: O1, O2, Oz (occipital - most important for SSVEP)
  - **Secondary channels**: PO3, PO4, POz, P3, P4, Pz (parietal-occipital)
  - **Additional channels**: CP1, CP2, Cz, FC1, FC2, P7, P8
  - **Reference**: Earlobe or mastoid
  - **Ground**: Opposite earlobe or forehead

### Electrode Placement
The system emphasizes occipital and parietal-occipital sites for optimal SSVEP detection, as visual cortex activity is strongest in these regions.

## Installation

### From source
```bash
git clone https://github.com/yourusername/ssvep-bci.git
cd ssvep-bci
pip install -r requirements.txt
pip install -e .
```

## Quick Start

### 1. Hardware Setup
1. Connect your OpenBCI Cyton + Daisy board
2. Apply EEG electrodes according to the 16-channel montage
3. Verify electrode impedances are below 5 kΩ

### 2. Calibration
Run calibration to collect training data:
```bash
python run_ssvep_calibration.py --port /dev/ttyUSB0 --trials 10
```

### 3. Online BCI
Run the real-time SSVEP BCI:
```bash
python run_ssvep_online.py --port /dev/ttyUSB0 --model data/model_*.pkl
```

## System Architecture

### Core Modules

#### Acquisition (`acquisition.py`)
- Real-time EEG data streaming from OpenBCI Cyton+Daisy
- Circular buffer for real-time access
- Data recording in multiple formats (EDF, CSV, FIF)
- Impedance estimation

#### SSVEP Preprocessing (`ssvep_preprocessing.py`)
- Bandpass filtering (3-45 Hz) for SSVEP frequencies
- Notch filtering (50/60 Hz)
- Spatial filtering (CAR, occipital emphasis)
- Artifact rejection (threshold-based and ICA)
- Frequency-specific filtering for each target

#### SSVEP Classification (`ssvep_classifier.py`)
- **CCA**: Canonical Correlation Analysis between EEG and reference signals
- **FBCCA**: Filter Bank CCA with multiple frequency bands
- **PSDA**: Power Spectral Density Analysis at target frequencies
- **Ensemble**: Weighted combination of methods

#### SSVEP Stimulus (`ssvep_stimulus.py`)
- Precise frequency control (6.0, 7.5, 8.57, 10.0, 12.0, 15.0 Hz)
- Multiple stimulus types (checkerboard, square, sinusoidal)
- Real-time phase tracking
- Pygame-based rendering with vsync support

### Configuration

Edit `ssvep_bci/config/settings.py` to customize:

```python
# Example key parameters
STIMULUS = {
    'frequencies': [6.0, 7.5, 8.57, 10.0, 12.0, 15.0],  # Hz
    'n_targets': 6,
    'stimulus_type': 'checkerboard',  # or 'square', 'sinusoidal'
}

CLASSIFIER = {
    'type': 'CCA',  # or 'FBCCA', 'PSDA', 'ensemble'
    'n_harmonics': 3,
    'window_length': 4.0,  # seconds
}

REALTIME = {
    'min_confidence': 0.6,
    'decision_interval': 500,  # ms
}
```

## Usage Examples

### Python API

```python
from p300_speller.modules import CalibrationSession
from p300_speller.config import settings

# Run calibration
session = CalibrationSession(settings.__dict__)
session.run_calibration()

# Load and use for spelling
session.load_calibration('SESSION_ID')
```

### Advanced Configuration

```python
# Custom classifier settings
config = settings.__dict__.copy()
config['CLASSIFIER']['type'] = 'MDM'
config['CLASSIFIER']['xdawn_components'] = 8

# Custom preprocessing
config['PREPROCESSING']['bandpass'] = (0.5, 30)
config['PREPROCESSING']['use_ica'] = True
```

## Performance Optimization

### Hardware Considerations
- Maintain electrode impedances below 5 kΩ
- Use a stable, artifact-free recording environment
- Ensure proper grounding and shielding

### Algorithm Tuning
- **xDAWN components**: Start with 6, increase for more channels
- **Sequence count**: Balance speed vs accuracy (5-15 sequences)
- **Flash timing**: 100ms flash, 75ms ISI works well for most users
- **Stopping threshold**: 0.9 provides good speed/accuracy tradeoff

## Evaluation Metrics

The system provides comprehensive performance evaluation:

- **Character Accuracy**: Percentage of correctly identified characters
- **Information Transfer Rate (ITR)**: Bits per minute accounting for accuracy and speed
- **Typing Speed**: Characters per minute
- **Selection Time**: Average time per character
- **False Positive/Negative Rates**: Error analysis
- **Confusion Matrix**: Per-character error patterns

## Extending the System

### Adding New Classifiers

```python
from p300_speller.modules.classifier import BaseClassifier

class MyClassifier(BaseClassifier):
    def fit(self, X, y):
        # Implementation
        pass
    
    def predict(self, X):
        # Implementation
        pass
```

### Custom Feature Extraction

```python
class MyFeatures(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        return self
    
    def transform(self, X):
        # Custom feature computation
        return features
```

### New Stimulus Paradigms

```python
def my_paradigm(self):
    # Define custom flash sequences
    sequence = [['A', 'B'], ['C', 'D']]  # Example grouping
    return sequence
```

## Troubleshooting

### Common Issues

1. **No OpenBCI connection**
   - Check serial port and permissions
   - Verify board power and USB connection

2. **Poor classification accuracy**
   - Check electrode impedances
   - Increase calibration data
   - Adjust preprocessing parameters

3. **High artifact levels**
   - Enable ICA preprocessing
   - Improve electrode preparation
   - Reduce environmental noise

### Debug Mode
Enable verbose output:
```bash
p300-calibrate --debug --dry-run  # Test without hardware
```

## Citation

If you use this software in your research, please cite:

```bibtex
@software{p300_speller,
  title={P300 Speller BCI System},
  author={P300 BCI Development Team},
  year={2024},
  url={https://github.com/p300-bci/p300-speller}
}
```

## Contributing

We welcome contributions! Please see `CONTRIBUTING.md` for guidelines.

### Development Setup
```bash
git clone https://github.com/p300-bci/p300-speller.git
cd p300-speller
pip install -e ".[dev]"
pre-commit install
```

## License

This project is licensed under the MIT License - see `LICENSE` file for details.

## Acknowledgments

- OpenBCI community for hardware support
- MNE-Python developers for EEG processing tools
- P300 BCI research community for foundational algorithms

## Support

- **Documentation**: https://p300-speller.readthedocs.io/
- **Issues**: https://github.com/p300-bci/p300-speller/issues
- **Discussions**: https://github.com/p300-bci/p300-speller/discussions

---

**Note**: This is a research-grade system. For clinical applications, additional validation and regulatory approval may be required.