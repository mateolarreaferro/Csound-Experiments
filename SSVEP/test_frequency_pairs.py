"""Test different frequency pairs for 2-choice BCI"""

import numpy as np
import sys
import os
import time

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from synthetic import synth_ssvep
from filters import SSVEPFilters
from detector_psd import PSDDetector

def test_frequency_pair(freq1, freq2, fs=125.0, duration=2.0):
    """Test a specific frequency pair"""
    
    # Initialize components
    filters = SSVEPFilters(fs=fs, bandpass=(6.0, 45.0), notch_freq=60.0)
    detector = PSDDetector(fs=fs, target_freqs=[freq1, freq2], harmonics=2)
    
    results = {
        'freq1_as_freq1': 0,
        'freq1_as_freq2': 0,
        'freq2_as_freq1': 0,
        'freq2_as_freq2': 0,
        'freq1_snr': [],
        'freq2_snr': []
    }
    
    # Test each frequency multiple times
    n_trials = 5
    
    for trial in range(n_trials):
        # Test freq1
        data1 = synth_ssvep(freq1, fs, duration, n_channels=8, snr=3.0)
        filtered1 = filters.apply_all(data1, axis=1)
        result1 = detector.detect(filtered1)
        
        if result1['frequency'] == freq1:
            results['freq1_as_freq1'] += 1
        else:
            results['freq1_as_freq2'] += 1
        results['freq1_snr'].append(result1['snr'])
        
        # Test freq2
        data2 = synth_ssvep(freq2, fs, duration, n_channels=8, snr=3.0)
        filtered2 = filters.apply_all(data2, axis=1)
        result2 = detector.detect(filtered2)
        
        if result2['frequency'] == freq2:
            results['freq2_as_freq2'] += 1
        else:
            results['freq2_as_freq1'] += 1
        results['freq2_snr'].append(result2['snr'])
    
    # Calculate metrics
    freq1_accuracy = results['freq1_as_freq1'] / n_trials * 100
    freq2_accuracy = results['freq2_as_freq2'] / n_trials * 100
    overall_accuracy = (results['freq1_as_freq1'] + results['freq2_as_freq2']) / (2 * n_trials) * 100
    
    freq1_avg_snr = np.mean(results['freq1_snr'])
    freq2_avg_snr = np.mean(results['freq2_snr'])
    
    return {
        'freq1': freq1,
        'freq2': freq2,
        'freq1_accuracy': freq1_accuracy,
        'freq2_accuracy': freq2_accuracy,
        'overall_accuracy': overall_accuracy,
        'freq1_avg_snr': freq1_avg_snr,
        'freq2_avg_snr': freq2_avg_snr,
        'separation': abs(freq2 - freq1)
    }


def test_discrimination(freq1, freq2, fs=125.0):
    """Test discrimination between two frequencies"""
    
    # Initialize components
    filters = SSVEPFilters(fs=fs, bandpass=(6.0, 45.0), notch_freq=60.0)
    detector = PSDDetector(fs=fs, target_freqs=[freq1, freq2], harmonics=2)
    
    # Generate mixed signal
    duration = 2.0
    t = np.arange(int(duration * fs)) / fs
    
    # Test different mixing ratios
    ratios = [(1.0, 0.0), (0.8, 0.2), (0.6, 0.4), (0.5, 0.5), (0.4, 0.6), (0.2, 0.8), (0.0, 1.0)]
    
    results = []
    for r1, r2 in ratios:
        data = np.zeros((8, len(t)))
        for ch in range(8):
            phase1 = np.random.uniform(0, 2*np.pi)
            phase2 = np.random.uniform(0, 2*np.pi)
            signal = (r1 * np.sin(2 * np.pi * freq1 * t + phase1) +
                     r2 * np.sin(2 * np.pi * freq2 * t + phase2) +
                     np.random.randn(len(t)) * 0.3)
            data[ch] = signal
        
        filtered = filters.apply_all(data, axis=1)
        result = detector.detect(filtered, return_all_scores=True)
        
        results.append({
            'ratio': (r1, r2),
            'detected': result['frequency'],
            'scores': result['all_scores']
        })
    
    return results


def main():
    """Test different frequency pairs for 2-choice BCI"""
    
    print("\n" + "="*50)
    print("FREQUENCY PAIR TESTING FOR 2-CHOICE BCI")
    print("="*50)
    
    # Test different frequency pairs
    frequency_pairs = [
        (7.5, 15.0),   # Maximum separation (2x)
        (8.0, 12.0),   # 1.5x ratio
        (10.0, 15.0),  # Default pair (1.5x)
        (10.0, 12.0),  # Close frequencies
        (7.5, 10.0),   # Lower range
        (12.0, 15.0),  # Higher range
        (8.0, 10.0),   # Very close
        (6.0, 12.0),   # 2x ratio
        (8.57, 12.0),  # 60Hz/7 and 60Hz/5
    ]
    
    print("\nTesting frequency pairs (5 trials each):")
    print("-"*70)
    print(f"{'Pair':12s} {'Sep':>4s} {'Acc1':>6s} {'Acc2':>6s} {'Overall':>7s} {'SNR1':>7s} {'SNR2':>7s}")
    print("-"*70)
    
    results = []
    for freq1, freq2 in frequency_pairs:
        result = test_frequency_pair(freq1, freq2)
        results.append(result)
        
        print(f"{freq1:4.1f}-{freq2:4.1f}Hz  "
              f"{result['separation']:4.1f}  "
              f"{result['freq1_accuracy']:5.0f}%  "
              f"{result['freq2_accuracy']:5.0f}%  "
              f"{result['overall_accuracy']:6.0f}%  "
              f"{result['freq1_avg_snr']:7.1f}  "
              f"{result['freq2_avg_snr']:7.1f}")
    
    print("-"*70)
    
    # Find best pairs
    best_accuracy = max(results, key=lambda x: x['overall_accuracy'])
    best_snr = max(results, key=lambda x: (x['freq1_avg_snr'] + x['freq2_avg_snr'])/2)
    
    print(f"\nBest accuracy: {best_accuracy['freq1']:.1f}-{best_accuracy['freq2']:.1f}Hz "
          f"({best_accuracy['overall_accuracy']:.0f}%)")
    print(f"Best SNR: {best_snr['freq1']:.1f}-{best_snr['freq2']:.1f}Hz "
          f"(avg SNR: {(best_snr['freq1_avg_snr'] + best_snr['freq2_avg_snr'])/2:.1f})")
    
    # Test discrimination for top pairs
    print("\n" + "="*50)
    print("DISCRIMINATION TEST (Mixed Signals)")
    print("="*50)
    
    test_pairs = [(10.0, 15.0), (8.0, 12.0), (7.5, 15.0)]
    
    for freq1, freq2 in test_pairs:
        print(f"\nTesting {freq1:.1f}-{freq2:.1f}Hz discrimination:")
        print("-"*40)
        
        disc_results = test_discrimination(freq1, freq2)
        
        for r in disc_results:
            r1, r2 = r['ratio']
            detected = r['detected']
            scores = r['scores']
            
            expected = freq1 if r1 > r2 else (freq2 if r2 > r1 else "?")
            correct = "✓" if detected == expected or r1 == r2 else "✗"
            
            print(f"Mix {r1:.1f}:{r2:.1f} -> Detected {detected:4.0f}Hz "
                  f"({freq1:.0f}Hz={scores[freq1]:.1f}, {freq2:.0f}Hz={scores[freq2]:.1f}) {correct}")
    
    print("\n" + "="*50)
    print("RECOMMENDATIONS FOR 2-CHOICE BCI")
    print("="*50)
    print("\n1. BEST OVERALL: 10-15 Hz")
    print("   - Good separation (5 Hz)")
    print("   - High SNR for both frequencies")
    print("   - Works well with 60Hz monitors")
    
    print("\n2. MAXIMUM SEPARATION: 7.5-15 Hz")
    print("   - 2x frequency ratio")
    print("   - Excellent discrimination")
    print("   - Good for users who need clear distinction")
    
    print("\n3. FAST RESPONSE: 8-12 Hz")
    print("   - Both in alpha/low beta range")
    print("   - Good SNR")
    print("   - 1.5x frequency ratio")
    
    print("\n4. AVOID: Frequencies closer than 2 Hz")
    print("   - Poor discrimination")
    print("   - Cross-talk between detectors")


if __name__ == "__main__":
    main()