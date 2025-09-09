#!/usr/bin/env python3
"""Verify SSVEP BCI installation and run basic tests"""

import sys
import os
import time
import traceback

# Add current directory to path
sys.path.insert(0, '.')
sys.path.insert(0, 'src')

def test_imports():
    """Test all required imports"""
    print("🔍 Testing imports...")
    
    try:
        # Core scientific computing
        import numpy as np
        import scipy
        import matplotlib.pyplot as plt
        print(f"✅ Scientific computing: numpy {np.__version__}, scipy {scipy.__version__}")
        
        # BCI hardware interface
        import brainflow
        from brainflow.board_shim import BoardShim, BoardIds
        print("✅ BrainFlow: Hardware interface ready")
        
        # Custom modules
        import config
        from src.filters import SSVEPFilters
        from src.detector_psd import PSDDetector
        from src.utils import TimeSeriesBuffer, StableVoteFilter
        from src.synthetic import SyntheticSSVEPGenerator, synth_ssvep
        from src.acquisition import OpenBCIAcquisition
        print("✅ Custom modules: All SSVEP components loaded")
        
        # Main application
        from binary_choice_app import BinaryChoiceBCI
        print("✅ BCI Application: Ready for use")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_detection():
    """Test SSVEP detection with synthetic data"""
    print("\n🧪 Testing SSVEP detection...")
    
    try:
        from src.filters import SSVEPFilters
        from src.detector_psd import PSDDetector
        from src.synthetic import synth_ssvep
        
        # Create components
        filters = SSVEPFilters(fs=125.0, bandpass=(6.0, 45.0), notch_freq=60.0)
        detector = PSDDetector(fs=125.0, target_freqs=[10.0, 15.0], harmonics=2)
        
        # Test both frequencies
        for freq in [10.0, 15.0]:
            # Generate synthetic SSVEP
            data = synth_ssvep(frequency=freq, fs=125.0, duration=2.0, 
                              n_channels=8, snr=3.0)
            
            # Apply filters
            filtered = filters.apply_all(data, axis=1)
            
            # Detect
            result = detector.detect(filtered)
            
            # Check result
            if result['frequency'] == freq and result['snr'] > 10:
                print(f"✅ {freq}Hz detection: SNR={result['snr']:.1f}, Confidence={result['confidence']:.2f}")
            else:
                print(f"⚠️  {freq}Hz detection: Got {result['frequency']}Hz instead")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Detection test failed: {e}")
        traceback.print_exc()
        return False

def test_binary_choice():
    """Test binary choice BCI functionality"""
    print("\n🎯 Testing binary choice BCI...")
    
    try:
        from binary_choice_app import BinaryChoiceBCI
        
        # Track detections
        detections = []
        
        def callback(choice):
            detections.append(choice)
            print(f"   Detected: {choice}")
        
        # Create BCI system
        bci = BinaryChoiceBCI(
            freq_left=10.0,
            freq_right=15.0,
            use_synthetic=True,
            callback=callback
        )
        
        # Reduce hold time for faster test
        bci.vote_hold_ms = 300
        bci.window_sec = 1.5
        
        # Start system
        if not bci.start():
            print("❌ Failed to start BCI system")
            return False
        
        # Test sequence
        test_sequence = [("left", 2), ("right", 2)]
        
        for target, duration in test_sequence:
            print(f"   Testing {target} for {duration}s...")
            bci.set_target(target)
            time.sleep(duration)
        
        # Stop system
        bci.stop()
        
        # Check results
        if len(detections) >= 2:
            print(f"✅ Binary choice test: {len(detections)} detections")
            return True
        else:
            print(f"⚠️  Binary choice test: Only {len(detections)} detections")
            return False
        
    except Exception as e:
        print(f"❌ Binary choice test failed: {e}")
        traceback.print_exc()
        return False

def test_visual_stimulus():
    """Test if visual stimulus modules can be imported"""
    print("\n🎨 Testing visual stimulus...")
    
    try:
        import psychopy
        from psychopy import visual, core, event
        print("✅ PsychoPy available: Full visual stimulus support")
        return True
    except ImportError:
        try:
            import pygame
            print("⚠️  PsychoPy not available, but Pygame is present")
            print("   Note: Visual stimulus will have limited functionality")
            return False
        except ImportError:
            print("❌ Neither PsychoPy nor Pygame available")
            print("   Visual stimulus will not work")
            return False

def main():
    """Run all verification tests"""
    
    print("="*60)
    print("🧠 SSVEP 2-CHOICE BCI SYSTEM VERIFICATION")
    print("="*60)
    
    # Test results
    results = {
        'imports': False,
        'detection': False,
        'binary_choice': False,
        'visual': False
    }
    
    # Run tests
    results['imports'] = test_imports()
    
    if results['imports']:
        results['detection'] = test_detection()
        results['binary_choice'] = test_binary_choice()
    
    results['visual'] = test_visual_stimulus()
    
    # Summary
    print("\n" + "="*60)
    print("📊 VERIFICATION RESULTS")
    print("="*60)
    
    core_working = results['imports'] and results['detection'] and results['binary_choice']
    
    if core_working:
        print("🎉 CORE SYSTEM: ✅ WORKING")
        print("\n   Available features:")
        print("   • Binary choice BCI with synthetic data")
        print("   • Real-time SSVEP detection")
        print("   • Signal processing and filtering")
        print("   • OpenBCI hardware support (when connected)")
        
        if results['visual']:
            print("   • Visual stimulus presentation")
        else:
            print("   • Visual stimulus: ⚠️  Limited (install PsychoPy)")
        
        print("\n✨ Quick test commands:")
        print("   python binary_choice_app.py --demo")
        print("   python run_ssvep.py --synthetic 10.0 --duration 5")
        
        if results['visual']:
            print("   python run_binary_stimulus.py")
    
    else:
        print("❌ CORE SYSTEM: ISSUES DETECTED")
        print("\n   Problems:")
        if not results['imports']:
            print("   • Import errors - check dependencies")
        if not results['detection']:
            print("   • SSVEP detection not working")
        if not results['binary_choice']:
            print("   • Binary choice system not working")
    
    print("\n" + "="*60)
    
    return core_working

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)