"""Test noise resilience and edge cases"""

import numpy as np
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from filters import SSVEPFilters
from detector_psd import PSDDetector
from synthetic import synth_ssvep

def test_noise_levels():
    """Test detection at different noise levels"""
    print("\n" + "="*50)
    print("NOISE RESILIENCE TEST")
    print("="*50)
    
    fs = 125.0
    duration = 2.0
    test_freq = 10.0
    
    # Initialize components
    filters = SSVEPFilters(fs=fs, bandpass=(6.0, 45.0), notch_freq=60.0)
    detector = PSDDetector(fs=fs, target_freqs=[10.0, 15.0], harmonics=2)
    
    # Test different SNR levels
    snr_levels = [10.0, 5.0, 3.0, 2.0, 1.5, 1.0, 0.5]
    
    print(f"\nTesting {test_freq}Hz SSVEP at different noise levels:")
    print("-"*50)
    
    results = []
    
    for snr in snr_levels:
        # Generate synthetic data with specified SNR
        data = synth_ssvep(frequency=test_freq, fs=fs, duration=duration, 
                          n_channels=8, snr=snr)
        
        # Apply filters
        filtered = filters.apply_all(data, axis=1)
        
        # Detect
        result = detector.detect(filtered, return_all_scores=True)
        
        # Check if correct frequency detected
        detected_correct = (result['frequency'] == test_freq)
        detected_snr = result['snr']
        confidence = result['confidence']
        
        results.append({
            'input_snr': snr,
            'detected_freq': result['frequency'],
            'detected_snr': detected_snr,
            'confidence': confidence,
            'correct': detected_correct
        })
        
        status = "✓" if detected_correct else "✗"
        print(f"SNR={snr:4.1f}: Detected {result['frequency']:4.0f}Hz "
              f"(SNR={detected_snr:6.2f}, Conf={confidence:.2f}) {status}")
    
    # Calculate accuracy
    correct_detections = sum(1 for r in results if r['correct'])
    accuracy = correct_detections / len(results) * 100
    
    print("-"*50)
    print(f"Accuracy: {accuracy:.1f}% ({correct_detections}/{len(results)})")
    
    # Find minimum working SNR
    min_working_snr = None
    for r in results:
        if r['correct']:
            min_working_snr = r['input_snr']
    
    if min_working_snr:
        print(f"Minimum working SNR: {min_working_snr}")
    
    return results


def test_interference():
    """Test with interfering frequencies"""
    print("\n" + "="*50)
    print("INTERFERENCE TEST")
    print("="*50)
    
    fs = 125.0
    duration = 2.0
    t = np.arange(int(duration * fs)) / fs
    
    # Initialize components
    filters = SSVEPFilters(fs=fs, bandpass=(6.0, 45.0), notch_freq=60.0)
    detector = PSDDetector(fs=fs, target_freqs=[10.0, 15.0], harmonics=2)
    
    print("\nTesting with interfering frequencies:")
    print("-"*50)
    
    # Test cases
    test_cases = [
        ("Clean 10Hz", [10.0], [1.0]),
        ("10Hz + weak 15Hz", [10.0, 15.0], [1.0, 0.3]),
        ("10Hz + strong 15Hz", [10.0, 15.0], [1.0, 0.8]),
        ("10Hz + 12Hz interference", [10.0, 12.0], [1.0, 0.5]),
        ("10Hz + alpha (9Hz)", [10.0, 9.0], [1.0, 0.5]),
        ("10Hz + harmonics", [10.0, 20.0, 30.0], [1.0, 0.3, 0.1]),
    ]
    
    for name, freqs, amps in test_cases:
        # Generate multi-frequency signal
        data = np.zeros((8, len(t)))
        for ch in range(8):
            signal = np.random.randn(len(t)) * 0.2  # Noise
            for f, a in zip(freqs, amps):
                signal += a * np.sin(2 * np.pi * f * t + np.random.uniform(0, 2*np.pi))
            data[ch] = signal
        
        # Apply filters
        filtered = filters.apply_all(data, axis=1)
        
        # Detect
        result = detector.detect(filtered, return_all_scores=True)
        
        print(f"{name:25s}: Detected {result['frequency']:4.0f}Hz "
              f"(10Hz={result['all_scores'][10.0]:.2f}, "
              f"15Hz={result['all_scores'][15.0]:.2f})")
    
    print("-"*50)


def test_short_windows():
    """Test with different window lengths"""
    print("\n" + "="*50)
    print("WINDOW LENGTH TEST")
    print("="*50)
    
    fs = 125.0
    test_freq = 15.0
    
    # Initialize components
    filters = SSVEPFilters(fs=fs, bandpass=(6.0, 45.0), notch_freq=60.0)
    detector = PSDDetector(fs=fs, target_freqs=[10.0, 15.0], harmonics=2)
    
    window_lengths = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    
    print(f"\nTesting {test_freq}Hz detection with different windows:")
    print("-"*50)
    
    for window_sec in window_lengths:
        # Generate data
        data = synth_ssvep(frequency=test_freq, fs=fs, duration=window_sec, 
                          n_channels=8, snr=3.0)
        
        # Apply filters
        filtered = filters.apply_all(data, axis=1)
        
        # Detect
        result = detector.detect(filtered, return_all_scores=True)
        
        correct = (result['frequency'] == test_freq)
        status = "✓" if correct else "✗"
        
        print(f"Window={window_sec:.1f}s: Detected {result['frequency']:4.0f}Hz "
              f"(SNR={result['snr']:6.2f}, Conf={result['confidence']:.2f}) {status}")
    
    print("-"*50)


def test_edge_cases():
    """Test edge cases and error conditions"""
    print("\n" + "="*50)
    print("EDGE CASES TEST")
    print("="*50)
    
    fs = 125.0
    filters = SSVEPFilters(fs=fs, bandpass=(6.0, 45.0), notch_freq=60.0)
    detector = PSDDetector(fs=fs, target_freqs=[10.0, 15.0], harmonics=2)
    
    print("\nTesting edge cases:")
    print("-"*50)
    
    # Test 1: Very short data
    print("1. Very short data (0.1s):", end=" ")
    try:
        short_data = np.random.randn(8, int(0.1 * fs))
        result = detector.detect(short_data)
        print(f"Detected {result['frequency']}Hz (SNR={result['snr']:.2f})")
    except Exception as e:
        print(f"Error: {str(e)[:50]}")
    
    # Test 2: Single channel
    print("2. Single channel data:", end=" ")
    try:
        single_ch = synth_ssvep(10.0, fs, 2.0, n_channels=1, snr=3.0)
        result = detector.detect(single_ch[0])  # Pass 1D array
        print(f"Detected {result['frequency']}Hz (SNR={result['snr']:.2f})")
    except Exception as e:
        print(f"Error: {str(e)[:50]}")
    
    # Test 3: No SSVEP (pure noise)
    print("3. Pure noise:", end=" ")
    noise_data = np.random.randn(8, int(2.0 * fs))
    filtered_noise = filters.apply_all(noise_data, axis=1)
    result = detector.detect(filtered_noise, return_all_scores=True)
    print(f"Detected {result['frequency']}Hz (SNR={result['snr']:.2f})")
    print(f"   Scores: 10Hz={result['all_scores'][10.0]:.2f}, "
          f"15Hz={result['all_scores'][15.0]:.2f}")
    
    # Test 4: Equal strength frequencies
    print("4. Equal strength frequencies:", end=" ")
    t = np.arange(int(2.0 * fs)) / fs
    equal_data = np.zeros((8, len(t)))
    for ch in range(8):
        equal_data[ch] = (np.sin(2 * np.pi * 10.0 * t) + 
                         np.sin(2 * np.pi * 15.0 * t) + 
                         np.random.randn(len(t)) * 0.3)
    filtered_equal = filters.apply_all(equal_data, axis=1)
    result = detector.detect(filtered_equal, return_all_scores=True)
    print(f"Detected {result['frequency']}Hz")
    print(f"   Scores: 10Hz={result['all_scores'][10.0]:.2f}, "
          f"15Hz={result['all_scores'][15.0]:.2f}")
    
    print("-"*50)


def main():
    """Run all noise and edge case tests"""
    
    # Test 1: Noise levels
    noise_results = test_noise_levels()
    
    # Test 2: Interference
    test_interference()
    
    # Test 3: Window lengths
    test_short_windows()
    
    # Test 4: Edge cases
    test_edge_cases()
    
    print("\n" + "="*50)
    print("ALL TESTS COMPLETED")
    print("="*50)


if __name__ == "__main__":
    main()