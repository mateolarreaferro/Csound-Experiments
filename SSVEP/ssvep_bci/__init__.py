"""
SSVEP BCI System
A Brain-Computer Interface system using Steady-State Visual Evoked Potentials
"""

__version__ = "1.0.0"
__author__ = "SSVEP BCI Team"

from .modules.acquisition import SSVEPAcquisition
from .modules.ssvep_stimulus import SSVEPStimulus
from .modules.ssvep_classifier import SSVEPClassifier
from .modules.ssvep_preprocessing import SSVEPPreprocessor

__all__ = [
    'SSVEPAcquisition',
    'SSVEPStimulus', 
    'SSVEPClassifier',
    'SSVEPPreprocessor'
]