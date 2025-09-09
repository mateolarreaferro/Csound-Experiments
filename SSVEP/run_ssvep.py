"""Real-time SSVEP detection system for OpenBCI Cyton/Cyton+Daisy"""

import numpy as np
import time
import logging
import threading
import sys
import os
from typing import Optional, List
import argparse

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import config
from acquisition import OpenBCIAcquisition
from synthetic import SyntheticSSVEPGenerator, synth_ssvep
from filters import SSVEPFilters
from detector_psd import PSDDetector
from utils import TimeSeriesBuffer, StableVoteFilter, format_detection_output

# Configure logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL), 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SSVEPSystem:
    """Real-time SSVEP detection system"""
    
    def __init__(self, use_synthetic: bool = False, synthetic_freq: Optional[float] = None):
        """
        Initialize SSVEP system
        
        Args:
            use_synthetic: Whether to use synthetic data instead of OpenBCI
            synthetic_freq: Frequency for synthetic data (if use_synthetic=True)
        """
        self.use_synthetic = use_synthetic
        self.synthetic_freq = synthetic_freq
        
        # Components
        self.acquisition = None
        self.filters = None
        self.detector = None
        self.data_buffer = None
        self.vote_filter = None
        
        # State
        self.is_running = False
        self.sampling_rate = None
        self.num_channels = None
        self.detection_thread = None
        
        # Statistics
        self.detection_count = 0
        self.start_time = None
        self.last_detection_time = None
        
        logger.info(f"SSVEP System initialized: synthetic={use_synthetic}, "
                   f"synthetic_freq={synthetic_freq}")
    
    def setup(self) -> bool:
        """Setup all system components"""
        try:
            # Setup data acquisition
            if self.use_synthetic:
                self.acquisition = SyntheticSSVEPGenerator(fs=125.0, n_channels=16)
                self.sampling_rate = 125.0
                self.num_channels = 16
                
                if self.synthetic_freq is not None:
                    self.acquisition.set_frequency(self.synthetic_freq)
                    logger.info(f"Set synthetic frequency to {self.synthetic_freq} Hz")
                
            else:
                self.acquisition = OpenBCIAcquisition(
                    board_id=config.BOARD_ID, 
                    serial_port=config.SERIAL_PORT
                )
                
                if not self.acquisition.connect():
                    logger.error("Failed to connect to OpenBCI board")
                    return False
                
                # Get board info
                board_info = self.acquisition.get_board_info()
                self.sampling_rate = board_info['sampling_rate']
                self.num_channels = board_info['num_channels']
            
            logger.info(f"Sampling rate: {self.sampling_rate} Hz, EEG channels: {self.num_channels}")
            
            # Setup signal processing
            self.filters = SSVEPFilters(
                fs=self.sampling_rate,
                bandpass=config.BANDPASS,
                notch_freq=config.NOTCH,
                notch_q=config.NOTCH_Q
            )
            
            # Setup detector
            self.detector = PSDDetector(
                fs=self.sampling_rate,
                target_freqs=config.FREQS,
                harmonics=config.HARMONICS,
                snr_neighbor_bw=config.SNR_NEIGHBOR_BW,
                snr_exclude_bw=config.SNR_EXCLUDE_BW
            )
            
            # Setup data buffer
            self.data_buffer = TimeSeriesBuffer(
                n_channels=self.num_channels,
                buffer_duration=config.BUFFER_DURATION,
                sampling_rate=self.sampling_rate
            )
            
            # Setup stable vote filter
            self.vote_filter = StableVoteFilter(hold_duration_ms=config.VOTE_HOLD_MS)
            
            logger.info("All components setup successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup system: {e}")
            return False
    
    def start_acquisition(self) -> bool:
        """Start data acquisition"""
        try:
            if self.use_synthetic:
                # Synthetic generator doesn't return bool
                self.acquisition.start_streaming()
            else:
                if not self.acquisition.start_streaming():
                    logger.error("Failed to start data streaming")
                    return False
            
            logger.info("Data acquisition started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start acquisition: {e}")
            return False
    
    def _detection_loop(self):
        """Main detection loop (runs in separate thread)"""
        logger.info("Detection loop started")
        
        window_samples = int(config.WINDOW_SEC * self.sampling_rate)
        step_samples = int(config.STEP_SEC * self.sampling_rate)
        
        last_process_time = time.time()
        
        while self.is_running:
            try:
                # Get new data from acquisition
                new_data = self.acquisition.get_data()
                
                if new_data is not None and new_data.shape[1] > 0:
                    # Add to buffer
                    self.data_buffer.add_samples(new_data)
                    
                    # Check if it's time to process
                    current_time = time.time()
                    if current_time - last_process_time >= config.STEP_SEC:
                        # Get analysis window
                        analysis_data = self.data_buffer.get_latest_samples(window_samples)
                        
                        if analysis_data is not None:
                            # Apply filters
                            filtered_data = self.filters.apply_all(analysis_data, axis=1)
                            
                            # Select channels if specified
                            if config.USE_CHANNELS is not None:
                                channel_indices = [ch for ch in config.USE_CHANNELS 
                                                 if ch < filtered_data.shape[0]]
                                if len(channel_indices) > 0:
                                    filtered_data = filtered_data[channel_indices, :]
                            
                            # Detect SSVEP
                            result = self.detector.detect(filtered_data, return_all_scores=True)
                            
                            # Check SNR threshold
                            if result['snr'] >= config.MIN_SNR_THRESHOLD:
                                # Update stable vote filter
                                stable_decision = self.vote_filter.update(result['frequency'])
                                
                                # Format output
                                output = format_detection_output(
                                    result['frequency'], 
                                    result['snr'], 
                                    result['all_scores'],
                                    is_stable=(stable_decision is not None)
                                )
                                
                                print(output)
                                
                                if stable_decision is not None:
                                    self.last_detection_time = current_time
                                
                                self.detection_count += 1
                            
                            else:
                                # Low SNR - reset vote filter
                                self.vote_filter.reset()
                        
                        last_process_time = current_time
                
                # Small sleep to prevent excessive CPU usage
                time.sleep(0.01)
                
            except Exception as e:
                logger.error(f"Error in detection loop: {e}")
                time.sleep(0.1)  # Longer sleep on error
        
        logger.info("Detection loop stopped")
    
    def start_detection(self) -> bool:
        """Start real-time detection"""
        if self.is_running:
            logger.warning("Detection already running")
            return True
        
        self.is_running = True
        self.start_time = time.time()
        self.detection_count = 0
        
        # Start detection thread
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
        logger.info("Real-time detection started")
        return True
    
    def stop_detection(self):
        """Stop real-time detection"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.detection_thread is not None:
            self.detection_thread.join(timeout=2.0)
        
        logger.info("Real-time detection stopped")
    
    def stop_acquisition(self):
        """Stop data acquisition"""
        if self.acquisition:
            self.acquisition.stop_streaming()
            logger.info("Data acquisition stopped")
    
    def disconnect(self):
        """Disconnect from acquisition device"""
        if self.acquisition and not self.use_synthetic:
            self.acquisition.disconnect()
            logger.info("Disconnected from OpenBCI board")
    
    def print_statistics(self):
        """Print system statistics"""
        if self.start_time is not None:
            runtime = time.time() - self.start_time
            detection_rate = self.detection_count / runtime if runtime > 0 else 0
            
            print("\n" + "="*50)
            print("SSVEP SYSTEM STATISTICS")
            print("="*50)
            print(f"Runtime: {runtime:.1f} seconds")
            print(f"Total detections: {self.detection_count}")
            print(f"Detection rate: {detection_rate:.1f} Hz")
            print(f"Target frequencies: {config.FREQS} Hz")
            print(f"Analysis window: {config.WINDOW_SEC:.1f}s")
            print(f"Update rate: {1/config.STEP_SEC:.1f} Hz")
            if self.last_detection_time is not None:
                print(f"Last stable detection: {time.time() - self.last_detection_time:.1f}s ago")
            print("="*50)
    
    def run(self, duration: Optional[float] = None):
        """
        Run the complete SSVEP system
        
        Args:
            duration: How long to run (seconds). None for indefinite.
        """
        try:
            # Setup
            if not self.setup():
                logger.error("System setup failed")
                return False
            
            # Start acquisition
            if not self.start_acquisition():
                logger.error("Failed to start acquisition")
                return False
            
            # Start detection
            if not self.start_detection():
                logger.error("Failed to start detection")
                return False
            
            # Print info
            print(f"\n[INFO] SSVEP Detection System Running")
            print(f"[INFO] Sampling rate: {self.sampling_rate} Hz, EEG channels: {self.num_channels}")
            print(f"[INFO] Target frequencies: {config.FREQS} Hz")
            print(f"[INFO] Analysis: {config.WINDOW_SEC}s window, {config.STEP_SEC}s step")
            print(f"[INFO] Press Ctrl+C to stop\n")
            
            # Run for specified duration or until interrupted
            start_time = time.time()
            try:
                while True:
                    if duration is not None and (time.time() - start_time) >= duration:
                        break
                    time.sleep(0.1)
                    
            except KeyboardInterrupt:
                print("\nStopping SSVEP system...")
            
            return True
            
        except Exception as e:
            logger.error(f"Error running system: {e}")
            return False
            
        finally:
            # Cleanup
            self.stop_detection()
            self.stop_acquisition()
            self.disconnect()
            self.print_statistics()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='SSVEP Real-time Detection System')
    
    # Data source options
    parser.add_argument('--synthetic', type=float, metavar='FREQ', nargs='?', const=10.0,
                       help='Use synthetic data at specified frequency (default: 10.0 Hz)')
    parser.add_argument('--duration', type=float, 
                       help='Run for specified duration in seconds')
    
    # Board options (for real acquisition)
    parser.add_argument('--board', choices=['CYTON', 'CYTON_DAISY'], default=config.BOARD_ID,
                       help='OpenBCI board type')
    parser.add_argument('--port', default=config.SERIAL_PORT,
                       help='Serial port for OpenBCI dongle')
    
    # Detection options
    parser.add_argument('--freqs', nargs='+', type=float, default=config.FREQS,
                       help='Target frequencies (Hz)')
    parser.add_argument('--window', type=float, default=config.WINDOW_SEC,
                       help='Analysis window duration (seconds)')
    parser.add_argument('--step', type=float, default=config.STEP_SEC,
                       help='Analysis step size (seconds)')
    parser.add_argument('--harmonics', type=int, default=config.HARMONICS,
                       help='Number of harmonics to use (1-3)')
    parser.add_argument('--hold-time', type=int, default=config.VOTE_HOLD_MS,
                       help='Stable decision hold time (ms)')
    
    # Channel selection
    parser.add_argument('--channels', nargs='+', type=int,
                       help='EEG channels to use (0-based indices)')
    parser.add_argument('--occipital-only', action='store_true',
                       help='Use only occipital channels (0,1,2,7,8,9 for 16-ch)')
    
    args = parser.parse_args()
    
    # Update config with command line arguments
    if args.freqs != config.FREQS:
        config.FREQS = args.freqs
    if args.window != config.WINDOW_SEC:
        config.WINDOW_SEC = args.window
    if args.step != config.STEP_SEC:
        config.STEP_SEC = args.step
    if args.harmonics != config.HARMONICS:
        config.HARMONICS = args.harmonics
    if args.hold_time != config.VOTE_HOLD_MS:
        config.VOTE_HOLD_MS = args.hold_time
    if args.board != config.BOARD_ID:
        config.BOARD_ID = args.board
    if args.port != config.SERIAL_PORT:
        config.SERIAL_PORT = args.port
    
    # Handle channel selection
    if args.occipital_only:
        if config.BOARD_ID == 'CYTON_DAISY':
            config.USE_CHANNELS = [0, 1, 2, 7, 8, 9]  # O1, O2, Oz, PO3, PO4, POz approximation
        else:
            config.USE_CHANNELS = [0, 1, 2]  # Reduced for 8-channel
    elif args.channels:
        config.USE_CHANNELS = args.channels
    
    # Create and run system
    use_synthetic = args.synthetic is not None
    synthetic_freq = args.synthetic if use_synthetic else None
    
    system = SSVEPSystem(use_synthetic=use_synthetic, synthetic_freq=synthetic_freq)
    success = system.run(duration=args.duration)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())