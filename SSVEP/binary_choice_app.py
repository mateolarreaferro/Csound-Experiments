"""Simple 2-choice BCI application using SSVEP"""

import numpy as np
import time
import threading
import sys
import os
from typing import Optional, Callable
import logging

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import config
from synthetic import SyntheticSSVEPGenerator
from filters import SSVEPFilters
from detector_psd import PSDDetector
from utils import TimeSeriesBuffer, StableVoteFilter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class BinaryChoiceBCI:
    """Simple 2-choice BCI interface using SSVEP"""
    
    def __init__(self, freq_left: float = 10.0, freq_right: float = 15.0,
                 use_synthetic: bool = True, callback: Optional[Callable] = None):
        """
        Initialize binary choice BCI
        
        Args:
            freq_left: Frequency for left/option 1 (Hz)
            freq_right: Frequency for right/option 2 (Hz)
            use_synthetic: Use synthetic data for testing
            callback: Function to call when choice is made (receives 'left' or 'right')
        """
        self.freq_left = freq_left
        self.freq_right = freq_right
        self.frequencies = [freq_left, freq_right]
        self.use_synthetic = use_synthetic
        self.callback = callback
        
        # System components
        self.acquisition = None
        self.filters = None
        self.detector = None
        self.data_buffer = None
        self.vote_filter = None
        
        # State
        self.is_running = False
        self.current_choice = None
        self.confidence = 0.0
        self.last_detection_time = None
        
        # Settings
        self.fs = 125.0  # Sampling rate
        self.window_sec = 2.0  # Analysis window
        self.step_sec = 0.2  # Update rate
        self.vote_hold_ms = 500  # Decision hold time
        self.min_snr = 1.5  # Minimum SNR threshold
        
    def setup(self) -> bool:
        """Initialize all components"""
        try:
            # Setup acquisition (synthetic for testing)
            if self.use_synthetic:
                self.acquisition = SyntheticSSVEPGenerator(fs=self.fs, n_channels=8)
                logger.info("Using synthetic data generator")
            else:
                # Real OpenBCI setup would go here
                logger.error("Real OpenBCI not implemented in this example")
                return False
            
            # Setup filters
            self.filters = SSVEPFilters(
                fs=self.fs,
                bandpass=(6.0, 45.0),
                notch_freq=60.0
            )
            
            # Setup detector
            self.detector = PSDDetector(
                fs=self.fs,
                target_freqs=self.frequencies,
                harmonics=2,
                snr_neighbor_bw=1.0,
                snr_exclude_bw=0.3
            )
            
            # Setup data buffer
            self.data_buffer = TimeSeriesBuffer(
                n_channels=8,
                buffer_duration=5.0,
                sampling_rate=self.fs
            )
            
            # Setup vote filter for stable decisions
            self.vote_filter = StableVoteFilter(hold_duration_ms=self.vote_hold_ms)
            
            logger.info(f"System initialized: Left={self.freq_left}Hz, Right={self.freq_right}Hz")
            return True
            
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            return False
    
    def start(self):
        """Start the BCI system"""
        if not self.setup():
            return False
        
        # Start data acquisition
        self.acquisition.start_streaming()
        
        # Start detection thread
        self.is_running = True
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
        logger.info("BCI system started")
        return True
    
    def stop(self):
        """Stop the BCI system"""
        self.is_running = False
        if self.acquisition:
            self.acquisition.stop_streaming()
        logger.info("BCI system stopped")
    
    def _detection_loop(self):
        """Main detection loop"""
        window_samples = int(self.window_sec * self.fs)
        
        while self.is_running:
            try:
                # Get new data
                new_data = self.acquisition.get_data()
                
                if new_data is not None and new_data.shape[1] > 0:
                    # Add to buffer
                    self.data_buffer.add_samples(new_data)
                    
                    # Get analysis window
                    analysis_data = self.data_buffer.get_latest_samples(window_samples)
                    
                    if analysis_data is not None:
                        # Apply filters
                        filtered_data = self.filters.apply_all(analysis_data, axis=1)
                        
                        # Detect SSVEP
                        result = self.detector.detect(filtered_data, return_all_scores=True)
                        
                        # Process detection
                        if result['snr'] >= self.min_snr:
                            detected_freq = result['frequency']
                            
                            # Map frequency to choice
                            if abs(detected_freq - self.freq_left) < 0.5:
                                choice = 'left'
                            elif abs(detected_freq - self.freq_right) < 0.5:
                                choice = 'right'
                            else:
                                choice = None
                            
                            if choice:
                                # Update stable vote
                                stable_choice = self.vote_filter.update(choice)
                                
                                if stable_choice and stable_choice != self.current_choice:
                                    self.current_choice = stable_choice
                                    self.confidence = result['confidence']
                                    self.last_detection_time = time.time()
                                    
                                    # Trigger callback only on change
                                    if self.callback:
                                        self.callback(stable_choice)
                                    
                                    logger.info(f"[CHOICE] {stable_choice.upper()} "
                                              f"(confidence: {self.confidence:.2f})")
                                    
                                    # Reset vote filter after selection
                                    self.vote_filter.reset()
                        else:
                            self.vote_filter.reset()
                
                time.sleep(self.step_sec)
                
            except Exception as e:
                logger.error(f"Detection error: {e}")
                time.sleep(0.5)
    
    def set_target(self, target: str):
        """Set the target for synthetic data (for testing)"""
        if self.use_synthetic and hasattr(self.acquisition, 'set_frequency'):
            if target == 'left':
                self.acquisition.set_frequency(self.freq_left)
                logger.info(f"Set synthetic target to LEFT ({self.freq_left}Hz)")
            elif target == 'right':
                self.acquisition.set_frequency(self.freq_right)
                logger.info(f"Set synthetic target to RIGHT ({self.freq_right}Hz)")
            elif target == 'none':
                self.acquisition.set_frequency(None)
                logger.info("Set synthetic target to NONE")
    
    def get_status(self) -> dict:
        """Get current system status"""
        return {
            'is_running': self.is_running,
            'current_choice': self.current_choice,
            'confidence': self.confidence,
            'last_detection': self.last_detection_time,
            'frequencies': {
                'left': self.freq_left,
                'right': self.freq_right
            }
        }


def demo_callback(choice: str):
    """Example callback function for demo"""
    print(f"\n>>> ACTION: User selected {choice.upper()} <<<\n")


def run_demo():
    """Run a demonstration of the 2-choice BCI"""
    print("\n" + "="*50)
    print("2-CHOICE BCI DEMO")
    print("="*50)
    print("This demo simulates a user making binary choices")
    print("using SSVEP by looking at flickering targets.")
    print("-"*50 + "\n")
    
    # Create BCI system
    bci = BinaryChoiceBCI(
        freq_left=10.0,
        freq_right=15.0,
        use_synthetic=True,
        callback=demo_callback
    )
    
    # Start system
    if not bci.start():
        print("Failed to start BCI system")
        return
    
    # Demo sequence
    demo_sequence = [
        ("left", 3),
        ("none", 2),
        ("right", 3),
        ("none", 2),
        ("left", 3),
        ("right", 3),
    ]
    
    try:
        print("Starting demo sequence...\n")
        
        for target, duration in demo_sequence:
            if target == "none":
                print(f"[DEMO] Resting state for {duration}s...")
            else:
                print(f"[DEMO] User looking at {target.upper()} for {duration}s...")
            
            bci.set_target(target)
            time.sleep(duration)
        
        print("\n" + "-"*50)
        print("Demo completed!")
        
        # Show final status
        status = bci.get_status()
        print(f"Final status:")
        print(f"  Last choice: {status['current_choice']}")
        print(f"  Confidence: {status['confidence']:.2f}")
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    
    finally:
        bci.stop()
        print("\nBCI system stopped")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='2-Choice BCI Application')
    parser.add_argument('--demo', action='store_true', help='Run demo with synthetic data')
    parser.add_argument('--left-freq', type=float, default=10.0, help='Left option frequency (Hz)')
    parser.add_argument('--right-freq', type=float, default=15.0, help='Right option frequency (Hz)')
    
    args = parser.parse_args()
    
    if args.demo:
        run_demo()
    else:
        print("Interactive mode:")
        print(f"Left: {args.left_freq}Hz, Right: {args.right_freq}Hz")
        print("Press Ctrl+C to exit\n")
        
        bci = BinaryChoiceBCI(
            freq_left=args.left_freq,
            freq_right=args.right_freq,
            use_synthetic=True,
            callback=lambda choice: print(f">>> Selected: {choice.upper()}")
        )
        
        if bci.start():
            try:
                # Simple interactive loop
                while True:
                    cmd = input("Enter target (left/right/none): ").strip().lower()
                    if cmd in ['left', 'right', 'none']:
                        bci.set_target(cmd)
                    elif cmd == 'status':
                        status = bci.get_status()
                        print(f"Status: {status}")
                    elif cmd == 'quit':
                        break
            except KeyboardInterrupt:
                pass
            finally:
                bci.stop()


if __name__ == "__main__":
    main()