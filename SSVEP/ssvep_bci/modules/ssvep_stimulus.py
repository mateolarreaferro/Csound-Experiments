"""
SSVEP Stimulus Presentation Module
Handles frequency-based visual stimulation for SSVEP BCI
"""

import numpy as np
import time
import pygame
import threading
from typing import List, Dict, Optional, Callable, Tuple
from collections import deque
import math

class SSVEPStimulus:
    """
    Manages SSVEP stimulus presentation with precise frequency control
    """
    
    def __init__(self, config: Dict, marker_callback: Optional[Callable] = None):
        """
        Initialize SSVEP stimulus system
        
        Args:
            config: Configuration dictionary from settings
            marker_callback: Function to call when inserting markers
        """
        self.config = config
        self.marker_callback = marker_callback
        
        # Stimulus settings
        self.frequencies = config['STIMULUS']['frequencies']
        self.n_targets = config['STIMULUS']['n_targets']
        self.layout = config['STIMULUS']['layout']
        self.stimulus_type = config['STIMULUS']['stimulus_type']
        self.contrast = config['STIMULUS']['contrast']
        
        # Target configuration
        self.commands = config['TARGETS']['commands']
        self.target_size = config['TARGETS']['target_size']
        self.spacing = config['TARGETS']['spacing']
        self.font_size = config['TARGETS']['font_size']
        self.bg_color = config['TARGETS']['background_color']
        self.text_color = config['TARGETS']['text_color']
        
        # Timing settings
        self.stimulus_duration = config['STIMULUS']['stimulus_duration'] / 1000.0
        self.rest_duration = config['STIMULUS']['rest_duration'] / 1000.0
        
        # Display settings
        self.fullscreen = config['UI']['fullscreen']
        self.window_size = config['UI']['window_size']
        self.refresh_rate = config['UI']['refresh_rate']
        self.vsync = config['UI']['vsync']
        self.show_frequency_labels = config['UI']['show_frequency_labels']
        self.show_spectrum = config['UI']['show_spectrum']
        
        # Pygame initialization
        pygame.init()
        self.screen = None
        self.font = None
        self.small_font = None
        self.clock = pygame.time.Clock()
        
        # Target positions and properties
        self.target_positions = {}
        self.target_rects = {}
        self.target_surfaces = {}
        self.flickering_surfaces = {}
        
        # Phase tracking for each frequency
        self.phases = {freq: 0.0 for freq in self.frequencies}
        self.last_update_time = time.time()
        
        # Control flags
        self.running = False
        self.stimulating = False
        self.current_target = None
        
        # Performance monitoring
        self.frame_times = deque(maxlen=100)
        self.actual_frequencies = {freq: freq for freq in self.frequencies}
        
        # Marker codes
        self.marker_codes = self._generate_marker_codes()
        
        # Thread for stimulus control
        self.stimulus_thread = None
        self.stop_event = threading.Event()
        
    def initialize_display(self) -> bool:
        """
        Initialize the Pygame display with vsync support
        
        Returns:
            Success status
        """
        try:
            # Set up display with vsync if enabled
            flags = pygame.DOUBLEBUF | pygame.HWSURFACE
            if self.fullscreen:
                flags |= pygame.FULLSCREEN
                
            if self.vsync:
                # Try to enable vsync
                pygame.display.gl_set_attribute(pygame.GL_SWAP_CONTROL, 1)
            
            if self.fullscreen:
                self.screen = pygame.display.set_mode((0, 0), flags)
                self.window_size = self.screen.get_size()
            else:
                self.screen = pygame.display.set_mode(self.window_size, flags)
            
            pygame.display.set_caption("SSVEP BCI System")
            
            # Initialize fonts
            self.font = pygame.font.Font(None, self.font_size)
            self.small_font = pygame.font.Font(None, 24)
            
            # Calculate target positions
            self._calculate_target_positions()
            
            # Create target surfaces
            self._create_target_surfaces()
            
            # Initial draw
            self.draw_interface()
            pygame.display.flip()
            
            self.running = True
            print(f"Display initialized: {self.window_size[0]}x{self.window_size[1]} @ {self.refresh_rate}Hz")
            return True
            
        except Exception as e:
            print(f"Failed to initialize display: {e}")
            return False
    
    def _calculate_target_positions(self):
        """Calculate positions for SSVEP targets"""
        rows, cols = self.layout
        target_width, target_height = self.target_size
        
        # Calculate total grid size
        grid_width = cols * target_width + (cols - 1) * self.spacing
        grid_height = rows * target_height + (rows - 1) * self.spacing
        
        # Center the grid
        start_x = (self.window_size[0] - grid_width) // 2
        start_y = (self.window_size[1] - grid_height) // 2
        
        # Calculate positions for each target
        for idx in range(min(self.n_targets, len(self.frequencies))):
            row = idx // cols
            col = idx % cols
            
            x = start_x + col * (target_width + self.spacing)
            y = start_y + row * (target_height + self.spacing)
            
            rect = pygame.Rect(x, y, target_width, target_height)
            self.target_positions[idx] = (x + target_width // 2, y + target_height // 2)
            self.target_rects[idx] = rect
    
    def _create_target_surfaces(self):
        """Create surfaces for each target"""
        for idx in range(min(self.n_targets, len(self.frequencies))):
            # Create base surface (off state)
            base_surface = pygame.Surface(self.target_size)
            base_surface.fill(self.bg_color)
            
            # Add border
            pygame.draw.rect(base_surface, (100, 100, 100), 
                           base_surface.get_rect(), 2)
            
            # Add command text
            if idx < len(self.commands):
                text = self.commands[idx]
                text_surface = self.font.render(text, True, self.text_color)
                text_rect = text_surface.get_rect(center=(self.target_size[0]//2, 
                                                         self.target_size[1]//2))
                base_surface.blit(text_surface, text_rect)
            
            # Add frequency label if enabled
            if self.show_frequency_labels:
                freq_text = f"{self.frequencies[idx]:.1f} Hz"
                freq_surface = self.small_font.render(freq_text, True, (150, 150, 150))
                freq_rect = freq_surface.get_rect(bottomright=(self.target_size[0]-5, 
                                                               self.target_size[1]-5))
                base_surface.blit(freq_surface, freq_rect)
            
            self.target_surfaces[idx] = base_surface
            
            # Create flickering surface based on stimulus type
            if self.stimulus_type == 'checkerboard':
                self.flickering_surfaces[idx] = self._create_checkerboard_surface(idx)
            elif self.stimulus_type == 'square':
                self.flickering_surfaces[idx] = self._create_square_surface(idx)
            else:  # sinusoidal
                self.flickering_surfaces[idx] = self._create_sinusoidal_surfaces(idx)
    
    def _create_checkerboard_surface(self, target_idx: int) -> pygame.Surface:
        """Create checkerboard pattern for flickering"""
        surface = pygame.Surface(self.target_size)
        checker_size = 20  # Size of each checker square
        
        for i in range(0, self.target_size[0], checker_size):
            for j in range(0, self.target_size[1], checker_size):
                if (i // checker_size + j // checker_size) % 2 == 0:
                    color = (255, 255, 255)
                else:
                    color = (0, 0, 0)
                pygame.draw.rect(surface, color, (i, j, checker_size, checker_size))
        
        # Add command text
        if target_idx < len(self.commands):
            text = self.commands[target_idx]
            text_surface = self.font.render(text, True, (128, 128, 128))
            text_rect = text_surface.get_rect(center=(self.target_size[0]//2, 
                                                     self.target_size[1]//2))
            surface.blit(text_surface, text_rect)
        
        return surface
    
    def _create_square_surface(self, target_idx: int) -> pygame.Surface:
        """Create square pattern for flickering"""
        surface = pygame.Surface(self.target_size)
        surface.fill((255, 255, 255))
        
        # Add command text in contrasting color
        if target_idx < len(self.commands):
            text = self.commands[target_idx]
            text_surface = self.font.render(text, True, (0, 0, 0))
            text_rect = text_surface.get_rect(center=(self.target_size[0]//2, 
                                                     self.target_size[1]//2))
            surface.blit(text_surface, text_rect)
        
        return surface
    
    def _create_sinusoidal_surfaces(self, target_idx: int) -> List[pygame.Surface]:
        """Create multiple surfaces for sinusoidal intensity modulation"""
        surfaces = []
        n_levels = 16  # Number of intensity levels
        
        for level in range(n_levels):
            intensity = int(255 * (0.5 + 0.5 * np.sin(2 * np.pi * level / n_levels)))
            surface = pygame.Surface(self.target_size)
            surface.fill((intensity, intensity, intensity))
            
            # Add command text
            if target_idx < len(self.commands):
                text = self.commands[target_idx]
                # Choose text color based on background intensity
                text_color = (0, 0, 0) if intensity > 128 else (255, 255, 255)
                text_surface = self.font.render(text, True, text_color)
                text_rect = text_surface.get_rect(center=(self.target_size[0]//2, 
                                                         self.target_size[1]//2))
                surface.blit(text_surface, text_rect)
            
            surfaces.append(surface)
        
        return surfaces
    
    def _generate_marker_codes(self) -> Dict:
        """Generate unique marker codes for SSVEP stimuli"""
        codes = {}
        
        # Frequency-specific codes
        for idx, freq in enumerate(self.frequencies):
            codes[f'freq_{freq}'] = 100 + idx
            codes[f'freq_{freq}_on'] = 200 + idx
            codes[f'freq_{freq}_off'] = 300 + idx
        
        # Command codes
        for idx, command in enumerate(self.commands):
            codes[command] = 400 + idx
        
        # Special codes
        codes['trial_start'] = 10
        codes['trial_end'] = 11
        codes['rest_start'] = 20
        codes['rest_end'] = 21
        codes['calibration_start'] = 30
        codes['calibration_end'] = 31
        
        return codes
    
    def draw_interface(self):
        """Draw the main interface"""
        # Clear screen
        self.screen.fill(self.bg_color)
        
        # Draw all targets
        for idx in range(min(self.n_targets, len(self.frequencies))):
            self._draw_target(idx)
        
        # Draw spectrum display if enabled
        if self.show_spectrum:
            self._draw_spectrum()
        
        # Draw performance metrics
        self._draw_performance_metrics()
    
    def _draw_target(self, target_idx: int):
        """Draw a single target with appropriate flickering"""
        rect = self.target_rects[target_idx]
        
        if self.stimulating and (self.current_target is None or self.current_target == target_idx):
            # Calculate current phase for this frequency
            frequency = self.frequencies[target_idx]
            current_time = time.time()
            phase = self.phases[frequency]
            
            # Determine visibility based on stimulus type
            if self.stimulus_type == 'sinusoidal':
                # Sinusoidal modulation
                intensity = 0.5 + 0.5 * np.sin(2 * np.pi * phase) * self.contrast
                if isinstance(self.flickering_surfaces[target_idx], list):
                    # Use pre-rendered surfaces
                    surface_idx = int(phase * len(self.flickering_surfaces[target_idx])) % len(self.flickering_surfaces[target_idx])
                    surface = self.flickering_surfaces[target_idx][surface_idx]
                else:
                    surface = self.flickering_surfaces[target_idx]
                    surface.set_alpha(int(255 * intensity))
            else:
                # Square wave modulation
                visible = (phase % 1.0) < 0.5
                
                if visible:
                    surface = self.flickering_surfaces[target_idx]
                else:
                    surface = self.target_surfaces[target_idx]
        else:
            # Not stimulating or not current target
            surface = self.target_surfaces[target_idx]
        
        # Blit surface to screen
        self.screen.blit(surface, rect)
        
        # Highlight current target during calibration
        if self.current_target == target_idx:
            pygame.draw.rect(self.screen, (0, 255, 0), rect, 3)
    
    def _draw_spectrum(self):
        """Draw real-time frequency spectrum (placeholder)"""
        # This would show real-time FFT of EEG data
        spectrum_rect = pygame.Rect(10, self.window_size[1] - 110, 300, 100)
        pygame.draw.rect(self.screen, (30, 30, 30), spectrum_rect)
        pygame.draw.rect(self.screen, (100, 100, 100), spectrum_rect, 1)
        
        # Draw frequency markers
        for freq in self.frequencies:
            x = 10 + int((freq / 30.0) * 300)  # Scale to 0-30 Hz range
            pygame.draw.line(self.screen, (0, 255, 0), 
                           (x, spectrum_rect.bottom - 20),
                           (x, spectrum_rect.bottom), 2)
    
    def _draw_performance_metrics(self):
        """Draw performance metrics"""
        # Calculate actual frame rate
        if len(self.frame_times) > 1:
            avg_frame_time = np.mean(np.diff(list(self.frame_times)))
            actual_fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
        else:
            actual_fps = 0
        
        # Display FPS
        fps_text = f"FPS: {actual_fps:.1f} / {self.refresh_rate}"
        fps_surface = self.small_font.render(fps_text, True, (150, 150, 150))
        self.screen.blit(fps_surface, (10, 10))
        
        # Display frequency accuracy
        y_offset = 35
        for idx, freq in enumerate(self.frequencies[:self.n_targets]):
            actual_freq = self.actual_frequencies.get(freq, freq)
            accuracy = (1 - abs(actual_freq - freq) / freq) * 100
            
            freq_text = f"F{idx+1}: {actual_freq:.2f}Hz ({accuracy:.1f}%)"
            color = (0, 255, 0) if accuracy > 95 else (255, 255, 0) if accuracy > 90 else (255, 0, 0)
            freq_surface = self.small_font.render(freq_text, True, color)
            self.screen.blit(freq_surface, (10, y_offset))
            y_offset += 25
    
    def update_phases(self):
        """Update phase values for each frequency"""
        current_time = time.time()
        dt = current_time - self.last_update_time
        
        for freq in self.frequencies:
            # Update phase based on elapsed time
            self.phases[freq] += freq * dt
            # Keep phase in [0, 1] range
            self.phases[freq] = self.phases[freq] % 1.0
        
        self.last_update_time = current_time
        self.frame_times.append(current_time)
    
    def start_stimulation(self, target_idx: Optional[int] = None):
        """
        Start SSVEP stimulation
        
        Args:
            target_idx: Specific target to stimulate (None for all)
        """
        self.stimulating = True
        self.current_target = target_idx
        self.last_update_time = time.time()
        
        # Reset phases
        for freq in self.frequencies:
            self.phases[freq] = 0.0
        
        # Send marker
        if self.marker_callback:
            if target_idx is not None:
                self.marker_callback(self.marker_codes[f'freq_{self.frequencies[target_idx]}_on'])
            else:
                self.marker_callback(self.marker_codes['trial_start'])
    
    def stop_stimulation(self):
        """Stop SSVEP stimulation"""
        if self.stimulating:
            self.stimulating = False
            
            # Send marker
            if self.marker_callback:
                if self.current_target is not None:
                    freq = self.frequencies[self.current_target]
                    self.marker_callback(self.marker_codes[f'freq_{freq}_off'])
                else:
                    self.marker_callback(self.marker_codes['trial_end'])
            
            self.current_target = None
    
    def run_calibration(self, n_trials_per_target: Optional[int] = None):
        """
        Run SSVEP calibration sequence
        
        Args:
            n_trials_per_target: Number of trials per frequency
        """
        if n_trials_per_target is None:
            n_trials_per_target = self.config['CALIBRATION']['n_trials_per_target']
        
        trial_duration = self.config['CALIBRATION']['trial_duration'] / 1000.0
        break_duration = self.config['CALIBRATION']['break_duration'] / 1000.0
        
        # Send calibration start marker
        if self.marker_callback:
            self.marker_callback(self.marker_codes['calibration_start'])
        
        # Create trial order
        trial_order = []
        for target_idx in range(min(self.n_targets, len(self.frequencies))):
            trial_order.extend([target_idx] * n_trials_per_target)
        
        # Randomize if configured
        if self.config['CALIBRATION']['randomize_order']:
            np.random.shuffle(trial_order)
        
        # Run trials
        for trial_num, target_idx in enumerate(trial_order):
            if not self.running:
                break
            
            print(f"Trial {trial_num + 1}/{len(trial_order)}: "
                  f"Focus on {self.commands[target_idx]} ({self.frequencies[target_idx]} Hz)")
            
            # Rest period
            if self.marker_callback:
                self.marker_callback(self.marker_codes['rest_start'])
            
            start_time = time.time()
            while time.time() - start_time < break_duration and self.running:
                self.update_phases()
                self.draw_interface()
                pygame.display.flip()
                self.handle_events()
                self.clock.tick(self.refresh_rate)
            
            if self.marker_callback:
                self.marker_callback(self.marker_codes['rest_end'])
            
            # Stimulation period
            self.start_stimulation(target_idx)
            
            start_time = time.time()
            while time.time() - start_time < trial_duration and self.running:
                self.update_phases()
                self.draw_interface()
                pygame.display.flip()
                self.handle_events()
                self.clock.tick(self.refresh_rate)
            
            self.stop_stimulation()
        
        # Send calibration end marker
        if self.marker_callback:
            self.marker_callback(self.marker_codes['calibration_end'])
        
        print("Calibration completed")
    
    def run_online(self, classifier_callback: Optional[Callable] = None):
        """
        Run online SSVEP BCI
        
        Args:
            classifier_callback: Function to call for classification
        """
        self.running = True
        self.start_stimulation()  # Start all frequencies
        
        classification_interval = self.config['REALTIME']['decision_interval'] / 1000.0
        last_classification = time.time()
        
        while self.running:
            current_time = time.time()
            
            # Update phases
            self.update_phases()
            
            # Draw interface
            self.draw_interface()
            pygame.display.flip()
            
            # Check for classification
            if current_time - last_classification >= classification_interval:
                if classifier_callback:
                    result = classifier_callback()
                    if result is not None:
                        target_idx, confidence = result
                        if confidence > self.config['REALTIME']['min_confidence']:
                            command = self.commands[target_idx]
                            print(f"Detected: {command} (Freq: {self.frequencies[target_idx]} Hz, "
                                  f"Confidence: {confidence:.2f})")
                            
                            # Visual feedback
                            self.current_target = target_idx
                            self.draw_interface()
                            pygame.display.flip()
                            time.sleep(0.5)
                            self.current_target = None
                
                last_classification = current_time
            
            # Handle events
            self.handle_events()
            
            # Control frame rate
            self.clock.tick(self.refresh_rate)
        
        self.stop_stimulation()
    
    def handle_events(self):
        """Handle pygame events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_SPACE:
                    if self.stimulating:
                        self.stop_stimulation()
                    else:
                        self.start_stimulation()
                elif event.key >= pygame.K_1 and event.key <= pygame.K_9:
                    # Number keys to select specific target
                    target_idx = event.key - pygame.K_1
                    if target_idx < self.n_targets:
                        if self.stimulating:
                            self.stop_stimulation()
                        self.start_stimulation(target_idx)
    
    def cleanup(self):
        """Clean up pygame resources"""
        self.running = False
        self.stop_stimulation()
        if self.stimulus_thread:
            self.stop_event.set()
            self.stimulus_thread.join(timeout=1.0)
        pygame.quit()
        print("SSVEP stimulus system cleaned up")
    
    def __del__(self):
        """Destructor"""
        self.cleanup()