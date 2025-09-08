"""
Data Acquisition Module for OpenBCI Cyton + Daisy
Optimized for SSVEP data streaming and recording
"""

import numpy as np
import time
import threading
import queue
from datetime import datetime
from pathlib import Path
import csv
import json
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter
import mne
from typing import Optional, Tuple, List, Dict, Any
from collections import deque


class SSVEPAcquisition:
    """
    Manages data acquisition from OpenBCI Cyton + Daisy board for SSVEP
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize acquisition system for SSVEP
        
        Args:
            config: Configuration dictionary from settings
        """
        self.config = config
        self.board = None
        self.board_id = BoardIds.CYTON_DAISY_BOARD.value
        self.streaming = False
        self.recording = False
        
        # Data buffers
        self.data_buffer = queue.Queue(maxsize=10000)
        self.marker_buffer = queue.Queue(maxsize=1000)
        self.raw_data = []
        self.markers = []
        
        # Circular buffer for real-time processing
        buffer_size = config['REALTIME']['buffer_size']
        self.circular_buffer = deque(maxlen=buffer_size)
        
        # Threading
        self.stream_thread = None
        self.stop_event = threading.Event()
        
        # Channel configuration - optimized for SSVEP
        self.n_channels = config['HARDWARE']['channels']
        self.sampling_rate = config['HARDWARE']['sampling_rate']
        self.channel_names = config['ELECTRODES']['channel_names']
        
        # Performance monitoring
        self.sample_count = 0
        self.start_time = None
        self.actual_sampling_rate = 0
        
        # File paths
        self.data_dir = Path(config['DATA_STORAGE']['data_dir'])
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Real-time data access
        self.latest_data_lock = threading.Lock()
        self.latest_data = None
        
    def initialize_board(self, serial_port: Optional[str] = None) -> bool:
        """
        Initialize the OpenBCI board for SSVEP recording
        
        Args:
            serial_port: Serial port for the board (auto-detect if None)
            
        Returns:
            Success status
        """
        try:
            # Set up board parameters
            params = BrainFlowInputParams()
            if serial_port:
                params.serial_port = serial_port
            elif self.config['HARDWARE']['serial_port']:
                params.serial_port = self.config['HARDWARE']['serial_port']
            
            # Initialize board
            BoardShim.enable_dev_board_logger()
            self.board = BoardShim(self.board_id, params)
            self.board.prepare_session()
            
            # Configure board settings for SSVEP
            self._configure_board_for_ssvep()
            
            print(f"Board initialized for SSVEP on port {params.serial_port}")
            print(f"Sampling rate: {self.sampling_rate} Hz")
            print(f"Channels: {self.n_channels}")
            return True
            
        except Exception as e:
            print(f"Failed to initialize board: {e}")
            return False
    
    def _configure_board_for_ssvep(self):
        """Configure OpenBCI board settings optimized for SSVEP"""
        if not self.board:
            return
            
        # Set sampling rate (250Hz is good for SSVEP up to 45Hz)
        if self.sampling_rate == 250:
            config_string = "~6"  # 250Hz mode
        elif self.sampling_rate == 500:
            config_string = "~5"  # 500Hz mode
        elif self.sampling_rate == 1000:
            config_string = "~4"  # 1000Hz mode
        else:
            config_string = "~6"  # Default to 250Hz
            
        self.board.config_board(config_string)
        time.sleep(0.5)
        
        # Enable all 16 channels with appropriate gain for SSVEP
        # SSVEP signals are typically smaller than P300, so we use higher gain
        for i in range(1, 17):
            # Channel settings: xCHANNEL POWER_DOWN GAIN_SET INPUT_TYPE_SET BIAS_SET SRB2_SET SRB1_SET X
            # Gain of 24x (setting 6) for better SSVEP detection
            self.board.config_board(f"x{i:X}060110X")
            time.sleep(0.1)
        
        print("Board configured for SSVEP recording")
    
    def start_streaming(self) -> bool:
        """
        Start EEG data streaming optimized for SSVEP
        
        Returns:
            Success status
        """
        if not self.board:
            print("Board not initialized")
            return False
            
        try:
            self.board.start_stream()
            self.streaming = True
            self.stop_event.clear()
            self.start_time = time.time()
            self.sample_count = 0
            
            # Start data collection thread
            self.stream_thread = threading.Thread(target=self._stream_worker_ssvep)
            self.stream_thread.daemon = True
            self.stream_thread.start()
            
            print("SSVEP streaming started")
            return True
            
        except Exception as e:
            print(f"Failed to start streaming: {e}")
            return False
    
    def stop_streaming(self):
        """Stop EEG data streaming"""
        if self.streaming:
            self.stop_event.set()
            if self.stream_thread:
                self.stream_thread.join(timeout=2.0)
            
            if self.board:
                self.board.stop_stream()
            
            self.streaming = False
            
            # Calculate actual sampling rate
            if self.start_time and self.sample_count > 0:
                duration = time.time() - self.start_time
                self.actual_sampling_rate = self.sample_count / duration
                print(f"Streaming stopped. Actual sampling rate: {self.actual_sampling_rate:.1f} Hz")
            else:
                print("Streaming stopped")
    
    def _stream_worker_ssvep(self):
        """Worker thread for continuous SSVEP data streaming"""
        while not self.stop_event.is_set():
            try:
                # Get available data
                data = self.board.get_board_data()
                
                if data.shape[1] > 0:
                    # Extract EEG channels
                    eeg_channels = BoardShim.get_eeg_channels(self.board_id)
                    eeg_data = data[eeg_channels, :]
                    
                    # Extract timestamp
                    timestamp_channel = BoardShim.get_timestamp_channel(self.board_id)
                    timestamps = data[timestamp_channel, :]
                    
                    # Extract markers if available
                    marker_channel = BoardShim.get_marker_channel(self.board_id)
                    if marker_channel >= 0:
                        markers = data[marker_channel, :]
                    else:
                        markers = np.zeros(data.shape[1])
                    
                    # Update sample count
                    self.sample_count += data.shape[1]
                    
                    # Store in buffers
                    for i in range(data.shape[1]):
                        sample = {
                            'timestamp': timestamps[i],
                            'eeg': eeg_data[:, i],
                            'marker': markers[i]
                        }
                        
                        # Add to circular buffer for real-time access
                        self.circular_buffer.append(sample)
                        
                        # Update latest data for real-time processing
                        with self.latest_data_lock:
                            self.latest_data = sample
                        
                        try:
                            self.data_buffer.put_nowait(sample)
                            
                            # Store for recording
                            if self.recording:
                                self.raw_data.append(sample)
                                
                        except queue.Full:
                            # Buffer full, remove oldest sample
                            self.data_buffer.get()
                            self.data_buffer.put_nowait(sample)
                
                time.sleep(0.001)  # Smaller delay for better real-time performance
                
            except Exception as e:
                print(f"Stream worker error: {e}")
    
    def get_realtime_data(self, window_length: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get real-time data for SSVEP processing
        
        Args:
            window_length: Length of data window in seconds
            
        Returns:
            Tuple of (eeg_data, timestamps)
        """
        n_samples = int(window_length * self.sampling_rate)
        
        # Get recent samples from circular buffer
        recent_samples = list(self.circular_buffer)[-n_samples:]
        
        if not recent_samples:
            return np.array([]), np.array([])
        
        # Convert to arrays
        eeg_data = np.array([s['eeg'] for s in recent_samples]).T
        timestamps = np.array([s['timestamp'] for s in recent_samples])
        
        return eeg_data, timestamps
    
    def get_latest_sample(self) -> Optional[Dict]:
        """
        Get the most recent sample for real-time feedback
        
        Returns:
            Latest sample dict or None
        """
        with self.latest_data_lock:
            return self.latest_data.copy() if self.latest_data else None
    
    def insert_marker(self, marker_code: int, timestamp: Optional[float] = None):
        """
        Insert a stimulus marker for SSVEP events
        
        Args:
            marker_code: Numeric code for the stimulus/event
            timestamp: Optional timestamp (uses current time if None)
        """
        if timestamp is None:
            timestamp = time.time()
            
        marker = {
            'code': marker_code,
            'timestamp': timestamp,
            'sample_index': self.sample_count
        }
        
        try:
            self.marker_buffer.put_nowait(marker)
            if self.recording:
                self.markers.append(marker)
                
            # Also insert into the data stream if possible
            if self.board and self.streaming:
                self.board.insert_marker(marker_code)
                
        except queue.Full:
            print("Marker buffer full")
    
    def start_recording(self, filename: Optional[str] = None, 
                       session_type: str = 'ssvep') -> str:
        """
        Start recording SSVEP data to disk
        
        Args:
            filename: Output filename (auto-generated if None)
            session_type: Type of session ('calibration', 'online', 'ssvep')
            
        Returns:
            Path to recording file
        """
        if not self.streaming:
            print("Start streaming before recording")
            return ""
            
        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ssvep_{session_type}_{timestamp}"
        
        self.recording_file = self.data_dir / filename
        self.recording = True
        self.raw_data = []
        self.markers = []
        
        # Save session metadata
        self._save_session_metadata(session_type)
        
        print(f"SSVEP recording started: {self.recording_file}")
        return str(self.recording_file)
    
    def stop_recording(self) -> str:
        """
        Stop recording and save SSVEP data to disk
        
        Returns:
            Path to saved file
        """
        if not self.recording:
            return ""
            
        self.recording = False
        
        # Save data based on format
        format_type = self.config['DATA_STORAGE']['format']
        
        if format_type == 'edf':
            filepath = self._save_as_edf()
        elif format_type == 'csv':
            filepath = self._save_as_csv()
        elif format_type == 'fif':
            filepath = self._save_as_fif()
        else:
            filepath = self._save_as_csv()  # Default to CSV
        
        print(f"SSVEP recording saved: {filepath}")
        
        # Clear buffers
        self.raw_data = []
        self.markers = []
        
        return filepath
    
    def _save_session_metadata(self, session_type: str):
        """Save SSVEP session metadata"""
        metadata = {
            'session_type': session_type,
            'timestamp': datetime.now().isoformat(),
            'sampling_rate': self.sampling_rate,
            'channels': self.channel_names,
            'n_channels': self.n_channels,
            'frequencies': self.config['STIMULUS']['frequencies'],
            'hardware': self.config['HARDWARE'],
            'preprocessing': self.config['PREPROCESSING'],
            'classifier': self.config['CLASSIFIER']
        }
        
        meta_file = str(self.recording_file) + "_metadata.json"
        with open(meta_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _save_as_csv(self) -> str:
        """Save SSVEP data as CSV files"""
        if not self.raw_data:
            return ""
            
        # Save EEG data
        eeg_file = str(self.recording_file) + "_eeg.csv"
        with open(eeg_file, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            header = ['timestamp', 'sample_index'] + self.channel_names + ['marker']
            writer.writerow(header)
            
            # Data
            for i, sample in enumerate(self.raw_data):
                row = [sample['timestamp'], i] + sample['eeg'].tolist() + [sample['marker']]
                writer.writerow(row)
        
        # Save markers separately with more detail
        marker_file = str(self.recording_file) + "_markers.csv"
        with open(marker_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'code', 'sample_index'])
            for marker in self.markers:
                writer.writerow([marker['timestamp'], marker['code'], 
                               marker.get('sample_index', -1)])
        
        return eeg_file
    
    def _save_as_edf(self) -> str:
        """Save SSVEP data as EDF file using MNE"""
        if not self.raw_data:
            return ""
            
        # Convert to numpy array
        n_samples = len(self.raw_data)
        eeg_array = np.zeros((self.n_channels, n_samples))
        for i, sample in enumerate(self.raw_data):
            eeg_array[:, i] = sample['eeg']
        
        # Convert from microvolts to volts for MNE
        eeg_array = eeg_array * 1e-6
        
        # Create MNE Raw object
        info = mne.create_info(
            ch_names=self.channel_names,
            sfreq=self.sampling_rate,
            ch_types='eeg'
        )
        
        # Set montage for better visualization
        montage = mne.channels.make_standard_montage('standard_1020')
        info.set_montage(montage, match_case=False)
        
        raw = mne.io.RawArray(eeg_array, info)
        
        # Add annotations for SSVEP markers
        if self.markers:
            onsets = []
            durations = []
            descriptions = []
            
            start_time = self.raw_data[0]['timestamp']
            for marker in self.markers:
                onsets.append(marker['timestamp'] - start_time)
                durations.append(0.0)
                
                # Create meaningful descriptions for SSVEP markers
                code = marker['code']
                if 100 <= code < 200:
                    # Frequency markers
                    freq_idx = code - 100
                    if freq_idx < len(self.config['STIMULUS']['frequencies']):
                        freq = self.config['STIMULUS']['frequencies'][freq_idx]
                        descriptions.append(f"SSVEP_{freq}Hz")
                    else:
                        descriptions.append(f"SSVEP_{code}")
                else:
                    descriptions.append(str(code))
            
            annotations = mne.Annotations(onsets, durations, descriptions)
            raw.set_annotations(annotations)
        
        # Save as EDF
        edf_file = str(self.recording_file) + ".edf"
        raw.export(edf_file, overwrite=True)
        
        return edf_file
    
    def _save_as_fif(self) -> str:
        """Save SSVEP data as FIF file using MNE"""
        if not self.raw_data:
            return ""
            
        # Convert to numpy array
        n_samples = len(self.raw_data)
        eeg_array = np.zeros((self.n_channels, n_samples))
        for i, sample in enumerate(self.raw_data):
            eeg_array[:, i] = sample['eeg']
        
        # Convert from microvolts to volts
        eeg_array = eeg_array * 1e-6
        
        # Create MNE Raw object
        info = mne.create_info(
            ch_names=self.channel_names,
            sfreq=self.sampling_rate,
            ch_types='eeg'
        )
        
        raw = mne.io.RawArray(eeg_array, info)
        
        # Add SSVEP-specific annotations
        if self.markers:
            onsets = []
            durations = []
            descriptions = []
            
            start_time = self.raw_data[0]['timestamp']
            for marker in self.markers:
                onsets.append(marker['timestamp'] - start_time)
                durations.append(0.0)
                descriptions.append(f"ssvep_{marker['code']}")
            
            annotations = mne.Annotations(onsets, durations, descriptions)
            raw.set_annotations(annotations)
        
        # Save as FIF with SSVEP metadata
        fif_file = str(self.recording_file) + ".fif"
        raw.save(fif_file, overwrite=True)
        
        return fif_file
    
    def get_impedances(self) -> Dict[str, float]:
        """
        Estimate electrode impedances for SSVEP recording quality
        
        Returns:
            Dictionary of channel names to impedance values
        """
        impedances = {}
        
        if not self.streaming:
            return impedances
        
        # Get recent data for impedance estimation
        eeg_data, _ = self.get_realtime_data(1.0)  # 1 second of data
        
        if eeg_data.size == 0:
            return impedances
        
        # Estimate impedance based on signal quality metrics
        for i, channel in enumerate(self.channel_names[:eeg_data.shape[0]]):
            # Simple impedance estimation based on signal variance
            # High variance often indicates poor electrode contact
            variance = np.var(eeg_data[i, :])
            
            # Convert to approximate impedance (this is a rough estimate)
            # Lower variance = better contact = lower impedance
            if variance < 10:
                impedance = 2000  # Good contact
            elif variance < 50:
                impedance = 5000  # Acceptable
            elif variance < 100:
                impedance = 10000  # Poor
            else:
                impedance = 20000  # Very poor
            
            impedances[channel] = impedance
        
        return impedances
    
    def cleanup(self):
        """Clean up resources and close connections"""
        self.stop_streaming()
        
        if self.board:
            self.board.release_session()
            self.board = None
        
        print("SSVEP acquisition system cleaned up")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()