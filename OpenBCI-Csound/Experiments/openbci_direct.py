#!/usr/bin/env python3
"""
Direct OpenBCI to OSC Streamer - Simplified and Robust
"""

import serial
import struct
import time
import threading
from pythonosc import udp_client
import numpy as np
from collections import deque
from scipy import signal
import sys

class OpenBCIDirect:
    def __init__(self, port="/dev/cu.usbserial-DM0258DY"):
        self.port = port
        self.serial = None
        self.running = False
        
        # OSC clients
        self.clients = {
            'bandpower': udp_client.SimpleUDPClient("127.0.0.1", 5003),
            'fft': udp_client.SimpleUDPClient("127.0.0.1", 5005),
            'accel': udp_client.SimpleUDPClient("127.0.0.1", 5004)
        }
        
        # OpenBCI packet parameters
        self.START_BYTE = 0xA0
        self.END_BYTE = 0xC0
        self.channels = 16  # Cyton + Daisy
        
        # Data buffers (1 second at 125Hz for Daisy)
        self.sample_rate = 125
        self.eeg_buffers = [deque(maxlen=self.sample_rate) for _ in range(self.channels)]
        
        # Scaling factor for OpenBCI (24-bit ADC, 4.5V reference, gain of 24)
        self.scale_factor = 4.5 / 24 / (2**23 - 1) * 1000000  # to microvolts
        
        # Band definitions
        self.bands = {
            'delta': (0.5, 4),
            'theta': (4, 8),
            'alpha': (8, 13),
            'beta': (13, 30),
            'gamma': (30, 60)
        }
        
    def connect(self):
        """Simple serial connection"""
        try:
            print(f"🔌 Connecting to {self.port}...")
            self.serial = serial.Serial(
                port=self.port,
                baudrate=115200,
                timeout=1.0
            )
            
            # Clear buffer and reset board
            self.serial.flushInput()
            time.sleep(0.5)
            
            # Send reset command
            self.serial.write(b'v')  # Reset to default state
            time.sleep(1)
            
            # Start streaming with Daisy
            print("📡 Starting 16-channel stream...")
            self.serial.write(b'b')  # Start streaming
            time.sleep(0.5)
            
            print("✅ Connected and streaming!")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def parse_packet(self, packet):
        """Parse OpenBCI packet format"""
        if len(packet) != 33:  # Standard packet size
            return None
            
        # Parse sample number
        sample_num = packet[0]
        
        # Parse 8 channels (3 bytes each)
        channels = []
        for i in range(8):
            idx = 1 + (i * 3)
            # 24-bit signed integer, big-endian
            val = (packet[idx] << 16) | (packet[idx+1] << 8) | packet[idx+2]
            # Convert to signed
            if val >= 0x800000:
                val -= 0x1000000
            channels.append(val * self.scale_factor)
        
        # Parse accelerometer data (last 6 bytes)
        accel = []
        for i in range(3):
            idx = 25 + (i * 2)
            val = (packet[idx] << 8) | packet[idx+1]
            if val >= 0x8000:
                val -= 0x10000
            accel.append(val * 0.002)  # Convert to g
        
        return {
            'sample': sample_num,
            'channels': channels,
            'accel': accel
        }
    
    def stream(self):
        """Main streaming loop"""
        self.running = True
        packet_buffer = bytearray()
        sample_count = 0
        last_band_calc = time.time()
        
        # Start band power thread
        band_thread = threading.Thread(target=self._process_bands, daemon=True)
        band_thread.start()
        
        print("📊 Streaming data via OSC...")
        print("   Band Powers → Port 5003")
        print("   Raw EEG → Port 5005")
        print("   Accelerometer → Port 5004")
        print("\nPress Ctrl+C to stop\n")
        
        while self.running:
            try:
                # Read byte by byte to find packet start
                byte = self.serial.read(1)
                if not byte:
                    continue
                    
                if byte[0] == self.START_BYTE:
                    # Read rest of packet
                    packet = self.serial.read(32)
                    if len(packet) == 32 and packet[-1] == self.END_BYTE:
                        # Valid packet
                        data = self.parse_packet(packet[:-1])
                        
                        if data:
                            # Store in buffers
                            for i, val in enumerate(data['channels'][:self.channels]):
                                self.eeg_buffers[i].append(val)
                            
                            # Send raw EEG
                            for i, val in enumerate(data['channels']):
                                self.clients['fft'].send_message(
                                    f"/openbci/eeg/{i}",
                                    [float(val)]
                                )
                            
                            # Send accelerometer
                            if data['accel']:
                                self.clients['accel'].send_message(
                                    "/openbci/accel",
                                    [float(a * 9.81) for a in data['accel']]  # Convert to m/s²
                                )
                            
                            sample_count += 1
                            if sample_count % 500 == 0:
                                print(f"📡 {sample_count} samples streamed")
                                
            except KeyboardInterrupt:
                break
            except Exception as e:
                if self.running:
                    print(f"Stream error: {e}")
    
    def _process_bands(self):
        """Calculate and send band powers"""
        while self.running:
            time.sleep(0.1)  # Update every 100ms
            
            for ch in range(min(8, len(self.eeg_buffers))):  # Process first 8 channels
                if len(self.eeg_buffers[ch]) >= self.sample_rate // 2:
                    try:
                        # Get data
                        data = np.array(self.eeg_buffers[ch])
                        
                        # Remove DC offset
                        data = data - np.mean(data)
                        
                        # Calculate PSD
                        freqs, psd = signal.welch(data, self.sample_rate, nperseg=min(64, len(data)))
                        
                        # Calculate band powers
                        powers = []
                        for band_name, (low, high) in self.bands.items():
                            idx_low = np.argmax(freqs >= low)
                            idx_high = np.argmax(freqs >= high) if np.any(freqs >= high) else len(freqs)-1
                            power = np.mean(psd[idx_low:idx_high+1]) * 1e6
                            powers.append(power)
                        
                        # Send band powers
                        self.clients['bandpower'].send_message(
                            f"/openbci/band-power/{ch}",
                            powers
                        )
                        
                    except Exception as e:
                        pass
    
    def stop(self):
        """Stop streaming"""
        self.running = False
        if self.serial:
            try:
                self.serial.write(b's')  # Stop streaming
                time.sleep(0.1)
                self.serial.close()
            except:
                pass
        print("\n✅ Streaming stopped")

def main():
    print("=" * 50)
    print("🧠 OpenBCI Direct Streamer (No GUI Required)")
    print("=" * 50)
    
    streamer = OpenBCIDirect()
    
    if not streamer.connect():
        print("\n⚠️  Connection failed. Please:")
        print("1. Turn OFF the OpenBCI board")
        print("2. Wait 3 seconds")
        print("3. Turn it back ON")
        print("4. Run this script again")
        sys.exit(1)
    
    try:
        streamer.stream()
    except KeyboardInterrupt:
        pass
    finally:
        streamer.stop()

if __name__ == "__main__":
    main()