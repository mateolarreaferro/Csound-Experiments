"""Test rapid switching between choices"""

import time
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from binary_choice_app import BinaryChoiceBCI

def test_rapid_switching():
    """Test rapid switching between left and right choices"""
    
    print("\n" + "="*50)
    print("RAPID SWITCHING TEST")
    print("="*50)
    
    # Track detections
    detections = []
    detection_times = []
    
    def callback(choice):
        detection_time = time.time()
        detections.append(choice)
        detection_times.append(detection_time)
        print(f"[{len(detections)}] Detected: {choice.upper()} at {detection_time:.2f}")
    
    # Create BCI with shorter hold time for faster switching
    bci = BinaryChoiceBCI(
        freq_left=10.0,
        freq_right=15.0,
        use_synthetic=True,
        callback=callback
    )
    
    # Reduce hold time for faster detection
    bci.vote_hold_ms = 300  # 300ms instead of 500ms
    bci.window_sec = 1.5    # Shorter window for faster updates
    
    if not bci.start():
        print("Failed to start BCI")
        return
    
    # Rapid switching sequence
    sequence = [
        ("left", 1.5),
        ("right", 1.5),
        ("left", 1.5),
        ("right", 1.5),
        ("left", 1.0),
        ("right", 1.0),
        ("left", 1.0),
        ("right", 1.0),
    ]
    
    print("\nStarting rapid switching sequence...")
    print("-"*50)
    
    start_time = time.time()
    
    for target, duration in sequence:
        print(f"\n[TEST] Switching to {target.upper()} for {duration}s...")
        bci.set_target(target)
        time.sleep(duration)
    
    # Final rest
    print("\n[TEST] Resting...")
    bci.set_target("none")
    time.sleep(1)
    
    total_time = time.time() - start_time
    
    # Stop system
    bci.stop()
    
    # Analyze results
    print("\n" + "="*50)
    print("RESULTS")
    print("="*50)
    print(f"Total test time: {total_time:.1f}s")
    print(f"Total detections: {len(detections)}")
    print(f"Expected switches: {len(sequence)}")
    
    if len(detections) > 0:
        print(f"\nDetection sequence: {' -> '.join(detections)}")
        
        # Calculate switch times
        if len(detection_times) > 1:
            switch_times = []
            for i in range(1, len(detection_times)):
                switch_time = detection_times[i] - detection_times[i-1]
                switch_times.append(switch_time)
            
            print(f"\nSwitch times:")
            for i, st in enumerate(switch_times):
                print(f"  Switch {i+1}: {st:.2f}s")
            
            avg_switch = sum(switch_times) / len(switch_times)
            print(f"\nAverage switch time: {avg_switch:.2f}s")
    
    print("="*50)

if __name__ == "__main__":
    test_rapid_switching()