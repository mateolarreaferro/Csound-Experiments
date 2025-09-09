# OpenBCI-Csound Experiments

This directory contains experimental Csound scripts for processing different types of OpenBCI data streams, plus a Python simulator to test them without the unreliable OpenBCI GUI.

## 📁 Files Overview

### Csound Scripts
- **`SimpleBCI.csd`** (main project) - Alpha band power from 16 channels
- **`BCI_Focus.csd`** - Focus/attention metrics 
- **`BCI_AccelAux.csd`** - Accelerometer (X,Y,Z) and auxiliary sensor data
- **`BCI_BandPower.csd`** - Individual brain wave band powers (delta, theta, alpha, beta, gamma)
- **`BCI_FFT.csd`** - Real-time FFT analysis of raw EEG signals
- **`BCI_Base.csd`** - Base template with shared functionality

### Python Simulator
- **`openbci_simulator.py`** - Reliable data simulator to replace OpenBCI GUI
- **`requirements.txt`** - Python dependencies
- **`README.md`** - This documentation

## 🚀 Quick Start

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Data Simulation
```bash
# Simulate all data types
python openbci_simulator.py --mode all

# Simulate specific data type
python openbci_simulator.py --mode focus
python openbci_simulator.py --mode accel
python openbci_simulator.py --mode bandpower
python openbci_simulator.py --mode fft

# Run for specific duration
python openbci_simulator.py --mode all --duration 60
```

### 3. Run Csound Scripts
In separate terminals, run the Csound scripts:
```bash
# Focus-based synthesis
csound BCI_Focus.csd

# Accelerometer-based synthesis  
csound BCI_AccelAux.csd

# Band power analysis
csound BCI_BandPower.csd

# FFT analysis
csound BCI_FFT.csd
```

## 🎛️ Data Streams & Ports

| Data Type | OSC Address | Port | Script |
|-----------|------------|------|--------|
| Band Power | `/openbci/band-power/{channel}` | 5003 | `BCI_BandPower.csd` |
| Focus | `/openbci/focus[/{channel}]` | 5003 | `BCI_Focus.csd` |
| Accelerometer | `/openbci/accel` | 5004 | `BCI_AccelAux.csd` |
| Auxiliary | `/openbci/aux/{channel}` | 5004 | `BCI_AccelAux.csd` |
| Raw EEG | `/openbci/eeg/{channel}` | 5005 | `BCI_FFT.csd` |

## 🎹 MIDI Control

All scripts support MIDI input for triggering synthesis:
- **MIDI Channel 1** triggers the synthesis instruments
- **MIDI CC 21-24** control metro speeds (optional)
- No MIDI controller? The scripts work fine with default values

## 🎵 Synthesis Architecture  

All scripts share the same core synthesis engine:
- **8 oscillators** modulated by BCI data
- **3 waveforms**: sine, square, saw
- **Reverb & delay** effects processing
- **16-channel BCI mapping** to musical parameters

Each script maps its unique data streams intelligently:

### 🎯 BCI_Focus.csd
- Maps focus values (0-100) to all 16 synthesis channels
- Higher focus = more active synthesis

### 📱 BCI_AccelAux.csd  
- X,Y,Z axes → channels 1-3
- 8 auxiliary sensors → channels 4-11  
- Motion derivatives → channels 12-16

### 🧠 BCI_BandPower.csd
- Delta waves → channels 1-2 (bass foundation)
- Theta waves → channels 3-4 (creativity)  
- Alpha waves → channels 5-8 (main arpeggios)
- Beta waves → channels 9-12 (active thinking)
- Gamma waves → channels 13-16 (high cognition)

### 📊 BCI_FFT.csd
- Real-time spectral analysis using resonant filters
- Frequency band extraction → RMS analysis → synthesis control
- Delta, theta, alpha, beta, gamma band mapping

## 🔧 Troubleshooting

### "ModuleNotFoundError: No module named 'pythonosc'"
```bash
pip install python-osc
```

### "No OSC data received" in Csound
1. Check that the Python simulator is running
2. Verify port numbers match (5003-5005)
3. Check firewall/network settings

### Synthesis sounds the same
- The BCI data ranges are small - try increasing the scaling factors in the Csound code
- Make sure MIDI input is working to trigger notes
- Monitor the console output to see if data is being received

## 🎪 Performance Tips

- **Start simple**: Begin with `BCI_Focus.csd` - it's the most straightforward
- **Monitor data flow**: Watch console output to verify OSC data reception  
- **Adjust scaling**: Modify the `* 0.0001` scaling factors for more/less modulation
- **Use MIDI**: Connect a MIDI keyboard for more musical control
- **Combine modes**: Run multiple Csound scripts simultaneously for layered textures

## 🚨 Why This Simulator?

The OpenBCI GUI can be unreliable and crash-prone. This Python simulator:
- ✅ **Stable** - No crashes or connection drops
- ✅ **Realistic** - Generates biologically-plausible data patterns  
- ✅ **Flexible** - Easy to modify data characteristics
- ✅ **Debuggable** - Console output shows exactly what's being sent
- ✅ **Controllable** - Set duration, specific modes, data ranges

Perfect for developing and testing your BCI-music systems!