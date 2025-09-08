#!/usr/bin/env python3
"""
SSVEP Online BCI Script
Real-time SSVEP detection and control
"""

import sys
import time
import numpy as np
from pathlib import Path
import argparse
import pickle
import threading
from collections import deque

# Add project to path
sys.path.append(str(Path(__file__).parent))

from ssvep_bci.config import settings
from ssvep_bci.modules.acquisition import SSVEPAcquisition
from ssvep_bci.modules.ssvep_stimulus import SSVEPStimulus
from ssvep_bci.modules.ssvep_preprocessing import SSVEPPreprocessor
from ssvep_bci.modules.ssvep_classifier import SSVEPClassifier


class SSVEPOnlineSystem:
    """
    Real-time SSVEP BCI system
    """
    
    def __init__(self, model_path=None):
        """
        Initialize online SSVEP system
        
        Args:
            model_path: Path to trained classifier model
        """
        self.config = settings.__dict__
        
        # Initialize components
        self.acquisition = SSVEPAcquisition(self.config)
        self.preprocessor = SSVEPPreprocessor(self.config)
        self.stimulus = None
        self.classifier = None
        
        # Load trained model if provided
        if model_path and Path(model_path).exists():
            with open(model_path, 'rb') as f:
                self.classifier = pickle.load(f)
            print(f"Loaded model from: {model_path}")
        else:
            # Use default CCA classifier
            self.classifier = SSVEPClassifier(self.config)
            print("Using default CCA classifier (no training required)")
        
        # Real-time processing variables
        self.processing_thread = None
        self.stop_processing = threading.Event()
        
        # Performance metrics
        self.predictions = deque(maxlen=100)
        self.confidence_history = deque(maxlen=100)
        self.last_prediction = None
        self.last_confidence = 0.0
        
    def initialize(self, serial_port=None):
        """
        Initialize hardware and display
        
        Args:
            serial_port: OpenBCI serial port
            
        Returns:
            Success status
        """
        print("\nInitializing SSVEP online system...")
        
        # Initialize OpenBCI
        if not self.acquisition.initialize_board(serial_port):
            print("Failed to initialize OpenBCI board")
            return False
        
        # Initialize stimulus with marker callback
        self.stimulus = SSVEPStimulus(
            self.config,
            marker_callback=self.acquisition.insert_marker
        )
        
        if not self.stimulus.initialize_display():
            print("Failed to initialize display")
            return False
        
        # Start streaming
        if not self.acquisition.start_streaming():
            print("Failed to start streaming")
            return False
        
        print("System initialized successfully")
        return True
    
    def start_processing(self):
        """Start real-time processing thread"""
        self.stop_processing.clear()
        self.processing_thread = threading.Thread(target=self._processing_loop)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        print("Real-time processing started")
    
    def stop_processing(self):
        """Stop real-time processing"""
        self.stop_processing.set()
        if self.processing_thread:
            self.processing_thread.join(timeout=2.0)
        print("Real-time processing stopped")
    
    def _processing_loop(self):
        """Main processing loop for real-time SSVEP detection"""
        window_length = self.config['CLASSIFIER']['window_length']
        update_interval = self.config['REALTIME']['update_interval'] / 1000.0
        
        while not self.stop_processing.is_set():
            try:
                # Get recent EEG data
                eeg_data, timestamps = self.acquisition.get_realtime_data(window_length)
                
                if eeg_data.size > 0:
                    # Preprocess
                    processed_data = self.preprocessor.process(eeg_data)
                    
                    # Classify
                    target_idx, confidence = self.classifier.predict(processed_data)
                    
                    # Store results
                    self.last_prediction = target_idx
                    self.last_confidence = confidence
                    self.predictions.append(target_idx)
                    self.confidence_history.append(confidence)
                    
                    # Check confidence threshold
                    if confidence > self.config['REALTIME']['min_confidence']:
                        # Valid detection
                        command = self.stimulus.commands[target_idx]
                        frequency = self.stimulus.frequencies[target_idx]
                        
                        print(f"\rDetected: {command} ({frequency:.1f} Hz) "
                              f"[Confidence: {confidence:.2%}]", end='')
                        
                        # Execute command (placeholder)
                        self.execute_command(command)
                    else:
                        print(f"\rWaiting for detection... "
                              f"[Best: {self.stimulus.commands[target_idx]} "
                              f"@ {confidence:.2%}]", end='')
                
                time.sleep(update_interval)
                
            except Exception as e:
                print(f"\nProcessing error: {e}")
                time.sleep(0.1)
    
    def execute_command(self, command):
        """
        Execute detected command
        
        Args:
            command: Detected command string
        """
        # This is a placeholder for actual command execution
        # You could integrate with robotics, wheelchair control, etc.
        
        # Insert marker for detected command
        if self.acquisition and command in self.stimulus.marker_codes:
            self.acquisition.insert_marker(self.stimulus.marker_codes[command])
    
    def get_classification_callback(self):
        """
        Get callback function for stimulus module
        
        Returns:
            Classification callback function
        """
        def callback():
            if self.last_prediction is not None:
                return (self.last_prediction, self.last_confidence)
            return None
        
        return callback
    
    def calculate_accuracy(self):
        """
        Calculate recent classification accuracy
        
        Returns:
            Accuracy percentage
        """
        if len(self.predictions) < 10:
            return 0.0
        
        # Calculate consistency of predictions
        recent = list(self.predictions)[-10:]
        most_common = max(set(recent), key=recent.count)
        consistency = recent.count(most_common) / len(recent)
        
        return consistency * 100
    
    def calculate_itr(self):
        """
        Calculate Information Transfer Rate
        
        Returns:
            ITR in bits per minute
        """
        if len(self.predictions) < 2:
            return 0.0
        
        accuracy = self.calculate_accuracy() / 100.0
        n_targets = len(self.stimulus.frequencies)
        selection_time = self.config['CLASSIFIER']['window_length']
        
        return self.classifier.calculate_itr(accuracy, n_targets, selection_time)
    
    def run(self):
        """Run online SSVEP BCI system"""
        print("\n" + "="*60)
        print("SSVEP ONLINE BCI SYSTEM")
        print("="*60)
        print("\nCommands:")
        for i, (freq, cmd) in enumerate(zip(self.stimulus.frequencies, 
                                           self.stimulus.commands)):
            print(f"  {i+1}. {cmd:10s} @ {freq:5.1f} Hz")
        print("\nControls:")
        print("  SPACE - Start/stop stimulation")
        print("  1-6   - Test specific frequency")
        print("  R     - Show real-time metrics")
        print("  ESC   - Exit")
        print("="*60)
        
        # Start processing
        self.start_processing()
        
        # Run stimulus presentation with classification callback
        try:
            self.stimulus.run_online(
                classifier_callback=self.get_classification_callback()
            )
        except KeyboardInterrupt:
            print("\n\nSystem interrupted by user")
        
        # Stop processing
        self.stop_processing()
        
        # Show final metrics
        self.show_metrics()
    
    def show_metrics(self):
        """Display performance metrics"""
        print("\n" + "="*60)
        print("PERFORMANCE METRICS")
        print("="*60)
        
        if len(self.predictions) > 0:
            print(f"Total predictions: {len(self.predictions)}")
            print(f"Accuracy: {self.calculate_accuracy():.1f}%")
            print(f"ITR: {self.calculate_itr():.1f} bits/min")
            print(f"Average confidence: {np.mean(list(self.confidence_history)):.2%}")
            
            # Show prediction distribution
            print("\nPrediction distribution:")
            for i, cmd in enumerate(self.stimulus.commands):
                count = list(self.predictions).count(i)
                percentage = (count / len(self.predictions)) * 100
                print(f"  {cmd:10s}: {count:3d} ({percentage:5.1f}%)")
        else:
            print("No predictions made")
        
        print("="*60)
    
    def cleanup(self):
        """Clean up resources"""
        self.stop_processing()
        
        if self.stimulus:
            self.stimulus.cleanup()
        
        if self.acquisition:
            self.acquisition.cleanup()
        
        print("\nSystem cleaned up")


def main():
    parser = argparse.ArgumentParser(description='SSVEP Online BCI System')
    parser.add_argument('--port', type=str, help='OpenBCI serial port')
    parser.add_argument('--model', type=str, help='Path to trained model')
    parser.add_argument('--record', action='store_true', 
                       help='Record session data')
    
    args = parser.parse_args()
    
    # Create online system
    system = SSVEPOnlineSystem(model_path=args.model)
    
    try:
        # Initialize hardware
        if not system.initialize(serial_port=args.port):
            print("Failed to initialize system")
            return
        
        # Start recording if requested
        if args.record:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"online_{timestamp}"
            system.acquisition.start_recording(filename, 'online')
            print(f"Recording to: {filename}")
        
        # Run system
        system.run()
        
        # Stop recording
        if args.record:
            recording_file = system.acquisition.stop_recording()
            print(f"\nRecording saved to: {recording_file}")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        system.cleanup()


if __name__ == "__main__":
    main()