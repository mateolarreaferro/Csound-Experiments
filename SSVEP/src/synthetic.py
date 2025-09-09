"""Synthetic SSVEP data generation for testing and validation"""

import numpy as np
import time
from typing import Optional, Dict
import threading
import logging

logger = logging.getLogger(__name__)


class SyntheticSSVEPGenerator:
    """Generator for synthetic SSVEP data that mimics real-time acquisition"""
    
    def __init__(self, fs: float = 125.0, n_channels: int = 16):
        """
        Initialize synthetic SSVEP generator
        
        Args:
            fs: Sampling rate in Hz
            n_channels: Number of EEG channels to simulate
        """
        self.fs = fs
        self.n_channels = n_channels
        self.is_streaming = False
        self.current_frequency = None
        self.thread = None
        self.buffer = []
        self.buffer_lock = threading.Lock()
        
        # Signal parameters
        self.snr = 3.0  # Signal-to-noise ratio
        self.phase_offsets = np.random.uniform(0, 2*np.pi, n_channels)
        self.amplitude_factors = np.random.uniform(0.8, 1.2, n_channels)
        self.sample_counter = 0
        
        logger.info(f"Synthetic generator initialized: {fs}Hz, {n_channels} channels")
    
    def set_frequency(self, frequency: float):
        """
        Set the current SSVEP frequency to generate
        
        Args:
            frequency: SSVEP frequency in Hz (None for no SSVEP)
        """
        self.current_frequency = frequency
        logger.info(f"Set synthetic SSVEP frequency to {frequency} Hz")
    
    def _generate_samples(self, n_samples: int) -> np.ndarray:
        """
        Generate synthetic EEG samples
        
        Args:
            n_samples: Number of samples to generate
            
        Returns:
            Array of shape (n_channels, n_samples)
        """
        t = (self.sample_counter + np.arange(n_samples)) / self.fs
        data = np.zeros((self.n_channels, n_samples))
        
        for ch in range(self.n_channels):
            # Start with noise
            signal = np.random.randn(n_samples) / self.snr
            
            # Add background brain activity
            # Alpha (8-12 Hz)
            alpha_freq = 9.0 + np.random.uniform(-1, 1)
            alpha_amp = 0.3 * self.amplitude_factors[ch]
            signal += alpha_amp * np.sin(2 * np.pi * alpha_freq * t + self.phase_offsets[ch])
            
            # Beta (13-30 Hz)
            beta_freq = 20.0 + np.random.uniform(-5, 5)
            beta_amp = 0.2 * self.amplitude_factors[ch]
            signal += beta_amp * np.sin(2 * np.pi * beta_freq * t + self.phase_offsets[ch] + 1)
            
            # Add SSVEP if frequency is set
            if self.current_frequency is not None:
                # Simulate spatial distribution - occipital channels stronger
                spatial_factor = 1.0
                if ch < self.n_channels // 2:  # Assume first half are occipital-like
                    spatial_factor = 1.5
                else:
                    spatial_factor = 0.7
                
                # Fundamental frequency
                ssvep_amp = 1.0 * self.amplitude_factors[ch] * spatial_factor
                signal += ssvep_amp * np.sin(2 * np.pi * self.current_frequency * t + 
                                           self.phase_offsets[ch])
                
                # Second harmonic (weaker)
                if 2 * self.current_frequency < self.fs / 2:
                    harmonic_amp = 0.3 * ssvep_amp
                    signal += harmonic_amp * np.sin(2 * np.pi * 2 * self.current_frequency * t + 
                                                   self.phase_offsets[ch])
            
            data[ch] = signal
        
        self.sample_counter += n_samples
        return data
    
    def _streaming_thread(self):
        """Thread function for continuous data generation"""
        chunk_size = int(0.04 * self.fs)  # ~40ms chunks for realistic timing
        
        while self.is_streaming:
            # Generate new data
            new_data = self._generate_samples(chunk_size)
            
            # Add to buffer
            with self.buffer_lock:
                self.buffer.append(new_data)
                
                # Keep buffer size reasonable
                if len(self.buffer) > 50:  # ~2 seconds at 40ms chunks
                    self.buffer.pop(0)
            
            # Sleep to maintain realistic timing
            time.sleep(chunk_size / self.fs)
    
    def start_streaming(self):
        """Start synthetic data streaming"""
        if not self.is_streaming:
            self.is_streaming = True
            self.buffer.clear()
            self.sample_counter = 0
            self.thread = threading.Thread(target=self._streaming_thread)
            self.thread.daemon = True
            self.thread.start()
            logger.info("Started synthetic data streaming")
    
    def stop_streaming(self):
        """Stop synthetic data streaming"""
        if self.is_streaming:
            self.is_streaming = False
            if self.thread is not None:
                self.thread.join()
            logger.info("Stopped synthetic data streaming")
    
    def get_data(self) -> Optional[np.ndarray]:
        """
        Get available synthetic data
        
        Returns:
            Array of shape (n_channels, n_samples) or None if no data
        """
        with self.buffer_lock:
            if len(self.buffer) == 0:
                return None
            
            # Concatenate all buffered data
            all_data = np.concatenate(self.buffer, axis=1)
            self.buffer.clear()
            
            return all_data
    
    def get_board_info(self) -> Dict:
        """
        Get synthetic board information (mimics real acquisition)
        
        Returns:
            Dictionary with board info
        """
        return {
            'board_type': 'synthetic',
            'sampling_rate': self.fs,
            'num_channels': self.n_channels,
            'current_frequency': self.current_frequency,
            'is_streaming': self.is_streaming
        }


def synth_ssvep(frequency: float, fs: float = 125.0, duration: float = 4.0, 
                n_channels: int = 8, snr: float = 2.0) -> np.ndarray:
    """
    Generate a block of synthetic SSVEP data (for batch testing)
    
    Args:
        frequency: SSVEP frequency in Hz
        fs: Sampling rate in Hz
        duration: Duration in seconds
        n_channels: Number of channels
        snr: Signal-to-noise ratio
    
    Returns:
        Synthetic EEG data of shape (n_channels, n_samples)
    """
    n_samples = int(duration * fs)
    t = np.arange(n_samples) / fs
    data = np.zeros((n_channels, n_samples))
    
    # Generate channel-specific parameters
    phase_offsets = np.random.uniform(0, 2*np.pi, n_channels)
    amplitude_factors = np.random.uniform(0.8, 1.2, n_channels)
    
    for ch in range(n_channels):
        # Base noise
        signal = np.random.randn(n_samples) / snr
        
        # Background brain activity
        # Alpha rhythm (8-12 Hz)
        alpha_freq = 10.0 + np.random.uniform(-1, 1)
        alpha_amp = 0.3 * amplitude_factors[ch]
        signal += alpha_amp * np.sin(2 * np.pi * alpha_freq * t + phase_offsets[ch])
        
        # Beta activity (15-25 Hz)
        beta_freq = 20.0 + np.random.uniform(-3, 3)
        beta_amp = 0.2 * amplitude_factors[ch]
        signal += beta_amp * np.sin(2 * np.pi * beta_freq * t + phase_offsets[ch] + 1)
        
        # Low gamma (30-40 Hz)
        gamma_freq = 35.0 + np.random.uniform(-3, 3)
        gamma_amp = 0.1 * amplitude_factors[ch]
        signal += gamma_amp * np.sin(2 * np.pi * gamma_freq * t + phase_offsets[ch] + 2)
        
        # SSVEP signal
        # Simulate spatial distribution (some channels stronger than others)
        spatial_factor = 1.0
        if ch < n_channels // 2:  # First half stronger (simulate occipital)
            spatial_factor = np.random.uniform(1.2, 1.8)
        else:
            spatial_factor = np.random.uniform(0.5, 1.0)
        
        # Fundamental
        ssvep_amp = 1.0 * amplitude_factors[ch] * spatial_factor
        signal += ssvep_amp * np.sin(2 * np.pi * frequency * t + phase_offsets[ch])
        
        # Second harmonic (if within Nyquist)
        if 2 * frequency < fs / 2:
            harmonic_amp = 0.3 * ssvep_amp
            signal += harmonic_amp * np.sin(2 * np.pi * 2 * frequency * t + phase_offsets[ch])
        
        data[ch] = signal
    
    return data


def test_synthetic():
    """Test synthetic SSVEP generation"""
    import matplotlib.pyplot as plt
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.detector_psd import PSDDetector
    
    print("Testing synthetic SSVEP generation...")
    
    # Test batch generation
    print("\n1. Testing batch generation:")
    test_freq = 12.0
    synthetic_data = synth_ssvep(frequency=test_freq, fs=125.0, duration=2.0, 
                                n_channels=8, snr=3.0)
    print(f"Generated data shape: {synthetic_data.shape}")
    
    # Test with detector
    detector = PSDDetector(fs=125.0, target_freqs=[7.5, 10.0, 12.0, 15.0], harmonics=2)
    result = detector.detect(synthetic_data, return_all_scores=True)
    
    print(f"True frequency: {test_freq} Hz")
    print(f"Detected frequency: {result['frequency']} Hz")
    print(f"SNR: {result['snr']:.2f}")
    print("All scores:", {f: f"{s:.2f}" for f, s in result['all_scores'].items()})
    
    # Test streaming generator
    print("\n2. Testing streaming generator:")
    generator = SyntheticSSVEPGenerator(fs=125.0, n_channels=8)
    generator.set_frequency(10.0)
    generator.start_streaming()
    
    # Collect data for a few iterations
    time.sleep(1.0)  # Let it generate some data
    
    for i in range(3):
        data = generator.get_data()
        if data is not None:
            print(f"Iteration {i}: Got {data.shape[1]} samples")
            
            # Test detection
            if data.shape[1] > 125:  # At least 1 second of data
                result = detector.detect(data)
                print(f"  Detected: {result['frequency']} Hz (SNR: {result['snr']:.2f})")
        
        time.sleep(0.5)
    
    generator.stop_streaming()
    
    # Plot example
    print("\n3. Creating visualization...")
    plot_data = synth_ssvep(frequency=15.0, fs=125.0, duration=1.0, n_channels=4)
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 6))
    
    # Time domain
    t = np.arange(plot_data.shape[1]) / 125.0
    for ch in range(min(3, plot_data.shape[0])):
        axes[0].plot(t[:250], plot_data[ch, :250] + ch * 2, label=f'Ch {ch}')
    axes[0].set_xlabel('Time (s)')
    axes[0].set_ylabel('Amplitude + Offset')
    axes[0].set_title('Synthetic SSVEP Signal (15 Hz)')
    axes[0].legend()
    axes[0].grid(True)
    
    # PSD
    from scipy import signal as sig
    freqs, psd = sig.welch(np.mean(plot_data, axis=0), fs=125.0, nperseg=125)
    axes[1].semilogy(freqs, psd)
    axes[1].axvline(15.0, color='red', linestyle='--', label='True freq (15 Hz)')
    axes[1].axvline(30.0, color='red', linestyle=':', alpha=0.5, label='2nd harmonic')
    axes[1].set_xlabel('Frequency (Hz)')
    axes[1].set_ylabel('Power')
    axes[1].set_title('Power Spectral Density')
    axes[1].set_xlim([0, 50])
    axes[1].legend()
    axes[1].grid(True)
    
    plt.tight_layout()
    plt.show()
    
    print("\nSynthetic data test completed!")


if __name__ == "__main__":
    test_synthetic()