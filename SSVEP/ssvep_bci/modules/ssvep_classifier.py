"""
SSVEP Classification Module
Implements CCA, FBCCA, and PSDA methods for SSVEP detection
"""

import numpy as np
from scipy import signal
from scipy.stats import pearsonr
from sklearn.cross_decomposition import CCA
from typing import Dict, List, Tuple, Optional, Any
import warnings
warnings.filterwarnings('ignore')


class SSVEPClassifier:
    """
    SSVEP classifier using multiple detection methods
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize SSVEP classifier
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.fs = config['HARDWARE']['sampling_rate']
        self.frequencies = config['STIMULUS']['frequencies']
        self.n_harmonics = config['CLASSIFIER']['n_harmonics']
        self.window_length = config['CLASSIFIER']['window_length']
        self.threshold = config['CLASSIFIER']['threshold']
        
        # Filter bank configuration
        self.use_filter_bank = config['CLASSIFIER']['filter_bank']['enabled']
        self.n_filters = config['CLASSIFIER']['filter_bank']['n_filters']
        self.filter_order = config['CLASSIFIER']['filter_bank']['filter_order']
        
        # Classification method
        self.method = config['CLASSIFIER']['type']
        
        # Reference signals for CCA
        self.reference_signals = {}
        self._generate_reference_signals()
        
        # Filter bank filters
        self.filter_bank = None
        if self.use_filter_bank:
            self._create_filter_bank()
        
        # Calibration data
        self.templates = {}
        self.trained = False
        
    def _generate_reference_signals(self):
        """Generate reference signals for each stimulus frequency"""
        n_samples = int(self.window_length * self.fs)
        t = np.arange(n_samples) / self.fs
        
        for freq in self.frequencies:
            refs = []
            
            # Generate sine and cosine references for fundamental and harmonics
            for harmonic in range(1, self.n_harmonics + 1):
                refs.append(np.sin(2 * np.pi * harmonic * freq * t))
                refs.append(np.cos(2 * np.pi * harmonic * freq * t))
            
            self.reference_signals[freq] = np.array(refs).T
    
    def _create_filter_bank(self):
        """Create filter bank for FBCCA"""
        self.filter_bank = []
        
        # Define sub-band ranges
        for i in range(self.n_filters):
            # Sub-bands: 6-14, 14-22, 22-30, 30-38, 38-46 Hz (example)
            low_freq = 6 + i * 8
            high_freq = min(14 + i * 8, 45)
            
            # Create bandpass filter
            sos = signal.butter(self.filter_order, 
                              [low_freq, high_freq], 
                              btype='band', 
                              fs=self.fs, 
                              output='sos')
            self.filter_bank.append(sos)
    
    def extract_features(self, eeg_data: np.ndarray) -> Dict[str, float]:
        """
        Extract SSVEP features from EEG data
        
        Args:
            eeg_data: EEG data (channels x samples)
            
        Returns:
            Dictionary of features for each frequency
        """
        features = {}
        
        if self.method == 'CCA':
            features = self._cca_features(eeg_data)
        elif self.method == 'FBCCA':
            features = self._fbcca_features(eeg_data)
        elif self.method == 'PSDA':
            features = self._psda_features(eeg_data)
        elif self.method == 'ensemble':
            # Combine multiple methods
            cca_features = self._cca_features(eeg_data)
            psda_features = self._psda_features(eeg_data)
            
            # Weighted combination
            for freq in self.frequencies:
                features[freq] = 0.7 * cca_features.get(freq, 0) + 0.3 * psda_features.get(freq, 0)
        
        return features
    
    def _cca_features(self, eeg_data: np.ndarray) -> Dict[str, float]:
        """
        Extract features using Canonical Correlation Analysis
        
        Args:
            eeg_data: EEG data (channels x samples)
            
        Returns:
            CCA coefficients for each frequency
        """
        features = {}
        
        # Ensure correct shape
        if eeg_data.shape[1] < eeg_data.shape[0]:
            eeg_data = eeg_data.T
        
        # Truncate to window length
        n_samples = int(self.window_length * self.fs)
        if eeg_data.shape[0] > n_samples:
            eeg_data = eeg_data[:n_samples, :]
        elif eeg_data.shape[0] < n_samples:
            # Pad with zeros if too short
            padding = n_samples - eeg_data.shape[0]
            eeg_data = np.vstack([eeg_data, np.zeros((padding, eeg_data.shape[1]))])
        
        # Compute CCA for each frequency
        for freq in self.frequencies:
            try:
                # Get reference signals
                ref_signals = self.reference_signals[freq][:eeg_data.shape[0], :]
                
                # Perform CCA
                cca = CCA(n_components=1, max_iter=500)
                cca.fit(eeg_data, ref_signals)
                
                # Get canonical correlation coefficient
                X_c, Y_c = cca.transform(eeg_data, ref_signals)
                corr = np.corrcoef(X_c.T, Y_c.T)[0, 1]
                
                features[freq] = abs(corr)
                
            except Exception as e:
                print(f"CCA error for {freq}Hz: {e}")
                features[freq] = 0.0
        
        return features
    
    def _fbcca_features(self, eeg_data: np.ndarray) -> Dict[str, float]:
        """
        Extract features using Filter Bank CCA
        
        Args:
            eeg_data: EEG data (channels x samples)
            
        Returns:
            FBCCA coefficients for each frequency
        """
        if not self.use_filter_bank:
            return self._cca_features(eeg_data)
        
        features = {}
        
        # Initialize features
        for freq in self.frequencies:
            features[freq] = 0.0
        
        # Apply each filter and compute CCA
        for fb_idx, sos_filter in enumerate(self.filter_bank):
            # Filter the data
            filtered_data = signal.sosfiltfilt(sos_filter, eeg_data, axis=1)
            
            # Get CCA features for filtered data
            fb_features = self._cca_features(filtered_data)
            
            # Weight by filter bank index (higher weight for lower frequencies)
            weight = (self.n_filters - fb_idx) / self.n_filters
            
            # Accumulate weighted features
            for freq in self.frequencies:
                features[freq] += weight * fb_features.get(freq, 0)
        
        # Normalize
        max_val = max(features.values()) if features else 1.0
        if max_val > 0:
            for freq in features:
                features[freq] /= max_val
        
        return features
    
    def _psda_features(self, eeg_data: np.ndarray) -> Dict[str, float]:
        """
        Extract features using Power Spectral Density Analysis
        
        Args:
            eeg_data: EEG data (channels x samples)
            
        Returns:
            PSDA features for each frequency
        """
        features = {}
        
        # Compute PSD using Welch's method
        nperseg = self.config['FEATURES']['psda']['nperseg']
        noverlap = self.config['FEATURES']['psda']['noverlap']
        
        # Average PSD across channels
        psd_list = []
        for ch in range(eeg_data.shape[0]):
            f, psd = signal.welch(eeg_data[ch, :], 
                                 fs=self.fs,
                                 nperseg=nperseg,
                                 noverlap=noverlap)
            psd_list.append(psd)
        
        # Average across channels
        psd_avg = np.mean(psd_list, axis=0)
        
        # Extract power at target frequencies and harmonics
        for freq in self.frequencies:
            power = 0.0
            
            for harmonic in range(1, self.n_harmonics + 1):
                target_freq = freq * harmonic
                
                # Find closest frequency bin
                freq_idx = np.argmin(np.abs(f - target_freq))
                
                # Sum power in a small window around target frequency
                window_size = 0.5  # Hz
                freq_range = np.where((f >= target_freq - window_size) & 
                                     (f <= target_freq + window_size))[0]
                
                if len(freq_range) > 0:
                    power += np.sum(psd_avg[freq_range])
            
            features[freq] = power
        
        # Normalize features
        max_power = max(features.values()) if features else 1.0
        if max_power > 0:
            for freq in features:
                features[freq] /= max_power
        
        return features
    
    def train(self, training_data: Dict[float, np.ndarray]):
        """
        Train classifier with calibration data
        
        Args:
            training_data: Dictionary mapping frequencies to EEG data arrays
        """
        self.templates = {}
        
        for freq, data_list in training_data.items():
            if freq not in self.frequencies:
                continue
            
            # Compute average template for each frequency
            templates = []
            
            for eeg_data in data_list:
                # Extract features or store raw template
                if self.method in ['CCA', 'FBCCA']:
                    # Store preprocessed data as template
                    templates.append(eeg_data)
                else:
                    # Store feature vector as template
                    features = self.extract_features(eeg_data)
                    templates.append(features[freq])
            
            # Average templates
            if templates:
                if isinstance(templates[0], np.ndarray):
                    self.templates[freq] = np.mean(templates, axis=0)
                else:
                    self.templates[freq] = np.mean(templates)
        
        self.trained = True
        print(f"Trained SSVEP classifier with {len(self.templates)} frequency templates")
    
    def predict(self, eeg_data: np.ndarray) -> Tuple[int, float]:
        """
        Predict SSVEP target from EEG data
        
        Args:
            eeg_data: EEG data (channels x samples)
            
        Returns:
            Tuple of (predicted target index, confidence)
        """
        # Extract features
        features = self.extract_features(eeg_data)
        
        # Find frequency with highest score
        max_score = 0.0
        predicted_freq = None
        
        for freq, score in features.items():
            if score > max_score:
                max_score = score
                predicted_freq = freq
        
        # Convert frequency to target index
        if predicted_freq is not None and predicted_freq in self.frequencies:
            target_idx = self.frequencies.index(predicted_freq)
        else:
            target_idx = 0
        
        # Calculate confidence (normalized score)
        confidence = max_score
        
        return target_idx, confidence
    
    def predict_proba(self, eeg_data: np.ndarray) -> np.ndarray:
        """
        Predict probability distribution over targets
        
        Args:
            eeg_data: EEG data (channels x samples)
            
        Returns:
            Probability array for each target
        """
        # Extract features
        features = self.extract_features(eeg_data)
        
        # Convert to probabilities using softmax
        scores = np.array([features.get(freq, 0) for freq in self.frequencies])
        
        # Apply softmax
        exp_scores = np.exp(scores - np.max(scores))
        probabilities = exp_scores / np.sum(exp_scores)
        
        return probabilities
    
    def calculate_snr(self, eeg_data: np.ndarray, target_freq: float) -> float:
        """
        Calculate Signal-to-Noise Ratio for a target frequency
        
        Args:
            eeg_data: EEG data (channels x samples)
            target_freq: Target frequency to analyze
            
        Returns:
            SNR in dB
        """
        # Compute PSD
        f, psd = signal.welch(np.mean(eeg_data, axis=0), 
                            fs=self.fs,
                            nperseg=self.fs*2)
        
        # Signal power (at target frequency and harmonics)
        signal_power = 0.0
        noise_indices = np.ones(len(f), dtype=bool)
        
        for harmonic in range(1, self.n_harmonics + 1):
            freq = target_freq * harmonic
            freq_idx = np.argmin(np.abs(f - freq))
            
            # Signal band (±0.5 Hz)
            signal_band = np.where((f >= freq - 0.5) & (f <= freq + 0.5))[0]
            signal_power += np.sum(psd[signal_band])
            noise_indices[signal_band] = False
        
        # Noise power (everything else in 3-45 Hz band)
        noise_band = np.where((f >= 3) & (f <= 45) & noise_indices)[0]
        noise_power = np.mean(psd[noise_band]) if len(noise_band) > 0 else 1e-10
        
        # Calculate SNR in dB
        snr_db = 10 * np.log10(signal_power / noise_power) if noise_power > 0 else 0
        
        return snr_db
    
    def calculate_itr(self, accuracy: float, n_targets: int, 
                     selection_time: float) -> float:
        """
        Calculate Information Transfer Rate
        
        Args:
            accuracy: Classification accuracy (0-1)
            n_targets: Number of possible targets
            selection_time: Time for one selection in seconds
            
        Returns:
            ITR in bits per minute
        """
        if accuracy <= 0 or accuracy >= 1 or selection_time <= 0:
            return 0.0
        
        # ITR formula for BCI
        p = accuracy
        
        if p == 1:
            bit_rate = np.log2(n_targets)
        else:
            bit_rate = np.log2(n_targets) + p * np.log2(p) + (1 - p) * np.log2((1 - p) / (n_targets - 1))
        
        # Convert to bits per minute
        itr = (60.0 / selection_time) * bit_rate
        
        return max(0, itr)