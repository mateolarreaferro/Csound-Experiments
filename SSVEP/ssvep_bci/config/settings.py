"""
Configuration settings for SSVEP BCI System
"""

import numpy as np

# Hardware Configuration
HARDWARE = {
    'board': 'cyton_daisy',
    'channels': 16,
    'sampling_rate': 250,
    'serial_port': None,  # Will be auto-detected if None
}

# Electrode Configuration (10-20 system) - Optimized for SSVEP
ELECTRODES = {
    'channel_names': ['O1', 'Oz', 'O2', 'PO3', 'POz', 'PO4', 'P3', 'Pz', 
                      'P4', 'P7', 'P8', 'CP1', 'CP2', 'Cz', 'FC1', 'FC2'],
    'reference': 'earlobe',  # Options: 'earlobe', 'forehead', 'average'
    'ground': 'earlobe',
    'impedance_threshold': 5000,  # in ohms
}

# Signal Processing Configuration for SSVEP
PREPROCESSING = {
    'bandpass': (3, 45),  # Hz - broader range for SSVEP harmonics
    'notch_freq': 60,  # 60 Hz for US, 50 Hz for Europe
    'notch_width': 2,  # Hz
    'downsample_freq': None,  # Keep original sampling rate for SSVEP
    'epoch_window': (0, 4),  # seconds - longer window for SSVEP
    'baseline': None,  # No baseline correction for SSVEP
    'artifact_threshold': 150,  # microvolts for artifact rejection
    'use_ica': False,  # Enable ICA for artifact removal
}

# SSVEP Stimulus Configuration
STIMULUS = {
    'frequencies': [6.0, 7.5, 8.57, 10.0, 12.0, 15.0],  # Hz - stimulation frequencies
    'n_targets': 6,  # Number of SSVEP targets
    'layout': (2, 3),  # Grid layout for targets (rows x cols)
    'stimulus_duration': 4000,  # milliseconds - duration of each stimulus
    'rest_duration': 2000,  # milliseconds - rest between trials
    'stimulus_type': 'checkerboard',  # Options: 'checkerboard', 'square', 'sinusoidal'
    'contrast': 1.0,  # Stimulus contrast (0-1)
    'phase_shift': 0,  # Phase shift for frequencies (radians)
}

# SSVEP Target Configuration
TARGETS = {
    'commands': [
        'FORWARD', 'BACKWARD', 'LEFT', 
        'RIGHT', 'STOP', 'SELECT'
    ],
    'characters': [  # Alternative character matrix for spelling
        ['A', 'B', 'C'],
        ['D', 'E', 'F']
    ],
    'font_size': 72,
    'background_color': (0, 0, 0),  # RGB - black background
    'text_color': (255, 255, 255),  # RGB - white text
    'target_size': (200, 200),  # pixels - size of each target
    'spacing': 50,  # pixels - spacing between targets
}

# SSVEP Classification Configuration
CLASSIFIER = {
    'type': 'CCA',  # Options: 'CCA', 'FBCCA', 'PSDA', 'ensemble'
    'n_harmonics': 3,  # Number of harmonics to consider
    'filter_bank': {
        'enabled': True,
        'n_filters': 5,
        'filter_order': 4,
    },
    'window_length': 4.0,  # seconds - analysis window
    'window_overlap': 0.5,  # Overlap ratio for sliding window
    'threshold': 0.3,  # Classification threshold
}

# Feature Extraction for SSVEP
FEATURES = {
    'methods': ['CCA', 'PSDA'],  # Methods to use: CCA, PSDA, MSI
    'cca': {
        'n_components': 1,
        'reference_signals': 'sine_cosine',  # Options: 'sine_cosine', 'square'
    },
    'psda': {
        'window_function': 'hann',
        'nperseg': 250,  # Samples per segment for Welch's method
        'noverlap': 125,  # Overlap samples
    },
    'msi': {
        'n_cycles': 5,  # Number of cycles for template
    }
}

# Real-time Processing Configuration
REALTIME = {
    'buffer_size': 1000,  # samples
    'update_interval': 100,  # milliseconds
    'decision_interval': 500,  # milliseconds between decisions
    'min_confidence': 0.6,  # Minimum confidence for decision
}

# Calibration Configuration for SSVEP
CALIBRATION = {
    'n_trials_per_target': 10,  # Number of trials per frequency
    'trial_duration': 4000,  # milliseconds
    'randomize_order': True,
    'break_duration': 2000,  # milliseconds between trials
    'save_templates': True,  # Save individual templates
}

# Data Storage Configuration
DATA_STORAGE = {
    'format': 'edf',  # Options: 'edf', 'csv', 'fif'
    'save_raw': True,
    'save_epochs': True,
    'save_features': True,
    'compression': True,
    'data_dir': 'data/',
    'log_dir': 'logs/',
}

# Performance Metrics Configuration
METRICS = {
    'calculate_itr': True,  # Information Transfer Rate
    'accuracy_window': 10,  # Number of recent predictions for accuracy
    'confusion_matrix': True,
    'log_performance': True,
    'real_time_feedback': True,
}

# UI Configuration
UI = {
    'fullscreen': False,
    'window_size': (1920, 1080),
    'refresh_rate': 60,  # Hz - monitor refresh rate
    'vsync': True,  # Enable vertical sync
    'show_frequency_labels': True,
    'show_confidence': True,
    'show_spectrum': True,  # Show real-time spectrum
    'feedback_duration': 1000,  # milliseconds
}

# Frequency Analysis Configuration
FREQUENCY_ANALYSIS = {
    'fft_size': 2048,
    'window': 'hann',
    'detrend': 'constant',
    'scaling': 'spectrum',
    'harmonics_to_analyze': [1, 2, 3],  # Fundamental and harmonics
}