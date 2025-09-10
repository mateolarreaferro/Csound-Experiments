#!/usr/bin/env python3
"""Fix pylsl to find the LSL library on macOS"""

import os
import shutil
import site

# Get the pylsl package location
site_packages = site.getsitepackages()[0]
pylsl_lib_dir = os.path.join(site_packages, 'pylsl', 'lib')

print(f"Fixing pylsl in: {pylsl_lib_dir}")

# Check if liblsl exists in homebrew
homebrew_lsl = "/opt/homebrew/lib/liblsl.dylib"
if not os.path.exists(homebrew_lsl):
    print(f"ERROR: LSL not found at {homebrew_lsl}")
    print("Please run: brew install labstreaminglayer/tap/lsl")
    exit(1)

# Copy the library to pylsl's lib folder
target = os.path.join(pylsl_lib_dir, "liblsl.dylib")
print(f"Copying {homebrew_lsl} to {target}")
shutil.copy2(homebrew_lsl, target)

print("✓ Fixed! pylsl should now work without DYLD_LIBRARY_PATH")
print("\nTest with: python -c 'from pylsl import StreamInlet'")