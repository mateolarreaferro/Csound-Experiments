"""
SSVEP Preprocessing Module
Signal preprocessing optimized for SSVEP detection
"""

import numpy as np
from scipy import signal
from typing import Tuple, Optional, Dict, Any
import mne
from mne.preprocessing import ICA


class SSVEPPreprocessor:
    """
    Preprocessing pipeline for SSVEP signals
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize preprocessor
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.fs = config['HARDWARE']['sampling_rate']
        self.channels = config['ELECTRODES']['channel_names']
        
        # Filter parameters
        self.bandpass = config['PREPROCESSING']['bandpass']
        self.notch_freq = config['PREPROCESSING']['notch_freq']
        self.notch_width = config['PREPROCESSING']['notch_width']
        
        # Artifact rejection
        self.artifact_threshold = config['PREPROCESSING']['artifact_threshold']
        self.use_ica = config['PREPROCESSING']['use_ica']
        
        # Create filters
        self._create_filters()
        
        # ICA for artifact removal
        self.ica = None
        if self.use_ica:
            self.ica = ICA(n_components=min(15, len(self.channels) - 1), 
                          random_state=42)
    
    def _create_filters(self):
        """Create filter coefficients"""
        # Bandpass filter
        self.bp_sos = signal.butter(4, self.bandpass, 
                                   btype='band', 
                                   fs=self.fs, 
                                   output='sos')
        
        # Notch filter
        self.notch_b, self.notch_a = signal.iirnotch(self.notch_freq, 
                                                     self.notch_freq/self.notch_width, 
                                                     self.fs)
        
        # Optional: Create filters for each SSVEP frequency band
        self.freq_filters = {}
        for freq in self.config['STIMULUS']['frequencies']:
            # Create narrow bandpass around each frequency and its harmonics
            filters = []
            for harmonic in range(1, 4):  # First 3 harmonics
                f_center = freq * harmonic
                f_low = f_center - 1.0
                f_high = f_center + 1.0
                
                if f_high < self.fs / 2:  # Below Nyquist
                    sos = signal.butter(3, [f_low, f_high], 
                                      btype='band', 
                                      fs=self.fs, 
                                      output='sos')
                    filters.append(sos)
            
            self.freq_filters[freq] = filters
    
    def process(self, eeg_data: np.ndarray, 
                apply_notch: bool = True,
                apply_bandpass: bool = True,
                remove_artifacts: bool = True) -> np.ndarray:
        """
        Apply preprocessing pipeline to EEG data
        
        Args:
            eeg_data: Raw EEG data (channels x samples)
            apply_notch: Apply notch filter
            apply_bandpass: Apply bandpass filter
            remove_artifacts: Remove artifacts
            
        Returns:
            Preprocessed EEG data
        """
        # Ensure correct shape
        if eeg_data.ndim == 1:
            eeg_data = eeg_data.reshape(1, -1)
        
        # Apply notch filter
        if apply_notch:
            eeg_data = self.apply_notch_filter(eeg_data)
        
        # Apply bandpass filter
        if apply_bandpass:
            eeg_data = self.apply_bandpass_filter(eeg_data)
        
        # Remove artifacts
        if remove_artifacts:
            eeg_data = self.remove_artifacts(eeg_data)
        
        # Remove DC offset
        eeg_data = self.remove_dc_offset(eeg_data)
        
        # Spatial filtering (optional)
        if self.config['ELECTRODES']['reference'] == 'average':
            eeg_data = self.apply_car(eeg_data)
        
        return eeg_data
    
    def apply_bandpass_filter(self, eeg_data: np.ndarray) -> np.ndarray:
        """
        Apply bandpass filter
        
        Args:
            eeg_data: EEG data (channels x samples)
            
        Returns:
            Filtered data
        """
        return signal.sosfiltfilt(self.bp_sos, eeg_data, axis=1)
    
    def apply_notch_filter(self, eeg_data: np.ndarray) -> np.ndarray:
        """
        Apply notch filter to remove powerline interference
        
        Args:
            eeg_data: EEG data (channels x samples)
            
        Returns:
            Filtered data
        """
        return signal.filtfilt(self.notch_b, self.notch_a, eeg_data, axis=1)
    
    def apply_frequency_filter(self, eeg_data: np.ndarray, 
                              target_freq: float) -> np.ndarray:
        """
        Apply narrow bandpass filters around target frequency and harmonics
        
        Args:
            eeg_data: EEG data (channels x samples)
            target_freq: Target SSVEP frequency
            
        Returns:
            Filtered data emphasizing target frequency
        """
        if target_freq not in self.freq_filters:
            return eeg_data
        
        filtered_data = np.zeros_like(eeg_data)
        
        # Apply filters for each harmonic and sum
        for sos_filter in self.freq_filters[target_freq]:
            filtered_data += signal.sosfiltfilt(sos_filter, eeg_data, axis=1)
        
        return filtered_data
    
    def remove_artifacts(self, eeg_data: np.ndarray) -> np.ndarray:
        """
        Remove artifacts from EEG data
        
        Args:
            eeg_data: EEG data (channels x samples)
            
        Returns:
            Cleaned data
        """
        # Simple threshold-based artifact rejection
        if self.artifact_threshold > 0:
            # Mark samples exceeding threshold
            artifact_mask = np.abs(eeg_data) > self.artifact_threshold
            
            # Replace artifacts with interpolated values
            for ch in range(eeg_data.shape[0]):
                artifact_indices = np.where(artifact_mask[ch, :])[0]
                if len(artifact_indices) > 0 and len(artifact_indices) < eeg_data.shape[1] * 0.5:
                    # Interpolate if less than 50% of data is artifacts
                    good_indices = np.where(~artifact_mask[ch, :])[0]
                    if len(good_indices) > 1:
                        eeg_data[ch, artifact_indices] = np.interp(
                            artifact_indices, 
                            good_indices, 
                            eeg_data[ch, good_indices]
                        )
        
        # ICA-based artifact removal
        if self.use_ica and self.ica is not None:
            try:
                # Create MNE raw object
                info = mne.create_info(
                    ch_names=self.channels[:eeg_data.shape[0]],
                    sfreq=self.fs,
                    ch_types='eeg'
                )
                
                # Convert to volts for MNE
                raw = mne.io.RawArray(eeg_data * 1e-6, info)
                
                # Fit ICA
                self.ica.fit(raw)
                
                # Automatically detect and remove EOG/ECG components
                # This is simplified - in practice, you'd want more sophisticated detection
                raw_clean = self.ica.apply(raw)
                
                # Convert back to microvolts
                eeg_data = raw_clean.get_data() * 1e6
                
            except Exception as e:
                print(f"ICA artifact removal failed: {e}")
        
        return eeg_data
    
    def remove_dc_offset(self, eeg_data: np.ndarray) -> np.ndarray:
        """
        Remove DC offset from each channel
        
        Args:
            eeg_data: EEG data (channels x samples)
            
        Returns:
            Data with DC offset removed
        """
        return eeg_data - np.mean(eeg_data, axis=1, keepdims=True)
    
    def apply_car(self, eeg_data: np.ndarray) -> np.ndarray:
        """
        Apply Common Average Reference
        
        Args:
            eeg_data: EEG data (channels x samples)
            
        Returns:
            Re-referenced data
        """
        car = np.mean(eeg_data, axis=0, keepdims=True)
        return eeg_data - car
    
    def apply_spatial_filter(self, eeg_data: np.ndarray, 
                           weights: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Apply spatial filtering to enhance SSVEP signals
        
        Args:
            eeg_data: EEG data (channels x samples)
            weights: Spatial filter weights (channels x components)
            
        Returns:
            Spatially filtered data
        """
        if weights is None:
            # Use default weights emphasizing occipital channels
            weights = self._get_occipital_weights()
        
        # Apply spatial filter
        filtered_data = weights.T @ eeg_data
        
        return filtered_data
    
    def _get_occipital_weights(self) -> np.ndarray:
        """
        Get spatial weights emphasizing occipital channels
        
        Returns:
            Weight matrix
        """
        weights = np.zeros((len(self.channels), 1))
        
        # Emphasize occipital and parietal-occipital channels
        occipital_channels = ['O1', 'O2', 'Oz', 'PO3', 'PO4', 'POz', 'P3', 'P4', 'Pz']
        
        for i, ch in enumerate(self.channels):
            if ch in occipital_channels[:3]:  # O1, O2, Oz
                weights[i, 0] = 1.0
            elif ch in occipital_channels[3:6]:  # PO3, PO4, POz
                weights[i, 0] = 0.7
            elif ch in occipital_channels[6:]:  # P3, P4, Pz
                weights[i, 0] = 0.5
            else:
                weights[i, 0] = 0.1
        
        # Normalize
        weights /= np.linalg.norm(weights)
        
        return weights
    
    def extract_epochs(self, eeg_data: np.ndarray, 
                      markers: np.ndarray,
                      epoch_window: Optional[Tuple[float, float]] = None) -> Dict:
        """
        Extract epochs around stimulus markers
        
        Args:
            eeg_data: Continuous EEG data (channels x samples)
            markers: Marker array with stimulus codes
            epoch_window: Time window around markers (pre, post) in seconds
            
        Returns:
            Dictionary of epochs for each stimulus frequency
        """
        if epoch_window is None:
            epoch_window = self.config['PREPROCESSING']['epoch_window']
        
        pre_samples = int(abs(epoch_window[0]) * self.fs)
        post_samples = int(epoch_window[1] * self.fs)
        epoch_length = pre_samples + post_samples
        
        epochs = {}
        
        # Find marker events
        marker_indices = np.where(markers > 0)[0]
        
        for idx in marker_indices:
            marker_code = markers[idx]
            
            # Extract epoch
            start_idx = max(0, idx - pre_samples)
            end_idx = min(eeg_data.shape[1], idx + post_samples)
            
            if end_idx - start_idx == epoch_length:
                epoch = eeg_data[:, start_idx:end_idx]
                
                # Store epoch by marker code
                if marker_code not in epochs:
                    epochs[marker_code] = []
                epochs[marker_code].append(epoch)
        
        return epochs
    
    def compute_snr_enhancement(self, raw_data: np.ndarray, 
                               processed_data: np.ndarray,
                               target_freq: float) -> float:
        """
        Compute SNR enhancement from preprocessing
        
        Args:
            raw_data: Original EEG data
            processed_data: Preprocessed EEG data
            target_freq: Target SSVEP frequency
            
        Returns:
            SNR enhancement in dB
        """
        # Compute PSD for raw and processed data
        f_raw, psd_raw = signal.welch(np.mean(raw_data, axis=0), 
                                     fs=self.fs, nperseg=self.fs*2)
        f_proc, psd_proc = signal.welch(np.mean(processed_data, axis=0), 
                                       fs=self.fs, nperseg=self.fs*2)
        
        # Calculate SNR for both
        snr_raw = self._calculate_snr_from_psd(f_raw, psd_raw, target_freq)
        snr_proc = self._calculate_snr_from_psd(f_proc, psd_proc, target_freq)
        
        return snr_proc - snr_raw
    
    def _calculate_snr_from_psd(self, freqs: np.ndarray, 
                               psd: np.ndarray, 
                               target_freq: float) -> float:
        """
        Calculate SNR from PSD
        
        Args:
            freqs: Frequency array
            psd: Power spectral density
            target_freq: Target frequency
            
        Returns:
            SNR in dB
        """
        # Signal power at target frequency
        freq_idx = np.argmin(np.abs(freqs - target_freq))
        signal_band = np.where((freqs >= target_freq - 0.5) & 
                              (freqs <= target_freq + 0.5))[0]
        signal_power = np.sum(psd[signal_band]) if len(signal_band) > 0 else 0
        
        # Noise power (3-45 Hz excluding signal band)
        noise_band = np.where((freqs >= 3) & (freqs <= 45) & 
                             ((freqs < target_freq - 1) | (freqs > target_freq + 1)))[0]
        noise_power = np.mean(psd[noise_band]) if len(noise_band) > 0 else 1e-10
        
        # Calculate SNR
        snr_db = 10 * np.log10(signal_power / noise_power) if noise_power > 0 else 0
        
        return snr_db