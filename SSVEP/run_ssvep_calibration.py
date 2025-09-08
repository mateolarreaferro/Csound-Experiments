#!/usr/bin/env python3
"""
SSVEP Calibration Script
Collects training data for SSVEP BCI system
"""

import sys
import time
import numpy as np
from pathlib import Path
from datetime import datetime
import argparse

# Add project to path
sys.path.append(str(Path(__file__).parent))

from ssvep_bci.config import settings
from ssvep_bci.modules.acquisition import SSVEPAcquisition
from ssvep_bci.modules.ssvep_stimulus import SSVEPStimulus
from ssvep_bci.modules.ssvep_preprocessing import SSVEPPreprocessor
from ssvep_bci.modules.ssvep_classifier import SSVEPClassifier


def run_calibration(serial_port=None, n_trials=10):
    """
    Run SSVEP calibration session
    
    Args:
        serial_port: OpenBCI serial port
        n_trials: Number of trials per frequency
    """
    print("="*60)
    print("SSVEP BCI Calibration")
    print("="*60)
    
    # Initialize components
    print("\n1. Initializing data acquisition...")
    acquisition = SSVEPAcquisition(settings.__dict__)
    
    if not acquisition.initialize_board(serial_port):
        print("Failed to initialize OpenBCI board")
        return
    
    print("\n2. Checking electrode impedances...")
    impedances = acquisition.get_impedances()
    print("Impedances (approximate):")
    for ch, imp in impedances.items():
        status = "✓" if imp < 5000 else "⚠" if imp < 10000 else "✗"
        print(f"  {ch}: {imp:.0f} Ω {status}")
    
    # Initialize stimulus
    print("\n3. Initializing stimulus presentation...")
    stimulus = SSVEPStimulus(
        settings.__dict__,
        marker_callback=acquisition.insert_marker
    )
    
    if not stimulus.initialize_display():
        print("Failed to initialize display")
        acquisition.cleanup()
        return
    
    # Initialize preprocessing
    print("\n4. Setting up signal processing...")
    preprocessor = SSVEPPreprocessor(settings.__dict__)
    
    # Start data streaming
    print("\n5. Starting EEG streaming...")
    if not acquisition.start_streaming():
        print("Failed to start streaming")
        stimulus.cleanup()
        acquisition.cleanup()
        return
    
    # Wait for signal to stabilize
    print("\nWaiting for signal to stabilize...")
    time.sleep(3)
    
    # Start recording
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"calibration_{timestamp}"
    print(f"\n6. Starting recording: {filename}")
    acquisition.start_recording(filename, 'calibration')
    
    # Instructions
    print("\n" + "="*60)
    print("CALIBRATION INSTRUCTIONS:")
    print("- Focus on the indicated target when it appears")
    print("- Try to minimize eye movements and blinks")
    print("- Stay relaxed and maintain focus")
    print("- Press ESC at any time to abort")
    print("="*60)
    
    input("\nPress ENTER to start calibration...")
    
    # Run calibration
    print("\n7. Running calibration trials...")
    try:
        stimulus.run_calibration(n_trials_per_target=n_trials)
    except KeyboardInterrupt:
        print("\nCalibration interrupted by user")
    
    # Stop recording
    print("\n8. Stopping recording...")
    recording_file = acquisition.stop_recording()
    print(f"Data saved to: {recording_file}")
    
    # Process calibration data for training
    print("\n9. Processing calibration data...")
    training_data = process_calibration_data(
        acquisition, preprocessor, stimulus.frequencies
    )
    
    # Train classifier
    if training_data:
        print("\n10. Training classifier...")
        classifier = SSVEPClassifier(settings.__dict__)
        classifier.train(training_data)
        
        # Save trained model
        import pickle
        model_file = Path(settings.DATA_STORAGE['data_dir']) / f"model_{timestamp}.pkl"
        with open(model_file, 'wb') as f:
            pickle.dump(classifier, f)
        print(f"Model saved to: {model_file}")
    
    # Cleanup
    print("\n11. Cleaning up...")
    stimulus.cleanup()
    acquisition.cleanup()
    
    print("\n" + "="*60)
    print("Calibration completed successfully!")
    print("="*60)


def process_calibration_data(acquisition, preprocessor, frequencies):
    """
    Process recorded calibration data
    
    Args:
        acquisition: Acquisition object with recorded data
        preprocessor: Preprocessing object
        frequencies: List of SSVEP frequencies
        
    Returns:
        Dictionary of training data per frequency
    """
    training_data = {freq: [] for freq in frequencies}
    
    # This is a placeholder - in practice, you'd load and segment the recorded data
    # based on markers and extract epochs for each frequency
    
    return training_data


def main():
    parser = argparse.ArgumentParser(description='SSVEP BCI Calibration')
    parser.add_argument('--port', type=str, help='OpenBCI serial port')
    parser.add_argument('--trials', type=int, default=10,
                       help='Number of trials per frequency')
    
    args = parser.parse_args()
    
    try:
        run_calibration(serial_port=args.port, n_trials=args.trials)
    except Exception as e:
        print(f"\nError during calibration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()