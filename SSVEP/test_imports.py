"""Test all imports and dependencies"""

import sys
import os
import importlib

def test_import(module_name, from_module=None, description=""):
    """Test importing a module or function"""
    try:
        if from_module:
            module = importlib.import_module(from_module)
            getattr(module, module_name)
            status = "✓"
        else:
            importlib.import_module(module_name)
            status = "✓"
    except ImportError as e:
        status = f"✗ {str(e)}"
    except AttributeError as e:
        status = f"✗ {str(e)}"
    except Exception as e:
        status = f"✗ {str(e)}"
    
    print(f"{status:60s} {description}")

def main():
    """Test all imports required by the SSVEP BCI system"""
    
    print("\n" + "="*60)
    print("TESTING ALL IMPORTS AND DEPENDENCIES")
    print("="*60)
    
    # Core Python modules
    print("\n1. Core Python modules:")
    print("-" * 40)
    test_import("sys", description="System-specific parameters")
    test_import("os", description="Operating system interface")
    test_import("time", description="Time-related functions")
    test_import("threading", description="Thread-based parallelism")
    test_import("logging", description="Logging facility")
    test_import("argparse", description="Command-line argument parsing")
    test_import("collections", description="Specialized container datatypes")
    
    # Scientific computing
    print("\n2. Scientific computing:")
    print("-" * 40)
    test_import("numpy", description="Numerical computing")
    test_import("scipy", description="Scientific computing")
    test_import("scipy.signal", description="Signal processing")
    
    # Visualization
    print("\n3. Visualization:")
    print("-" * 40)
    test_import("matplotlib", description="Plotting library")
    test_import("matplotlib.pyplot", description="Pyplot interface")
    
    # BCI/EEG specific
    print("\n4. BCI/EEG specific:")
    print("-" * 40)
    test_import("brainflow", description="OpenBCI interface")
    test_import("BoardShim", "brainflow.board_shim", "BrainFlow board interface")
    test_import("BrainFlowInputParams", "brainflow.board_shim", "BrainFlow parameters")
    test_import("BoardIds", "brainflow.board_shim", "Board ID constants")
    test_import("DataFilter", "brainflow.data_filter", "BrainFlow data filtering")
    
    # Stimulus presentation
    print("\n5. Stimulus presentation:")
    print("-" * 40)
    test_import("psychopy", description="Psychology experiment framework")
    test_import("visual", "psychopy", "Visual stimuli")
    test_import("core", "psychopy", "Core timing functions")
    test_import("event", "psychopy", "Event handling")
    test_import("monitors", "psychopy", "Monitor management")
    
    # Our custom modules
    print("\n6. Custom SSVEP modules:")
    print("-" * 40)
    
    # Add src to path
    sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
    
    test_import("config", description="Configuration settings")
    test_import("acquisition", description="Data acquisition")
    test_import("filters", description="Signal processing filters")
    test_import("detector_psd", description="PSD-based SSVEP detector")
    test_import("utils", description="Utility functions")
    test_import("synthetic", description="Synthetic data generation")
    
    # Test specific classes and functions
    print("\n7. Specific classes and functions:")
    print("-" * 40)
    test_import("OpenBCIAcquisition", "acquisition", "OpenBCI acquisition class")
    test_import("SSVEPFilters", "filters", "SSVEP filters class")
    test_import("PSDDetector", "detector_psd", "PSD detector class")
    test_import("TimeSeriesBuffer", "utils", "Time series buffer")
    test_import("StableVoteFilter", "utils", "Stable vote filter")
    test_import("SyntheticSSVEPGenerator", "synthetic", "Synthetic generator")
    test_import("synth_ssvep", "synthetic", "Synthetic SSVEP function")
    
    # Test main application files
    print("\n8. Main application files:")
    print("-" * 40)
    
    # Test if files can be imported
    app_files = [
        ("run_ssvep", "Main SSVEP detection system"),
        ("run_stimulus", "Visual stimulus presentation"),
        ("binary_choice_app", "Binary choice BCI app"),
        ("run_binary_stimulus", "Binary choice stimulus"),
    ]
    
    for module, desc in app_files:
        try:
            importlib.import_module(module)
            print(f"{'✓':60s} {desc}")
        except Exception as e:
            print(f"{'✗ Import error':60s} {desc}")
    
    print("\n" + "="*60)
    print("IMPORT TEST COMPLETED")
    print("="*60)

if __name__ == "__main__":
    main()