"""Data acquisition module for OpenBCI Cyton/Cyton+Daisy using BrainFlow"""

import logging
import numpy as np
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter
import time
from typing import Optional, Tuple, List

logger = logging.getLogger(__name__)


class OpenBCIAcquisition:
    """Handles data acquisition from OpenBCI Cyton or Cyton+Daisy boards"""
    
    def __init__(self, board_id: str = "CYTON_DAISY", serial_port: str = "COM5"):
        """
        Initialize OpenBCI acquisition
        
        Args:
            board_id: "CYTON" for 8 channels, "CYTON_DAISY" for 16 channels
            serial_port: Serial port of the OpenBCI dongle
        """
        self.board = None
        self.board_id = getattr(BoardIds, f"{board_id}_BOARD")
        self.serial_port = serial_port
        self.sampling_rate = None
        self.eeg_channels = None
        self.num_channels = None
        self.is_streaming = False
        
    def connect(self) -> bool:
        """
        Connect to the OpenBCI board
        
        Returns:
            True if connection successful
        """
        try:
            # Set up board parameters
            params = BrainFlowInputParams()
            params.serial_port = self.serial_port
            
            # Create board instance
            self.board = BoardShim(self.board_id, params)
            
            # Prepare session
            self.board.prepare_session()
            
            # Get board info
            self.sampling_rate = BoardShim.get_sampling_rate(self.board_id)
            self.eeg_channels = BoardShim.get_eeg_channels(self.board_id)
            self.num_channels = len(self.eeg_channels)
            
            logger.info(f"Connected to OpenBCI board")
            logger.info(f"Board ID: {self.board_id}")
            logger.info(f"Sampling rate: {self.sampling_rate} Hz")
            logger.info(f"Number of EEG channels: {self.num_channels}")
            logger.info(f"EEG channel indices: {self.eeg_channels}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to OpenBCI board: {e}")
            return False
    
    def start_streaming(self) -> bool:
        """
        Start data streaming
        
        Returns:
            True if streaming started successfully
        """
        if self.board is None:
            logger.error("Board not connected. Call connect() first.")
            return False
            
        try:
            self.board.start_stream()
            self.is_streaming = True
            logger.info("Started data streaming")
            
            # Wait for buffer to fill a bit
            time.sleep(0.5)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            return False
    
    def get_data(self, num_samples: Optional[int] = None) -> Optional[np.ndarray]:
        """
        Get EEG data from the board
        
        Args:
            num_samples: Number of samples to retrieve. If None, gets all available.
        
        Returns:
            2D numpy array of shape (channels, samples) or None if error
        """
        if not self.is_streaming:
            logger.warning("Not streaming. Call start_streaming() first.")
            return None
            
        try:
            if num_samples is None:
                # Get all available data
                data = self.board.get_board_data()
            else:
                # Get specific number of samples
                data = self.board.get_board_data(num_samples)
            
            if data.shape[1] == 0:
                return None
                
            # Extract only EEG channels
            eeg_data = data[self.eeg_channels, :]
            
            return eeg_data
            
        except Exception as e:
            logger.error(f"Failed to get data: {e}")
            return None
    
    def get_current_data(self, num_samples: int) -> Optional[np.ndarray]:
        """
        Get the most recent N samples without removing from buffer
        
        Args:
            num_samples: Number of most recent samples to retrieve
        
        Returns:
            2D numpy array of shape (channels, samples) or None if not enough data
        """
        if not self.is_streaming:
            logger.warning("Not streaming. Call start_streaming() first.")
            return None
            
        try:
            # Get current board data without removing
            data = self.board.get_current_board_data(num_samples)
            
            if data.shape[1] < num_samples:
                return None  # Not enough data yet
                
            # Extract only EEG channels
            eeg_data = data[self.eeg_channels, :]
            
            return eeg_data
            
        except Exception as e:
            logger.error(f"Failed to get current data: {e}")
            return None
    
    def stop_streaming(self):
        """Stop data streaming"""
        if self.board and self.is_streaming:
            try:
                self.board.stop_stream()
                self.is_streaming = False
                logger.info("Stopped data streaming")
            except Exception as e:
                logger.error(f"Error stopping stream: {e}")
    
    def disconnect(self):
        """Disconnect from the board and release resources"""
        if self.board:
            try:
                if self.is_streaming:
                    self.stop_streaming()
                self.board.release_session()
                logger.info("Disconnected from OpenBCI board")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
            finally:
                self.board = None
    
    def get_board_info(self) -> dict:
        """
        Get information about the connected board
        
        Returns:
            Dictionary with board information
        """
        if self.board is None:
            return {}
            
        return {
            "board_id": self.board_id,
            "serial_port": self.serial_port,
            "sampling_rate": self.sampling_rate,
            "num_channels": self.num_channels,
            "eeg_channels": self.eeg_channels,
            "is_streaming": self.is_streaming
        }
    
    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()


def test_acquisition():
    """Test function to verify OpenBCI connection and data acquisition"""
    import config
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Create acquisition object
    acq = OpenBCIAcquisition(board_id=config.BOARD_ID, serial_port=config.SERIAL_PORT)
    
    # Connect to board
    if not acq.connect():
        print("Failed to connect to board")
        return
    
    # Print board info
    print(f"\nBoard Info:")
    for key, value in acq.get_board_info().items():
        print(f"  {key}: {value}")
    
    # Start streaming
    if not acq.start_streaming():
        print("Failed to start streaming")
        acq.disconnect()
        return
    
    # Collect data for 3 seconds
    print("\nCollecting data for 3 seconds...")
    time.sleep(3)
    
    # Get data
    data = acq.get_data()
    if data is not None:
        print(f"Retrieved data shape: {data.shape}")
        print(f"Data range: [{np.min(data):.2f}, {np.max(data):.2f}] μV")
    
    # Stop and disconnect
    acq.disconnect()
    print("\nTest completed successfully!")


if __name__ == "__main__":
    test_acquisition()