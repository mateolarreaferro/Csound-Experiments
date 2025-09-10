#!/usr/bin/env python3
"""SSVEP binary selector using OpenBCI GUI LSL stream"""

import numpy as np
import time
from pylsl import StreamInlet, resolve_streams
from scipy import signal
from scipy.signal import welch
from collections import deque

# SSVEP parameters
TARGET_FREQS = [10.0, 15.0]  # Hz - matching binary stimulus
HARMONICS = 2  # Include 2nd harmonic
WINDOW_SEC = 2.0  # Analysis window
UPDATE_RATE = 4  # Hz

class SSVEPDetectorLSL:
    def __init__(self):
        self.inlet = None
        self.fs = None
        self.n_channels = None
        self.buffer = deque(maxlen=int(250 * WINDOW_SEC))  # Assuming ~250Hz from GUI
        self.running = False
        
    def connect_lsl(self):
        """Connect to LSL stream from OpenBCI GUI"""
        print("Looking for LSL stream from OpenBCI GUI...")
        
        # Resolve EEG stream
        print("Waiting for EEG stream (5 seconds)...")
        streams = resolve_streams(wait_time=5.0)
        
        if not streams:
            print("No EEG stream found. Make sure:")
            print("1. OpenBCI GUI is running")
            print("2. Data stream is started") 
            print("3. LSL stream is started with 'TimeSeriesRaw' data type")
            return False
        
        # Create inlet
        self.inlet = StreamInlet(streams[0])
        info = self.inlet.info()
        
        self.fs = info.nominal_srate()
        self.n_channels = info.channel_count()
        
        print(f"✓ Connected to LSL stream!")
        print(f"  - Sampling rate: {self.fs} Hz")
        print(f"  - Channels: {self.n_channels}")
        print(f"  - Stream name: {info.name()}")
        
        # Update buffer size based on actual sampling rate
        self.buffer = deque(maxlen=int(self.fs * WINDOW_SEC))
        
        return True
    
    def compute_ssvep_power(self, data, freq, harmonics=2):
        """Compute SSVEP power at target frequency and harmonics"""
        # Apply bandpass filter
        sos = signal.butter(4, [5, 45], btype='band', fs=self.fs, output='sos')
        filtered = signal.sosfiltfilt(sos, data, axis=1)
        
        # Apply 60Hz notch filter for power line noise
        notch_sos = signal.butter(2, [59, 61], btype='bandstop', fs=self.fs, output='sos')
        filtered = signal.sosfiltfilt(notch_sos, filtered, axis=1)
        
        # Compute PSD with longer window for better frequency resolution
        nperseg = min(len(filtered[0]), int(self.fs * 2))  # 2 second window
        freqs, psd = welch(filtered, fs=self.fs, nperseg=nperseg, noverlap=nperseg//2, axis=1)
        
        # Use occipital channels (typically channels 7-9 for O1, O2, Oz in 16-channel setup)
        # OpenBCI channel mapping: 1-8 are frontal/central, 9-16 are parietal/occipital
        if self.n_channels >= 16:
            # Use channels 8-10 (indices 7-9) for occipital region
            psd_mean = np.mean(psd[7:10, :], axis=0)
        elif self.n_channels >= 8:
            # Use last 3 channels
            psd_mean = np.mean(psd[-3:, :], axis=0)
        else:
            psd_mean = np.mean(psd, axis=0)
        
        # Calculate power at target frequency
        target_idx = np.argmin(np.abs(freqs - freq))
        signal_power = psd_mean[target_idx]
        
        # Add harmonic if significant
        if harmonics >= 2:
            harmonic_idx = np.argmin(np.abs(freqs - freq * 2))
            if harmonic_idx < len(psd_mean):
                signal_power += 0.3 * psd_mean[harmonic_idx]  # Weight harmonic less
        
        # Calculate noise as median of surrounding frequencies
        noise_band = np.where((freqs >= freq - 2) & (freqs <= freq + 2) & 
                              (np.abs(freqs - freq) > 0.5))[0]
        if len(noise_band) > 0:
            noise_power = np.median(psd_mean[noise_band])
            snr = signal_power / (noise_power + 1e-10)
        else:
            snr = signal_power
        
        return snr
    
    def detection_loop(self):
        """Main detection loop"""
        print("\n" + "="*50)
        print("SSVEP DETECTION STARTED")
        print(f"Target frequencies: {TARGET_FREQS} Hz")
        print("Look at LEFT (10Hz) or RIGHT (15Hz) flickering box")
        print("="*50 + "\n")
        
        last_update = time.time()
        
        while self.running:
            try:
                # Pull chunk from LSL
                chunk, timestamps = self.inlet.pull_chunk(timeout=0.0, max_samples=32)
                
                if chunk:
                    # Add to buffer
                    for sample in chunk:
                        self.buffer.append(sample)
                
                # Process at UPDATE_RATE Hz
                if time.time() - last_update > 1.0/UPDATE_RATE and len(self.buffer) >= self.fs * 0.5:
                    # Convert buffer to array
                    data = np.array(self.buffer).T  # Shape: (channels, samples)
                    
                    # Compute SSVEP power for each frequency
                    powers = []
                    for freq in TARGET_FREQS:
                        power = self.compute_ssvep_power(data, freq, HARMONICS)
                        powers.append(power)
                    
                    # Determine selection with higher threshold
                    powers = np.array(powers)
                    
                    # Only select if one frequency is significantly stronger
                    if np.max(powers) > 2.0 and np.max(powers) > np.min(powers) * 1.5:
                        selection = np.argmax(powers)
                        if selection == 0:
                            selection_text = "→ LEFT (10 Hz) ←"
                        else:
                            selection_text = "→ RIGHT (15 Hz) ←"
                        
                        # Print with power levels
                        print(f"\r{selection_text:20s} | " +
                              f"SNR 10Hz: {powers[0]:5.2f} | SNR 15Hz: {powers[1]:5.2f}    ", end='')
                    else:
                        print(f"\r{'Looking...':20s} | " +
                              f"SNR 10Hz: {powers[0]:5.2f} | SNR 15Hz: {powers[1]:5.2f}    ", end='')
                    
                    last_update = time.time()
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\nError: {e}")
                time.sleep(0.1)
    
    def run(self):
        """Start SSVEP detection"""
        if not self.connect_lsl():
            return
        
        self.running = True
        
        try:
            self.detection_loop()
        except KeyboardInterrupt:
            print("\n\nStopping...")
        finally:
            self.running = False
            print("Detection stopped")

def main():
    print("="*60)
    print("SSVEP DETECTOR WITH LSL")
    print("="*60)
    print("\nMake sure:")
    print("1. OpenBCI GUI is running and streaming data")
    print("2. In LSL widget, set Stream 1 to 'TimeSeriesRaw' and click Start")
    print("3. Visual stimulus is running (python run_binary_stimulus_pygame.py)")
    print("\nPress Ctrl+C to stop\n")
    
    detector = SSVEPDetectorLSL()
    detector.run()

if __name__ == "__main__":
    main()