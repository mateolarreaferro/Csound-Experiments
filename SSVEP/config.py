"""Configuration for SSVEP BCI system with OpenBCI Cyton + Daisy"""

# Board configuration
BOARD_ID = "CYTON_DAISY"     # or "CYTON" if using 8-ch
SERIAL_PORT = "COM5"          # e.g. COM5 on Windows, /dev/tty.usbserial-DMxxxx on macOS
                              # On macOS, find with: ls /dev/tty.usbserial*

# Signal processing parameters
WINDOW_SEC = 2.0              # analysis window length in seconds
STEP_SEC = 0.2                # hop size in seconds (how often to update)
BANDPASS = (6.0, 45.0)        # Hz - bandpass filter range
NOTCH = 60.0                  # Hz - set to 50.0 for 50 Hz regions
NOTCH_Q = 30.0                # Notch filter quality factor

# SSVEP detection parameters
FREQS = [10.0, 15.0]  # Two target frequencies for binary choice (60 Hz monitor friendly)
# Alternative frequency pairs that work well:
# FREQS = [8.0, 12.0]   # Good separation, both divide into 60Hz
# FREQS = [7.5, 15.0]   # Maximum separation
# FREQS = [10.0, 12.0]  # Closer frequencies, may be easier for some users
HARMONICS = 2                 # 1 = fundamental only, 2 = add 2nd harmonic
USE_CHANNELS = None           # None = use all EEG channels, or list like [0,1,2,7,8,9]
SNR_NEIGHBOR_BW = 1.0         # Hz - sidebands for noise floor calculation
SNR_EXCLUDE_BW = 0.3          # Hz - exclude ±0.3 Hz around peak from noise floor

# Decision parameters
VOTE_HOLD_MS = 500            # ms - must hold the top class this long before select
MIN_SNR_THRESHOLD = 1.5       # Minimum SNR to consider a detection valid

# Display parameters (for stimulus)
STIM_SIZE = 200               # Size of each flicker box in pixels
STIM_SPACING = 300            # Spacing between boxes
WINDOW_WIDTH = 1024           # Stimulus window width
WINDOW_HEIGHT = 768           # Stimulus window height
FULLSCREEN = False            # Set to True for fullscreen mode

# System parameters
LOGGING = True                # Enable/disable detailed logging
LOG_LEVEL = "INFO"            # DEBUG, INFO, WARNING, ERROR
BUFFER_DURATION = 5.0         # Seconds of data to keep in ring buffer