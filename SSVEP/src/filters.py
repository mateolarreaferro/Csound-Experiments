"""Signal processing filters for SSVEP detection"""

import numpy as np
from scipy import signal
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class SSVEPFilters:
    """Collection of filters for SSVEP signal processing"""
    
    def __init__(self, fs: float, bandpass: Tuple[float, float] = (6.0, 45.0), 
                 notch_freq: Optional[float] = 60.0, notch_q: float = 30.0):
        """
        Initialize filters
        
        Args:
            fs: Sampling frequency in Hz
            bandpass: Tuple of (low, high) frequencies for bandpass filter
            notch_freq: Frequency for notch filter (50 or 60 Hz), None to disable
            notch_q: Quality factor for notch filter
        """
        self.fs = fs
        self.nyquist = fs / 2.0
        
        # Design bandpass filter
        self.bp_low, self.bp_high = bandpass
        self.sos_bandpass = self._design_bandpass(self.bp_low, self.bp_high)
        
        # Design notch filter
        self.notch_freq = notch_freq
        self.sos_notch = None
        if notch_freq is not None:
            self.sos_notch = self._design_notch(notch_freq, notch_q)
        
        logger.info(f"Filters initialized: fs={fs}Hz, bandpass={bandpass}Hz, notch={notch_freq}Hz")
    
    def _design_bandpass(self, lowcut: float, highcut: float, order: int = 4) -> np.ndarray:
        """
        Design a Butterworth bandpass filter
        
        Args:
            lowcut: Low cutoff frequency
            highcut: High cutoff frequency
            order: Filter order
        
        Returns:
            Second-order sections representation of the filter
        """
        low = lowcut / self.nyquist
        high = highcut / self.nyquist
        
        # Check if frequencies are valid
        if low <= 0 or high >= 1:
            logger.warning(f"Bandpass frequencies out of range: {lowcut}-{highcut}Hz at fs={self.fs}Hz")
            low = max(0.01, low)
            high = min(0.99, high)
        
        sos = signal.butter(order, [low, high], btype='band', output='sos')
        return sos
    
    def _design_notch(self, freq: float, q: float = 30.0) -> np.ndarray:
        """
        Design a notch filter
        
        Args:
            freq: Notch frequency
            q: Quality factor (higher = narrower notch)
        
        Returns:
            Second-order sections representation of the filter
        """
        w0 = freq / self.nyquist
        
        # Check if frequency is valid
        if w0 <= 0 or w0 >= 1:
            logger.warning(f"Notch frequency out of range: {freq}Hz at fs={self.fs}Hz")
            return None
        
        # Design IIR notch filter
        b, a = signal.iirnotch(w0, q)
        sos = signal.tf2sos(b, a)
        return sos
    
    def apply_bandpass(self, data: np.ndarray, axis: int = -1) -> np.ndarray:
        """
        Apply bandpass filter to data
        
        Args:
            data: Input data (channels x samples or just samples)
            axis: Axis along which to filter
        
        Returns:
            Filtered data
        """
        return signal.sosfiltfilt(self.sos_bandpass, data, axis=axis)
    
    def apply_notch(self, data: np.ndarray, axis: int = -1) -> np.ndarray:
        """
        Apply notch filter to data
        
        Args:
            data: Input data (channels x samples or just samples)
            axis: Axis along which to filter
        
        Returns:
            Filtered data
        """
        if self.sos_notch is None:
            return data
        return signal.sosfiltfilt(self.sos_notch, data, axis=axis)
    
    def apply_all(self, data: np.ndarray, axis: int = -1) -> np.ndarray:
        """
        Apply all filters in sequence
        
        Args:
            data: Input data (channels x samples or just samples)
            axis: Axis along which to filter
        
        Returns:
            Filtered data
        """
        # Apply bandpass first
        filtered = self.apply_bandpass(data, axis=axis)
        
        # Then apply notch if enabled
        if self.sos_notch is not None:
            filtered = self.apply_notch(filtered, axis=axis)
        
        return filtered
    
    def filter_online(self, data: np.ndarray, zi_bp=None, zi_notch=None):
        """
        Apply filters for online/real-time processing with filter states
        
        Args:
            data: New data samples (channels x samples)
            zi_bp: Bandpass filter state
            zi_notch: Notch filter state
        
        Returns:
            Tuple of (filtered_data, new_zi_bp, new_zi_notch)
        """
        # Initialize filter states if needed
        if zi_bp is None:
            zi_bp = signal.sosfilt_zi(self.sos_bandpass)
            if data.ndim == 2:
                zi_bp = np.repeat(zi_bp[np.newaxis, :, :], data.shape[0], axis=0)
        
        # Apply bandpass
        if data.ndim == 2:
            filtered = np.zeros_like(data)
            new_zi_bp = np.zeros_like(zi_bp)
            for ch in range(data.shape[0]):
                filtered[ch], new_zi_bp[ch] = signal.sosfilt(self.sos_bandpass, data[ch], zi=zi_bp[ch])
        else:
            filtered, new_zi_bp = signal.sosfilt(self.sos_bandpass, data, zi=zi_bp)
        
        # Apply notch if enabled
        new_zi_notch = zi_notch
        if self.sos_notch is not None:
            if zi_notch is None:
                zi_notch = signal.sosfilt_zi(self.sos_notch)
                if data.ndim == 2:
                    zi_notch = np.repeat(zi_notch[np.newaxis, :, :], data.shape[0], axis=0)
            
            if data.ndim == 2:
                new_zi_notch = np.zeros_like(zi_notch)
                for ch in range(data.shape[0]):
                    filtered[ch], new_zi_notch[ch] = signal.sosfilt(self.sos_notch, filtered[ch], zi=zi_notch[ch])
            else:
                filtered, new_zi_notch = signal.sosfilt(self.sos_notch, filtered, zi=zi_notch)
        
        return filtered, new_zi_bp, new_zi_notch
    
    def get_filter_response(self, freqs: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get frequency response of the combined filters
        
        Args:
            freqs: Frequencies to evaluate (Hz). If None, uses default range.
        
        Returns:
            Tuple of (frequencies, magnitude_response)
        """
        if freqs is None:
            freqs = np.linspace(0, self.nyquist, 1000)
        
        w = 2 * np.pi * freqs / self.fs
        
        # Get bandpass response
        w_bp, h_bp = signal.sosfreqz(self.sos_bandpass, worN=w, fs=self.fs)
        mag_bp = np.abs(h_bp)
        
        # Get notch response if enabled
        if self.sos_notch is not None:
            w_notch, h_notch = signal.sosfreqz(self.sos_notch, worN=w, fs=self.fs)
            mag_notch = np.abs(h_notch)
            mag_total = mag_bp * mag_notch
        else:
            mag_total = mag_bp
        
        return freqs, mag_total


def test_filters():
    """Test the filter implementations"""
    import matplotlib.pyplot as plt
    
    # Create filters
    fs = 125.0  # OpenBCI Cyton+Daisy sampling rate
    filters = SSVEPFilters(fs=fs, bandpass=(6.0, 45.0), notch_freq=60.0)
    
    # Test on synthetic signal
    duration = 2.0
    t = np.arange(0, duration, 1/fs)
    
    # Create test signal with SSVEP frequency + noise + 60Hz interference
    signal_clean = np.sin(2 * np.pi * 10.0 * t)  # 10 Hz SSVEP
    noise = 0.5 * np.random.randn(len(t))
    interference = 0.3 * np.sin(2 * np.pi * 60.0 * t)  # 60 Hz interference
    signal_noisy = signal_clean + noise + interference
    
    # Apply filters
    signal_filtered = filters.apply_all(signal_noisy)
    
    # Plot results
    fig, axes = plt.subplots(3, 1, figsize=(12, 8))
    
    # Time domain
    axes[0].plot(t[:250], signal_noisy[:250], 'b-', alpha=0.7, label='Noisy')
    axes[0].plot(t[:250], signal_filtered[:250], 'r-', label='Filtered')
    axes[0].set_xlabel('Time (s)')
    axes[0].set_ylabel('Amplitude')
    axes[0].set_title('Time Domain')
    axes[0].legend()
    axes[0].grid(True)
    
    # Frequency domain
    freqs_fft = np.fft.fftfreq(len(t), 1/fs)
    fft_noisy = np.abs(np.fft.fft(signal_noisy))
    fft_filtered = np.abs(np.fft.fft(signal_filtered))
    
    mask = freqs_fft >= 0
    axes[1].plot(freqs_fft[mask], fft_noisy[mask], 'b-', alpha=0.7, label='Noisy')
    axes[1].plot(freqs_fft[mask], fft_filtered[mask], 'r-', label='Filtered')
    axes[1].set_xlabel('Frequency (Hz)')
    axes[1].set_ylabel('Magnitude')
    axes[1].set_title('Frequency Domain')
    axes[1].set_xlim([0, 80])
    axes[1].legend()
    axes[1].grid(True)
    
    # Filter response
    freqs, mag = filters.get_filter_response()
    axes[2].plot(freqs, 20 * np.log10(mag))
    axes[2].set_xlabel('Frequency (Hz)')
    axes[2].set_ylabel('Magnitude (dB)')
    axes[2].set_title('Filter Frequency Response')
    axes[2].set_xlim([0, 80])
    axes[2].grid(True)
    axes[2].axvline(10.0, color='g', linestyle='--', alpha=0.5, label='SSVEP freq')
    axes[2].axvline(60.0, color='r', linestyle='--', alpha=0.5, label='Notch freq')
    axes[2].legend()
    
    plt.tight_layout()
    plt.show()
    
    print("Filter test completed!")
    print(f"Signal power at 10 Hz: before={fft_noisy[np.argmin(np.abs(freqs_fft - 10.0))]:.2f}, "
          f"after={fft_filtered[np.argmin(np.abs(freqs_fft - 10.0))]:.2f}")
    print(f"Signal power at 60 Hz: before={fft_noisy[np.argmin(np.abs(freqs_fft - 60.0))]:.2f}, "
          f"after={fft_filtered[np.argmin(np.abs(freqs_fft - 60.0))]:.2f}")


if __name__ == "__main__":
    test_filters()