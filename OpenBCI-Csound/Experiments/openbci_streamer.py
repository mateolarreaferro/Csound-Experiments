#!/usr/bin/env python3
"""
OpenBCI Hardware Streamer for Csound Scripts
============================================

This script directly interfaces with OpenBCI hardware (Cyton + Daisy for 16 channels)
and streams the data via OSC to Csound scripts, without needing the OpenBCI GUI.

Hardware Setup:
- OpenBCI Cyton (8 channels) + Daisy (8 additional channels) = 16 total channels
- Sample rate: 250 Hz
- Data transmitted via OSC to various ports

OSC Output Ports:
- Band Power & Focus: Port 5003
- Accelerometer/Aux: Port 5004  
- Raw EEG: Port 5005

Usage:
    python openbci_streamer.py --port /dev/tty.usbserial-xxx [--mode all]
    
Requirements:
    pip install brainflow python-osc numpy scipy
"""

import argparse
import time
import threading
import numpy as np
from collections import deque
from typing import Dict, List, Optional
from pythonosc import udp_client
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, DetrendOperations
from scipy import signal
import sys


class OpenBCIStreamer:
    def __init__(self, port: str, daisy: bool = True):
        """
        Initialize the OpenBCI streamer
        
        Args:
            port: Serial port of the OpenBCI board
            daisy: Whether Daisy module is attached (16 channels if True, 8 if False)
        """
        # OSC clients for different data types (matching OpenBCI GUI ports)
        self.clients = {
            'bandpower': udp_client.SimpleUDPClient("127.0.0.1", 5001),  # OpenBCI GUI uses 5001 for band power
            'focus': udp_client.SimpleUDPClient("127.0.0.1", 5001),      # Same port as band power
            'accel': udp_client.SimpleUDPClient("127.0.0.1", 5004),
            'fft': udp_client.SimpleUDPClient("127.0.0.1", 5005)
        }
        
        # BrainFlow parameters
        self.port = port
        self.daisy = daisy
        self.board_id = BoardIds.CYTON_DAISY_BOARD if daisy else BoardIds.CYTON_BOARD
        self.channels = 16 if daisy else 8
        self.sample_rate = BoardShim.get_sampling_rate(self.board_id)  # 125 Hz for Daisy, 250 Hz for Cyton only
        self.board = None
        self.board_params = None
        
        # Data buffers for processing (1 second of data)
        self.buffer_size = int(self.sample_rate)
        self.eeg_buffers = [deque(maxlen=self.buffer_size) for _ in range(self.channels)]
        
        # Band definitions (Hz)
        self.bands = {
            'delta': (0.5, 4),
            'theta': (4, 8),
            'alpha': (8, 13),
            'beta': (13, 30),
            'gamma': (30, 100)
        }
        
        # Processing parameters
        self.process_interval = 0.1  # Process band powers every 100ms
        self.last_process_time = time.time()
        
        # Thread control
        self.running = False
        self.processing_thread = None
        self.streaming_thread = None
        
    def connect(self):
        """Connect to the OpenBCI board"""
        try:
            print(f"🔌 Connecting to OpenBCI on {self.port}...")
            
            # Setup BrainFlow parameters
            self.board_params = BrainFlowInputParams()
            self.board_params.serial_port = self.port
            
            # Create and prepare board
            self.board = BoardShim(self.board_id, self.board_params)
            self.board.prepare_session()
            
            print(f"✅ Connected! Detected {self.channels} channels")
            print(f"   Sample rate: {self.sample_rate} Hz")
            return True
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the OpenBCI board"""
        if self.board and self.board.is_prepared():
            self.board.stop_stream()
            self.board.release_session()
            print("🔌 Disconnected from OpenBCI")
    
    def start_streaming(self, modes: List[str]):
        """Start streaming data from the board"""
        if not self.board:
            print("❌ Board not connected!")
            return
        
        self.running = True
        self.modes = modes
        
        # Start the BrainFlow stream
        self.board.start_stream()
        print(f"🎯 Starting data stream with modes: {modes}")
        print("Press Ctrl+C to stop...\n")
        
        # Start processing thread for band power calculations
        if 'bandpower' in modes or 'all' in modes:
            self.processing_thread = threading.Thread(target=self._process_band_powers, daemon=True)
            self.processing_thread.start()
            print("📊 Started Band Power processing")
        
        # Start streaming thread
        self.streaming_thread = threading.Thread(target=self._stream_data, daemon=True)
        self.streaming_thread.start()
    
    def stop_streaming(self):
        """Stop streaming data"""
        self.running = False
        if self.board and self.board.is_prepared():
            self.board.stop_stream()
        if self.processing_thread:
            self.processing_thread.join(timeout=1)
        if self.streaming_thread:
            self.streaming_thread.join(timeout=1)
        print("🛑 Streaming stopped")
    
    def _stream_data(self):
        """Main streaming loop to read and process data from the board"""
        # Get channel indices
        eeg_channels = BoardShim.get_eeg_channels(self.board_id)[:self.channels]
        accel_channels = BoardShim.get_accel_channels(self.board_id)
        aux_channels = BoardShim.get_analog_channels(self.board_id)
        
        print(f"📡 Streaming started - EEG channels: {len(eeg_channels)}")
        print(f"   Sending to ports:")
        print(f"   - Band Power: 5001")
        print(f"   - Accelerometer: 5004") 
        print(f"   - Raw EEG: 5005")
        sample_count = 0
        last_status_time = time.time()
        
        while self.running:
            try:
                # Get current board data
                data = self.board.get_current_board_data(250)  # Get up to 250 samples
                
                if data.shape[1] > 0:
                    # Process each sample
                    for i in range(data.shape[1]):
                        # Extract EEG data (already in microvolts for BrainFlow)
                        eeg_data = data[eeg_channels, i]
                        
                        # Store in buffers for processing
                        for ch in range(len(eeg_data)):
                            self.eeg_buffers[ch].append(eeg_data[ch])
                        
                        # Send raw EEG data
                        if 'fft' in self.modes or 'all' in self.modes:
                            for ch in range(len(eeg_data)):
                                self.clients['fft'].send_message(
                                    f"/openbci/eeg/{ch}",
                                    [float(eeg_data[ch])]
                                )
                        
                        # Handle accelerometer data
                        if ('accel' in self.modes or 'all' in self.modes) and len(accel_channels) > 0:
                            accel_data = data[accel_channels, i]
                            
                            if len(accel_data) >= 3:
                                # BrainFlow returns accelerometer data in g
                                # Convert to m/s^2
                                accel_x = accel_data[0] * 9.81
                                accel_y = accel_data[1] * 9.81
                                accel_z = accel_data[2] * 9.81
                                
                                self.clients['accel'].send_message(
                                    "/openbci/accel",
                                    [float(accel_x), float(accel_y), float(accel_z)]
                                )
                        
                        # Send auxiliary data
                        if ('accel' in self.modes or 'all' in self.modes) and len(aux_channels) > 0:
                            aux_data = data[aux_channels, i]
                            for aux_ch in range(len(aux_data)):
                                self.clients['accel'].send_message(
                                    f"/openbci/aux/{aux_ch}",
                                    [float(aux_data[aux_ch])]
                                )
                    
                    sample_count += data.shape[1]
                    
                    # Print status every 5 seconds
                    if time.time() - last_status_time > 5:
                        print(f"📊 Streamed {sample_count} samples")
                        last_status_time = time.time()
                
                time.sleep(0.01)  # Small delay to prevent CPU overload
                
            except Exception as e:
                if self.running:
                    print(f"Stream error: {e}")
                    time.sleep(0.1)
    
    def _process_band_powers(self):
        """Background thread to calculate and send band powers"""
        while self.running:
            current_time = time.time()
            
            # Process at specified interval
            if current_time - self.last_process_time >= self.process_interval:
                self.last_process_time = current_time
                
                # Calculate band powers for each channel
                for ch in range(self.channels):
                    if len(self.eeg_buffers[ch]) >= self.sample_rate // 2:  # Need at least 0.5s of data
                        band_powers = self._calculate_band_power(ch)
                        
                        if band_powers:
                            # Send band power data (matching OpenBCI GUI format)
                            # The GUI sends: [delta, theta, alpha, beta, gamma]
                            power_values = [
                                band_powers['delta'],
                                band_powers['theta'],
                                band_powers['alpha'],
                                band_powers['beta'],
                                band_powers['gamma']
                            ]
                            
                            # Send to the format expected by Csound BCI_BandPower.csd
                            self.clients['bandpower'].send_message(
                                f"/openbci/band-power/{ch}",  # Correct format for BCI_BandPower.csd
                                power_values
                            )
                            
                            # Debug print first channel
                            if ch == 0:
                                print(f"Sending band power ch0: {power_values[:3]}...")
                            
                            # Calculate and send focus metric (alpha/beta ratio)
                            if 'focus' in self.modes or 'all' in self.modes:
                                focus = self._calculate_focus(band_powers)
                                self.clients['focus'].send_message(
                                    f"/openbci/focus/{ch}",
                                    [focus]
                                )
            
            time.sleep(0.01)  # Small sleep to prevent CPU overload
    
    def _calculate_band_power(self, channel: int) -> Optional[Dict[str, float]]:
        """
        Calculate power in each frequency band for a channel
        
        Args:
            channel: Channel index
            
        Returns:
            Dictionary of band powers or None if insufficient data
        """
        if len(self.eeg_buffers[channel]) < self.sample_rate // 2:
            return None
        
        # Get data from buffer
        data = np.array(self.eeg_buffers[channel])
        
        # Remove DC offset
        data = data - np.mean(data)
        
        # Apply Hamming window
        data = data * np.hamming(len(data))
        
        # Calculate power spectral density using Welch's method
        freqs, psd = signal.welch(data, self.sample_rate, nperseg=min(256, len(data)))
        
        # Calculate band powers
        band_powers = {}
        for band_name, (low_freq, high_freq) in self.bands.items():
            # Find frequency indices
            idx_low = np.argmax(freqs >= low_freq)
            idx_high = np.argmax(freqs >= high_freq)
            if idx_high == 0:
                idx_high = len(freqs) - 1
            
            # Calculate average power in band (convert to microvolts squared)
            band_power = np.mean(psd[idx_low:idx_high+1]) * 1e6
            band_powers[band_name] = band_power
        
        return band_powers
    
    def _calculate_focus(self, band_powers: Dict[str, float]) -> float:
        """
        Calculate focus metric from band powers
        
        Focus is typically calculated as the ratio of beta to alpha+theta
        Higher values indicate more focused/alert state
        
        Args:
            band_powers: Dictionary of band powers
            
        Returns:
            Focus value (0-100)
        """
        if not band_powers:
            return 50.0
        
        # Calculate focus metric
        beta = band_powers.get('beta', 1.0)
        alpha = band_powers.get('alpha', 1.0)
        theta = band_powers.get('theta', 1.0)
        
        # Avoid division by zero
        denominator = alpha + theta
        if denominator < 0.001:
            denominator = 0.001
        
        # Calculate raw focus ratio
        focus_ratio = beta / denominator
        
        # Normalize to 0-100 scale (typical range is 0.2 to 2.0)
        focus_normalized = min(100, max(0, (focus_ratio - 0.2) * 50))
        
        return focus_normalized
    
    def print_status(self):
        """Print current streaming status"""
        if self.running:
            print("\n📊 Streaming Status:")
            print(f"  Channels: {self.channels}")
            print(f"  Sample Rate: {self.sample_rate} Hz")
            print(f"  Modes: {self.modes}")
            print(f"  Buffer Status: {[len(buf) for buf in self.eeg_buffers[:4]]}...")


def find_openbci_port():
    """Attempt to auto-detect OpenBCI port"""
    import serial.tools.list_ports
    
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Common OpenBCI device identifiers
        if 'usbserial' in port.device.lower() or 'COM' in port.device:
            if 'OpenBCI' in port.description or 'FTDI' in port.description:
                return port.device
    
    # Return list of all serial ports if OpenBCI not found
    print("Available serial ports:")
    for port in ports:
        print(f"  {port.device}: {port.description}")
    
    return None


def main():
    parser = argparse.ArgumentParser(description='OpenBCI Hardware Streamer for Csound')
    parser.add_argument(
        '--port',
        type=str,
        help='Serial port of OpenBCI board (e.g., /dev/tty.usbserial-xxx or COM3)'
    )
    parser.add_argument(
        '--mode',
        choices=['bandpower', 'focus', 'accel', 'fft', 'all'],
        default='all',
        help='Data streaming mode (default: all)'
    )
    parser.add_argument(
        '--no-daisy',
        action='store_true',
        help='Disable Daisy module (use only 8 channels)'
    )
    parser.add_argument(
        '--auto-detect',
        action='store_true',
        help='Attempt to auto-detect OpenBCI port'
    )
    
    args = parser.parse_args()
    
    # Auto-detect port if requested or no port provided
    if args.auto_detect or not args.port:
        detected_port = find_openbci_port()
        if detected_port and not args.port:
            print(f"🔍 Auto-detected OpenBCI on {detected_port}")
            args.port = detected_port
        elif not args.port:
            print("❌ Could not auto-detect OpenBCI port. Please specify with --port")
            sys.exit(1)
    
    # Create streamer instance
    streamer = OpenBCIStreamer(args.port, daisy=not args.no_daisy)
    
    print("🧠 OpenBCI Hardware Streamer for Csound")
    print("=" * 50)
    print(f"Port: {args.port}")
    print(f"Channels: {streamer.channels}")
    print(f"Mode: {args.mode}")
    print("\nOSC Output Ports:")
    print("  📊 Band Power & Focus: 127.0.0.1:5003")
    print("  📱 Accelerometer/Aux:  127.0.0.1:5004")
    print("  🧠 Raw EEG:           127.0.0.1:5005")
    print("\nConnecting to OpenBCI hardware...\n")
    
    # Connect to board
    if not streamer.connect():
        print("Failed to connect to OpenBCI board!")
        sys.exit(1)
    
    try:
        # Start streaming
        modes = [args.mode] if args.mode != 'all' else ['bandpower', 'focus', 'accel', 'fft']
        streamer.start_streaming(modes)
        
        # Keep running until interrupted
        while True:
            time.sleep(5)
            streamer.print_status()
            
    except KeyboardInterrupt:
        print("\n⏹️  Stopping stream...")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        streamer.stop_streaming()
        streamer.disconnect()


if __name__ == "__main__":
    main()