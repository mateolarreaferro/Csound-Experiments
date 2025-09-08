"""
Setup script for SSVEP BCI System
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text() if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    with open(requirements_path) as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="ssvep-bci",
    version="1.0.0",
    author="SSVEP BCI Development Team",
    author_email="contact@ssvepbci.org",
    description="A modular SSVEP brain-computer interface system for OpenBCI Cyton+Daisy",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ssvep-bci/ssvep-bci",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Healthcare Industry",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Scientific/Engineering :: Human Machine Interfaces",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "sphinx>=4.0.0",
            "sphinx-rtd-theme>=1.0.0",
        ],
        "advanced": [
            "tensorflow>=2.8.0",
            "torch>=1.11.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ssvep-calibrate=run_ssvep_calibration:main",
            "ssvep-online=run_ssvep_online:main",
        ],
    },
    include_package_data=True,
    package_data={
        "ssvep_bci": [
            "config/*.py",
            "data/*",
            "logs/.gitkeep",
        ],
    },
    keywords=[
        "brain-computer interface",
        "BCI",
        "SSVEP",
        "steady-state visual evoked potentials",
        "EEG",
        "OpenBCI",
        "neuroscience",
        "signal processing",
        "machine learning",
        "CCA",
        "frequency detection",
    ],
    project_urls={
        "Bug Reports": "https://github.com/ssvep-bci/ssvep-bci/issues",
        "Source": "https://github.com/ssvep-bci/ssvep-bci",
        "Documentation": "https://ssvep-bci.readthedocs.io/",
    },
)