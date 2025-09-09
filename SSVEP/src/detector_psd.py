"""PSD-based SSVEP detector using Welch's method and SNR scoring"""

import numpy as np
from scipy import signal
from typing import List, Tuple, Optional, Dict
import logging

logger = logging.getLogger(__name__)


class PSDDetector:
    """SSVEP detector based on Power Spectral Density and SNR calculation"""
    
    def __init__(self, fs: float, target_freqs: List[float], 
                 harmonics: int = 2, snr_neighbor_bw: float = 1.0,
                 snr_exclude_bw: float = 0.3):
        """
        Initialize PSD-based SSVEP detector
        
        Args:
            fs: Sampling frequency in Hz
            target_freqs: List of target SSVEP frequencies
            harmonics: Number of harmonics to consider (1=fundamental only, 2=add 2nd harmonic)
            snr_neighbor_bw: Bandwidth for noise floor calculation (Hz)
            snr_exclude_bw: Exclusion zone around peak for noise calculation (Hz)
        """
        self.fs = fs
        self.target_freqs = sorted(target_freqs)
        self.harmonics = harmonics
        self.snr_neighbor_bw = snr_neighbor_bw
        self.snr_exclude_bw = snr_exclude_bw
        
        logger.info(f"PSD Detector initialized: freqs={target_freqs}Hz, harmonics={harmonics}")
    
    def compute_psd(self, data: np.ndarray, nperseg: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute Power Spectral Density using Welch's method
        
        Args:
            data: Input signal (samples) or (channels x samples)
            nperseg: Length of each segment for Welch's method
        
        Returns:
            Tuple of (frequencies, psd)
        """
        if nperseg is None:
            # Use ~1 second windows or half the data length
            nperseg = min(int(self.fs), data.shape[-1] // 2)
        
        if data.ndim == 1:
            # Single channel
            freqs, psd = signal.welch(data, fs=self.fs, nperseg=nperseg)
        else:
            # Multiple channels - average PSDs
            psds = []
            for ch in range(data.shape[0]):
                f, p = signal.welch(data[ch], fs=self.fs, nperseg=nperseg)
                psds.append(p)
            freqs = f
            psd = np.mean(psds, axis=0)
        
        return freqs, psd
    
    def calculate_snr(self, freqs: np.ndarray, psd: np.ndarray, 
                      target_freq: float) -> float:
        """
        Calculate Signal-to-Noise Ratio for a target frequency
        
        Args:
            freqs: Frequency array from PSD
            psd: Power spectral density
            target_freq: Target frequency to evaluate
        
        Returns:
            SNR value (linear, not dB)
        """
        # Find index of target frequency
        target_idx = np.argmin(np.abs(freqs - target_freq))
        
        # Get signal power at target frequency
        signal_power = psd[target_idx]
        
        # Define noise band indices
        freq_resolution = freqs[1] - freqs[0]
        exclude_bins = int(np.ceil(self.snr_exclude_bw / freq_resolution))
        neighbor_bins = int(np.ceil(self.snr_neighbor_bw / freq_resolution))
        
        # Left noise band
        left_start = max(0, target_idx - neighbor_bins - exclude_bins)
        left_end = max(0, target_idx - exclude_bins)
        
        # Right noise band
        right_start = min(len(psd), target_idx + exclude_bins + 1)
        right_end = min(len(psd), target_idx + neighbor_bins + exclude_bins + 1)
        
        # Collect noise samples
        noise_samples = []
        if left_end > left_start:
            noise_samples.extend(psd[left_start:left_end])
        if right_end > right_start:
            noise_samples.extend(psd[right_start:right_end])
        
        # Calculate noise power
        if len(noise_samples) > 0:
            noise_power = np.mean(noise_samples)
            if noise_power > 0:
                snr = signal_power / noise_power
            else:
                snr = 0.0
        else:
            snr = 0.0
        
        return snr
    
    def detect(self, data: np.ndarray, return_all_scores: bool = False) -> Dict:
        """
        Detect SSVEP frequency from EEG data
        
        Args:
            data: EEG data (samples) or (channels x samples)
            return_all_scores: If True, return SNR scores for all frequencies
        
        Returns:
            Dictionary with detection results:
                - 'frequency': Detected frequency (Hz)
                - 'snr': SNR of detected frequency
                - 'confidence': Detection confidence (0-1)
                - 'all_scores': Dict of freq->SNR (if return_all_scores=True)
                - 'psd': Tuple of (freqs, psd) for visualization
        """
        # Compute PSD
        freqs, psd = self.compute_psd(data)
        
        # Calculate SNR for each target frequency
        snr_scores = {}
        
        for target_freq in self.target_freqs:
            # Calculate SNR for fundamental
            snr_fundamental = self.calculate_snr(freqs, psd, target_freq)
            
            # Calculate SNR for harmonics if enabled
            total_snr = snr_fundamental
            
            if self.harmonics >= 2:
                # Add 2nd harmonic
                snr_2nd = self.calculate_snr(freqs, psd, 2 * target_freq)
                total_snr += 0.5 * snr_2nd  # Weight 2nd harmonic less
            
            if self.harmonics >= 3:
                # Add 3rd harmonic
                snr_3rd = self.calculate_snr(freqs, psd, 3 * target_freq)
                total_snr += 0.25 * snr_3rd  # Weight 3rd harmonic even less
            
            snr_scores[target_freq] = total_snr
        
        # Find frequency with highest SNR
        best_freq = max(snr_scores.keys(), key=lambda f: snr_scores[f])
        best_snr = snr_scores[best_freq]
        
        # Calculate confidence based on SNR difference to second best
        sorted_scores = sorted(snr_scores.values(), reverse=True)
        if len(sorted_scores) > 1 and sorted_scores[1] > 0:
            # Confidence based on ratio of best to second best
            confidence = 1.0 - (sorted_scores[1] / sorted_scores[0])
        else:
            confidence = 1.0 if best_snr > 1.5 else best_snr / 1.5
        
        # Prepare result
        result = {
            'frequency': best_freq,
            'snr': best_snr,
            'confidence': np.clip(confidence, 0.0, 1.0),
            'psd': (freqs, psd)
        }
        
        if return_all_scores:
            result['all_scores'] = snr_scores
        
        return result
    
    def detect_with_history(self, data: np.ndarray, history: List[float], 
                            history_weight: float = 0.2) -> Dict:
        """
        Detect SSVEP with temporal smoothing using detection history
        
        Args:
            data: EEG data (samples) or (channels x samples)
            history: List of previously detected frequencies
            history_weight: Weight for historical bias (0-1)
        
        Returns:
            Detection results dictionary
        """
        # Get current detection
        result = self.detect(data, return_all_scores=True)
        
        if len(history) > 0 and 'all_scores' in result:
            # Calculate historical bias
            hist_counts = {freq: 0 for freq in self.target_freqs}
            for h_freq in history:
                if h_freq in hist_counts:
                    hist_counts[h_freq] += 1
            
            # Apply historical weighting
            for freq in result['all_scores']:
                hist_bias = hist_counts.get(freq, 0) / max(1, len(history))
                result['all_scores'][freq] *= (1 - history_weight) + hist_bias * history_weight
            
            # Re-determine best frequency
            best_freq = max(result['all_scores'].keys(), 
                          key=lambda f: result['all_scores'][f])
            result['frequency'] = best_freq
            result['snr'] = result['all_scores'][best_freq]
        
        return result


def test_detector():
    """Test the PSD detector with synthetic SSVEP signal"""
    import matplotlib.pyplot as plt
    
    # Parameters
    fs = 125.0  # Sampling rate
    duration = 2.0  # seconds
    target_freqs = [7.5, 10.0, 12.0, 15.0]
    true_freq = 10.0  # Simulated SSVEP frequency
    
    # Generate synthetic SSVEP signal
    t = np.arange(0, duration, 1/fs)
    
    # SSVEP signal with harmonics
    signal_ssvep = (np.sin(2 * np.pi * true_freq * t) + 
                   0.3 * np.sin(2 * np.pi * 2 * true_freq * t))  # 2nd harmonic
    
    # Add noise
    noise = 0.5 * np.random.randn(len(t))
    
    # Add some other frequency components (distractors)
    distractors = 0.2 * np.sin(2 * np.pi * 8.0 * t) + 0.2 * np.sin(2 * np.pi * 13.0 * t)
    
    # Combined signal
    eeg_signal = signal_ssvep + noise + distractors
    
    # Create detector
    detector = PSDDetector(fs=fs, target_freqs=target_freqs, harmonics=2)
    
    # Detect SSVEP
    result = detector.detect(eeg_signal, return_all_scores=True)
    
    # Print results
    print(f"True frequency: {true_freq} Hz")
    print(f"Detected frequency: {result['frequency']} Hz")
    print(f"SNR: {result['snr']:.2f}")
    print(f"Confidence: {result['confidence']:.2f}")
    print("\nAll SNR scores:")
    for freq, snr in result['all_scores'].items():
        print(f"  {freq:5.1f} Hz: {snr:6.2f}")
    
    # Plot
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    
    # Time domain
    axes[0].plot(t[:250], eeg_signal[:250])
    axes[0].set_xlabel('Time (s)')
    axes[0].set_ylabel('Amplitude')
    axes[0].set_title(f'Synthetic SSVEP Signal (True freq = {true_freq} Hz)')
    axes[0].grid(True)
    
    # PSD with detection results
    freqs, psd = result['psd']
    axes[1].semilogy(freqs, psd, 'b-', label='PSD')
    
    # Mark target frequencies
    for freq in target_freqs:
        axes[1].axvline(freq, color='gray', linestyle='--', alpha=0.3)
        if freq in result['all_scores']:
            snr = result['all_scores'][freq]
            color = 'green' if freq == result['frequency'] else 'red'
            axes[1].plot(freq, psd[np.argmin(np.abs(freqs - freq))], 
                        'o', color=color, markersize=8,
                        label=f'{freq}Hz (SNR={snr:.1f})')
    
    axes[1].set_xlabel('Frequency (Hz)')
    axes[1].set_ylabel('Power')
    axes[1].set_title(f"PSD and Detection (Detected: {result['frequency']} Hz)")
    axes[1].set_xlim([0, 30])
    axes[1].legend()
    axes[1].grid(True)
    
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    test_detector()