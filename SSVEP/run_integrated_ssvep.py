#!/usr/bin/env python3
"""Integrated SSVEP system with visual stimulus, calibration, and real-time feedback"""

import numpy as np
import pygame
import time
import threading
import queue
from pylsl import StreamInlet, resolve_streams
from scipy import signal
from scipy.signal import welch
from collections import deque
import sys
import os
import logging

# Add local src directory
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from utils import StableVoteFilter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# SSVEP parameters
TARGET_FREQS = [10.0, 15.0]  # Hz
HARMONICS = 2
WINDOW_SEC = 2.0
UPDATE_RATE = 4  # Hz

class IntegratedSSVEP:
    """Combined visual stimulus and SSVEP detector with calibration"""
    
    def __init__(self, fullscreen=False):
        # Visual parameters
        self.frequencies = TARGET_FREQS
        self.labels = ["LEFT", "RIGHT"]
        self.fullscreen = fullscreen
        self.window_size = (1024, 600)
        
        # Visual elements
        self.box_size = 250
        self.separation = 400
        
        # Colors
        self.bg_color = (128, 128, 128)
        self.white = (255, 255, 255)
        self.black = (0, 0, 0)
        self.red = (255, 0, 0)
        self.green = (0, 255, 0)
        self.blue = (0, 100, 255)
        self.yellow = (255, 255, 0)
        
        # LSL connection
        self.inlet = None
        self.fs = None
        self.n_channels = None
        self.buffer = deque(maxlen=500)  # Will be resized after connection
        
        # Detection parameters
        self.snr_threshold = 2.0
        self.margin_ratio = 1.5
        self.ema_alpha = 0.3
        self.hold_ms = 500
        
        # Calibration data
        self.calibration_data = {freq: [] for freq in self.frequencies}
        self.baseline_noise = None
        self.optimal_channels = None
        self.personalized_thresholds = None
        
        # State management
        self.running = False
        self.calibrating = False
        self.stimulating = False
        self.current_selection = None
        self.confidence = 0.0
        
        # Smoothing and filtering
        self.smoothed_powers = np.zeros(len(self.frequencies))
        self.vote_filter = StableVoteFilter(hold_duration_ms=self.hold_ms)
        
        # Communication queue between threads
        self.detection_queue = queue.Queue()
        
        # Initialize Pygame
        pygame.init()
        
    def setup_display(self):
        """Initialize Pygame display"""
        if self.fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.window_size = self.screen.get_size()
        else:
            self.screen = pygame.display.set_mode(self.window_size)
        
        pygame.display.set_caption("SSVEP BCI - Integrated System")
        
        # Fonts
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        self.large_font = pygame.font.Font(None, 48)
        
        # Clock
        self.clock = pygame.time.Clock()
        
        # Calculate positions
        center_x = self.window_size[0] // 2
        center_y = self.window_size[1] // 2
        
        self.left_pos = (center_x - self.separation // 2 - self.box_size // 2,
                        center_y - self.box_size // 2)
        self.right_pos = (center_x + self.separation // 2 - self.box_size // 2,
                         center_y - self.box_size // 2)
    
    def connect_lsl(self):
        """Connect to LSL stream from OpenBCI GUI"""
        logger.info("Looking for LSL stream from OpenBCI GUI...")
        
        streams = resolve_streams(wait_time=5.0)
        
        if not streams:
            logger.error("No LSL stream found. Make sure OpenBCI GUI is streaming.")
            return False
        
        self.inlet = StreamInlet(streams[0])
        info = self.inlet.info()
        
        self.fs = info.nominal_srate()
        self.n_channels = info.channel_count()
        
        logger.info(f"Connected to LSL stream: {info.name()}")
        logger.info(f"Sampling rate: {self.fs} Hz, Channels: {self.n_channels}")
        
        # Update buffer size
        self.buffer = deque(maxlen=int(self.fs * WINDOW_SEC))
        
        return True
    
    def find_optimal_channels(self, data):
        """Find channels with best SSVEP response"""
        if self.n_channels >= 16:
            # Test occipital channels (typically 7-10 for O1, O2, Oz, POz)
            test_channels = list(range(7, min(11, self.n_channels)))
        elif self.n_channels >= 8:
            # Use last 4 channels
            test_channels = list(range(max(0, self.n_channels-4), self.n_channels))
        else:
            test_channels = list(range(self.n_channels))
        
        # Compute SNR for each channel
        channel_snrs = []
        for ch in test_channels:
            ch_data = data[ch:ch+1, :]
            snr_sum = 0
            for freq in self.frequencies:
                snr = self.compute_ssvep_power(ch_data, freq)
                snr_sum += snr
            channel_snrs.append(snr_sum)
        
        # Select top 3 channels
        best_indices = np.argsort(channel_snrs)[-3:]
        self.optimal_channels = [test_channels[i] for i in best_indices]
        
        logger.info(f"Optimal channels selected: {self.optimal_channels}")
        return self.optimal_channels
    
    def compute_ssvep_power(self, data, freq):
        """Compute SSVEP power with improved processing"""
        # Bandpass filter
        sos = signal.butter(4, [5, 45], btype='band', fs=self.fs, output='sos')
        filtered = signal.sosfiltfilt(sos, data, axis=1)
        
        # Notch filter for power line noise
        notch_sos = signal.butter(2, [59, 61], btype='bandstop', fs=self.fs, output='sos')
        filtered = signal.sosfiltfilt(notch_sos, filtered, axis=1)
        
        # Compute PSD
        nperseg = min(data.shape[1], int(self.fs * 1.5))
        freqs, psd = welch(filtered, fs=self.fs, nperseg=nperseg, 
                          noverlap=nperseg//2, axis=1)
        
        # Average across channels
        psd_mean = np.mean(psd, axis=0)
        
        # Target frequency power
        target_idx = np.argmin(np.abs(freqs - freq))
        signal_power = psd_mean[target_idx]
        
        # Add harmonic
        if HARMONICS >= 2:
            harmonic_idx = np.argmin(np.abs(freqs - freq * 2))
            if harmonic_idx < len(psd_mean):
                signal_power += 0.3 * psd_mean[harmonic_idx]
        
        # Calculate noise
        noise_band = np.where((freqs >= freq - 2) & (freqs <= freq + 2) & 
                              (np.abs(freqs - freq) > 0.5))[0]
        if len(noise_band) > 0:
            noise_power = np.median(psd_mean[noise_band])
            if self.baseline_noise is not None:
                noise_power = max(noise_power, self.baseline_noise)
            snr = signal_power / (noise_power + 1e-10)
        else:
            snr = signal_power
        
        return snr
    
    def calibration_phase(self):
        """Run calibration to optimize detection parameters"""
        logger.info("Starting calibration phase...")
        self.calibrating = True
        
        # Collect baseline (no stimulus)
        logger.info("Collecting baseline - please relax and look at center")
        baseline_data = []
        start_time = time.time()
        
        while time.time() - start_time < 5.0:
            chunk, _ = self.inlet.pull_chunk(timeout=0.0, max_samples=32)
            if chunk:
                baseline_data.extend(chunk)
        
        if len(baseline_data) > self.fs:
            baseline_array = np.array(baseline_data[-int(self.fs*2):]).T
            
            # Find optimal channels
            self.find_optimal_channels(baseline_array)
            
            # Calculate baseline noise
            noise_levels = []
            for freq in range(5, 30):
                if freq not in self.frequencies:
                    noise_levels.append(self.compute_ssvep_power(baseline_array, freq))
            self.baseline_noise = np.median(noise_levels)
            logger.info(f"Baseline noise level: {self.baseline_noise:.2f}")
        
        # Calibrate each frequency
        for i, freq in enumerate(self.frequencies):
            logger.info(f"Look at {self.labels[i]} ({freq}Hz) for 10 seconds...")
            
            calib_data = []
            start_time = time.time()
            
            while time.time() - start_time < 10.0:
                chunk, _ = self.inlet.pull_chunk(timeout=0.0, max_samples=32)
                if chunk:
                    for sample in chunk:
                        self.buffer.append(sample)
                
                if len(self.buffer) >= self.fs * 1.5:
                    data = np.array(self.buffer)
                    if self.optimal_channels:
                        data = data[:, self.optimal_channels].T
                    else:
                        data = data.T
                    
                    snr = self.compute_ssvep_power(data, freq)
                    self.calibration_data[freq].append(snr)
            
            logger.info(f"Calibration for {freq}Hz complete")
            time.sleep(2)  # Rest period
        
        # Calculate personalized thresholds
        self.calculate_thresholds()
        
        self.calibrating = False
        logger.info("Calibration complete!")
    
    def calculate_thresholds(self):
        """Calculate personalized detection thresholds from calibration"""
        if not any(self.calibration_data.values()):
            return
        
        # Calculate statistics for each frequency
        stats = {}
        for freq in self.frequencies:
            if self.calibration_data[freq]:
                data = np.array(self.calibration_data[freq])
                stats[freq] = {
                    'mean': np.mean(data),
                    'std': np.std(data),
                    'max': np.max(data),
                    'p75': np.percentile(data, 75)
                }
        
        # Set adaptive thresholds
        if stats:
            min_snr = min(s['p75'] for s in stats.values())
            self.snr_threshold = max(1.5, min_snr * 0.7)  # 70% of weakest response
            
            logger.info(f"Personalized SNR threshold: {self.snr_threshold:.2f}")
            for freq, stat in stats.items():
                logger.info(f"{freq}Hz - Mean: {stat['mean']:.2f}, Max: {stat['max']:.2f}")
    
    def detection_thread(self):
        """Background thread for SSVEP detection"""
        last_update = time.time()
        
        while self.running:
            try:
                # Pull data from LSL
                chunk, _ = self.inlet.pull_chunk(timeout=0.0, max_samples=32)
                
                if chunk:
                    for sample in chunk:
                        self.buffer.append(sample)
                
                # Process at UPDATE_RATE
                if (time.time() - last_update > 1.0/UPDATE_RATE and 
                    len(self.buffer) >= self.fs * 0.5 and 
                    self.stimulating):
                    
                    # Convert buffer to array
                    data = np.array(self.buffer)
                    
                    # Use optimal channels if available
                    if self.optimal_channels:
                        data = data[:, self.optimal_channels].T
                    else:
                        data = data.T
                    
                    # Compute power for each frequency
                    powers = []
                    for freq in self.frequencies:
                        power = self.compute_ssvep_power(data, freq)
                        powers.append(power)
                    
                    # Smooth estimates
                    powers = np.array(powers)
                    self.smoothed_powers = (
                        self.ema_alpha * powers + 
                        (1 - self.ema_alpha) * self.smoothed_powers
                    )
                    powers = self.smoothed_powers
                    
                    # Detection logic
                    if (np.max(powers) > self.snr_threshold and 
                        np.max(powers) > np.min(powers) * self.margin_ratio):
                        
                        winner = int(np.argmax(powers))
                        stable = self.vote_filter.update(winner)
                        
                        # Calculate confidence
                        self.confidence = (powers[winner] - self.snr_threshold) / self.snr_threshold
                        self.confidence = min(1.0, self.confidence)
                        
                        # Send detection result
                        self.detection_queue.put({
                            'selection': stable,
                            'candidate': winner,
                            'powers': powers.copy(),
                            'confidence': self.confidence
                        })
                    else:
                        self.vote_filter.reset()
                        self.detection_queue.put({
                            'selection': None,
                            'candidate': None,
                            'powers': powers.copy(),
                            'confidence': 0.0
                        })
                    
                    last_update = time.time()
                    
            except Exception as e:
                logger.error(f"Detection error: {e}")
                time.sleep(0.1)
    
    def draw_interface(self):
        """Draw the main interface"""
        # Clear screen
        self.screen.fill(self.bg_color)
        
        # Title
        title = "SSVEP BCI System"
        if self.calibrating:
            title += " - CALIBRATION MODE"
        
        text = self.large_font.render(title, True, self.white)
        text_rect = text.get_rect(centerx=self.window_size[0]//2, y=20)
        self.screen.blit(text, text_rect)
        
        # Instructions
        if not self.stimulating:
            instructions = [
                "Press C to calibrate (recommended first)",
                "Press SPACE to start stimulus",
                "Press ESC to exit"
            ]
        else:
            instructions = [
                f"Look at a box to make selection",
                f"Left: {self.frequencies[0]}Hz | Right: {self.frequencies[1]}Hz",
                "Press SPACE to stop"
            ]
        
        y_offset = 80
        for line in instructions:
            text = self.small_font.render(line, True, self.white)
            text_rect = text.get_rect(centerx=self.window_size[0]//2, y=y_offset)
            self.screen.blit(text, text_rect)
            y_offset += 25
    
    def draw_boxes(self, left_color, right_color):
        """Draw flickering boxes with selection feedback"""
        # Get current detection result
        detection = None
        try:
            detection = self.detection_queue.get_nowait()
            self.current_selection = detection.get('selection')
            self.confidence = detection.get('confidence', 0)
        except queue.Empty:
            pass
        
        # Draw left box
        left_border_color = self.black
        left_border_width = 3
        
        if self.current_selection == 0:
            left_border_color = self.green
            left_border_width = 6
        elif detection and detection.get('candidate') == 0:
            left_border_color = self.yellow
            left_border_width = 4
        
        pygame.draw.rect(self.screen, left_color,
                        (self.left_pos[0], self.left_pos[1], 
                         self.box_size, self.box_size))
        pygame.draw.rect(self.screen, left_border_color,
                        (self.left_pos[0], self.left_pos[1], 
                         self.box_size, self.box_size), left_border_width)
        
        # Draw right box
        right_border_color = self.black
        right_border_width = 3
        
        if self.current_selection == 1:
            right_border_color = self.green
            right_border_width = 6
        elif detection and detection.get('candidate') == 1:
            right_border_color = self.yellow
            right_border_width = 4
        
        pygame.draw.rect(self.screen, right_color,
                        (self.right_pos[0], self.right_pos[1], 
                         self.box_size, self.box_size))
        pygame.draw.rect(self.screen, right_border_color,
                        (self.right_pos[0], self.right_pos[1], 
                         self.box_size, self.box_size), right_border_width)
        
        # Labels
        for i, (pos, label) in enumerate([(self.left_pos, self.labels[0]), 
                                           (self.right_pos, self.labels[1])]):
            text = self.font.render(label, True, self.white)
            text_rect = text.get_rect(centerx=pos[0] + self.box_size//2,
                                      bottom=pos[1] - 20)
            self.screen.blit(text, text_rect)
        
        # Draw detection feedback
        if self.current_selection is not None:
            selection_text = f"SELECTED: {self.labels[self.current_selection]}"
            color = self.green
        elif detection and detection.get('candidate') is not None:
            selection_text = f"Detecting: {self.labels[detection['candidate']]}"
            color = self.yellow
        else:
            selection_text = "Looking for signal..."
            color = self.white
        
        text = self.font.render(selection_text, True, color)
        text_rect = text.get_rect(centerx=self.window_size[0]//2,
                                  bottom=self.window_size[1] - 80)
        self.screen.blit(text, text_rect)
        
        # Confidence bar
        if self.confidence > 0:
            bar_width = 300
            bar_height = 20
            bar_x = (self.window_size[0] - bar_width) // 2
            bar_y = self.window_size[1] - 50
            
            # Background
            pygame.draw.rect(self.screen, self.black,
                           (bar_x, bar_y, bar_width, bar_height))
            
            # Fill based on confidence
            fill_width = int(bar_width * self.confidence)
            if self.confidence > 0.7:
                bar_color = self.green
            elif self.confidence > 0.4:
                bar_color = self.yellow
            else:
                bar_color = self.red
            
            pygame.draw.rect(self.screen, bar_color,
                           (bar_x, bar_y, fill_width, bar_height))
            
            # Border
            pygame.draw.rect(self.screen, self.white,
                           (bar_x, bar_y, bar_width, bar_height), 2)
        
        # SNR display
        if detection and detection.get('powers') is not None:
            powers = detection['powers']
            for i, (freq, power) in enumerate(zip(self.frequencies, powers)):
                text = f"{freq}Hz SNR: {power:.2f}"
                color = self.green if power > self.snr_threshold else self.white
                snr_text = self.small_font.render(text, True, color)
                snr_rect = snr_text.get_rect(x=20, y=self.window_size[1] - 100 + i*25)
                self.screen.blit(snr_text, snr_rect)
    
    def update_flicker(self, start_time):
        """Calculate flicker states"""
        current_time = time.time()
        elapsed = current_time - start_time
        
        # Calculate phases
        left_phase = np.sin(2 * np.pi * self.frequencies[0] * elapsed)
        right_phase = np.sin(2 * np.pi * self.frequencies[1] * elapsed)
        
        # Convert to colors
        left_intensity = int((left_phase + 1) * 127.5)
        right_intensity = int((right_phase + 1) * 127.5)
        
        left_color = (left_intensity, left_intensity, left_intensity)
        right_color = (right_intensity, right_intensity, right_intensity)
        
        return left_color, right_color
    
    def run(self):
        """Main application loop"""
        # Setup display
        self.setup_display()
        
        # Connect to LSL
        if not self.connect_lsl():
            logger.error("Failed to connect to LSL stream")
            return
        
        # Start detection thread
        self.running = True
        detection_thread = threading.Thread(target=self.detection_thread)
        detection_thread.daemon = True
        detection_thread.start()
        
        # Main loop
        start_time = None
        
        logger.info("System ready. Press C to calibrate, SPACE to start.")
        
        while self.running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_SPACE:
                        if not self.calibrating:
                            self.stimulating = not self.stimulating
                            if self.stimulating:
                                start_time = time.time()
                                logger.info("Stimulus started")
                            else:
                                logger.info("Stimulus stopped")
                    elif event.key == pygame.K_c:
                        if not self.stimulating:
                            # Run calibration in separate thread
                            calib_thread = threading.Thread(target=self.calibration_phase)
                            calib_thread.daemon = True
                            calib_thread.start()
            
            # Draw interface
            self.draw_interface()
            
            # Draw stimulus boxes
            if self.stimulating and start_time:
                left_color, right_color = self.update_flicker(start_time)
                self.draw_boxes(left_color, right_color)
            elif not self.calibrating:
                # Static boxes when not stimulating
                self.draw_boxes(self.white, self.white)
            
            # Calibration display
            if self.calibrating:
                calib_text = "Please follow the on-screen instructions"
                text = self.font.render(calib_text, True, self.yellow)
                text_rect = text.get_rect(centerx=self.window_size[0]//2,
                                         centery=self.window_size[1]//2)
                self.screen.blit(text, text_rect)
            
            # Update display
            pygame.display.flip()
            self.clock.tick(60)
        
        # Cleanup
        pygame.quit()
        logger.info("System shutdown")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Integrated SSVEP BCI System')
    parser.add_argument('--fullscreen', action='store_true',
                       help='Run in fullscreen mode')
    
    args = parser.parse_args()
    
    # Create and run system
    system = IntegratedSSVEP(fullscreen=args.fullscreen)
    
    try:
        system.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()