#!/usr/bin/env python3
"""
Test script to verify OpenBCI connection
"""

import sys
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter
import time

def test_connection(port="/dev/cu.usbserial-DM0258DY", daisy=True):
    """Test connection to OpenBCI board"""
    
    print("🔍 Testing OpenBCI Connection")
    print("=" * 40)
    print(f"Port: {port}")
    print(f"Board: {'Cyton + Daisy (16ch)' if daisy else 'Cyton (8ch)'}")
    print()
    
    # Setup parameters
    params = BrainFlowInputParams()
    params.serial_port = port
    
    board_id = BoardIds.CYTON_DAISY_BOARD if daisy else BoardIds.CYTON_BOARD
    
    try:
        # Create board object
        board = BoardShim(board_id, params)
        
        print("📡 Attempting to connect...")
        board.prepare_session()
        
        print("✅ Connected successfully!")
        print(f"   Sample rate: {BoardShim.get_sampling_rate(board_id)} Hz")
        print(f"   EEG channels: {len(BoardShim.get_eeg_channels(board_id))}")
        print()
        
        # Try to get some data
        print("📊 Starting data stream for 2 seconds...")
        board.start_stream()
        time.sleep(2)
        
        data = board.get_board_data()
        board.stop_stream()
        
        print(f"✅ Received {data.shape[1]} samples")
        print(f"   Data shape: {data.shape}")
        
        # Show first few EEG values
        eeg_channels = BoardShim.get_eeg_channels(board_id)
        if len(eeg_channels) > 0 and data.shape[1] > 0:
            print(f"\n📈 Sample EEG values (first channel, first 5 samples):")
            print(f"   {data[eeg_channels[0], :5]}")
        
        # Cleanup
        board.release_session()
        print("\n✅ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure the OpenBCI board is powered on")
        print("2. Check that the USB dongle is properly connected")
        print("3. Verify the serial port is correct")
        print("4. Try without Daisy module: add --no-daisy flag")
        print("5. On Mac, you might need to install FTDI drivers")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test OpenBCI Connection')
    parser.add_argument('--port', default='/dev/cu.usbserial-DM0258DY', help='Serial port')
    parser.add_argument('--no-daisy', action='store_true', help='Test without Daisy (8ch only)')
    
    args = parser.parse_args()
    
    # Enable BrainFlow logging
    BoardShim.enable_dev_board_logger()
    
    success = test_connection(args.port, not args.no_daisy)
    sys.exit(0 if success else 1)