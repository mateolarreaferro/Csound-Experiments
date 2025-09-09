"""Visual stimulus presentation for SSVEP BCI system"""

import numpy as np
import time
from psychopy import visual, core, event, monitors
import threading
import logging
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
import config

# Configure logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL), 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SSVEPStimulus:
    """SSVEP visual stimulus presentation system"""
    
    def __init__(self, target_freqs=None, window_size=None, fullscreen=None):
        """
        Initialize SSVEP stimulus
        
        Args:
            target_freqs: List of target frequencies (default from config)
            window_size: Tuple of (width, height) or None for config default
            fullscreen: Bool for fullscreen mode or None for config default
        """
        # Use config defaults if not specified
        self.target_freqs = target_freqs or config.FREQS
        self.fullscreen = fullscreen if fullscreen is not None else config.FULLSCREEN
        
        if window_size is None:
            self.window_size = (config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        else:
            self.window_size = window_size
        
        # Visual parameters
        self.stim_size = config.STIM_SIZE
        self.stim_spacing = config.STIM_SPACING
        
        # Initialize window and stimuli
        self.win = None
        self.stimuli = []
        self.text_labels = []
        self.feedback_text = None
        
        # Animation parameters
        self.frame_rate = 60.0  # Assume 60 Hz monitor
        self.frames_per_cycle = {}
        self.frame_counters = {}
        
        # Calculate frames per cycle for each frequency
        for freq in self.target_freqs:
            self.frames_per_cycle[freq] = self.frame_rate / freq
            self.frame_counters[freq] = 0.0
        
        # State
        self.is_running = False
        self.selected_frequency = None
        
        logger.info(f"Stimulus initialized: freqs={self.target_freqs}Hz, "
                   f"size={self.window_size}, fullscreen={self.fullscreen}")
    
    def setup_window(self):
        """Setup PsychoPy window and visual elements"""
        try:
            # Create window
            self.win = visual.Window(
                size=self.window_size,
                fullscr=self.fullscreen,
                monitor='testMonitor',
                units='pix',
                color=[-0.5, -0.5, -0.5]  # Gray background
            )
            
            # Get actual refresh rate
            actual_rate = self.win.getActualFrameRate()
            if actual_rate is not None:
                self.frame_rate = actual_rate
                logger.info(f"Detected monitor refresh rate: {self.frame_rate:.1f} Hz")
                
                # Recalculate frames per cycle with actual rate
                for freq in self.target_freqs:
                    self.frames_per_cycle[freq] = self.frame_rate / freq
            
            # Calculate positions for stimuli (arranged in a grid)
            positions = self._calculate_positions()
            
            # Create stimuli
            self.stimuli = []
            self.text_labels = []
            
            for i, (freq, pos) in enumerate(zip(self.target_freqs, positions)):
                # Create flickering rectangle
                stim = visual.Rect(
                    win=self.win,
                    width=self.stim_size,
                    height=self.stim_size,
                    pos=pos,
                    fillColor=[1, 1, 1],  # White
                    lineColor=[0, 0, 0]   # Black border
                )
                self.stimuli.append(stim)
                
                # Create frequency label
                label = visual.TextStim(
                    win=self.win,
                    text=f'{freq}Hz',
                    pos=(pos[0], pos[1] - self.stim_size/2 - 30),
                    color=[1, 1, 1],
                    height=20
                )
                self.text_labels.append(label)
            
            # Create feedback text
            self.feedback_text = visual.TextStim(
                win=self.win,
                text='',
                pos=(0, -self.window_size[1]//2 + 50),
                color=[0, 1, 0],  # Green
                height=24
            )
            
            logger.info(f"Window setup complete: {len(self.stimuli)} stimuli created")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup window: {e}")
            return False
    
    def _calculate_positions(self):
        """Calculate positions for stimuli in a grid layout"""
        n_stimuli = len(self.target_freqs)
        
        if n_stimuli <= 2:
            # Horizontal arrangement
            positions = []
            start_x = -(n_stimuli - 1) * self.stim_spacing / 2
            for i in range(n_stimuli):
                x = start_x + i * self.stim_spacing
                positions.append((x, 0))
        
        elif n_stimuli <= 4:
            # 2x2 grid
            positions = [
                (-self.stim_spacing//2, self.stim_spacing//2),   # Top-left
                (self.stim_spacing//2, self.stim_spacing//2),    # Top-right
                (-self.stim_spacing//2, -self.stim_spacing//2),  # Bottom-left
                (self.stim_spacing//2, -self.stim_spacing//2)    # Bottom-right
            ]
        
        else:
            # Circular arrangement for more stimuli
            positions = []
            radius = self.stim_spacing
            for i in range(n_stimuli):
                angle = 2 * np.pi * i / n_stimuli
                x = radius * np.cos(angle)
                y = radius * np.sin(angle)
                positions.append((x, y))
        
        return positions[:n_stimuli]
    
    def update_stimulus_opacity(self, freq, frame_count):
        """
        Update stimulus opacity based on frame count and frequency
        
        Args:
            freq: Target frequency
            frame_count: Current frame counter for this frequency
        
        Returns:
            Opacity value (0-1)
        """
        # Calculate phase based on frame count
        phase = 2 * np.pi * frame_count / self.frames_per_cycle[freq]
        
        # Convert sine wave to opacity (0-1 range)
        opacity = (np.sin(phase) + 1) / 2
        
        return opacity
    
    def draw_frame(self):
        """Draw a single frame with updated stimuli"""
        # Update frame counters
        for freq in self.target_freqs:
            self.frame_counters[freq] += 1.0
            if self.frame_counters[freq] >= self.frames_per_cycle[freq]:
                self.frame_counters[freq] = 0.0
        
        # Update and draw stimuli
        for i, freq in enumerate(self.target_freqs):
            opacity = self.update_stimulus_opacity(freq, self.frame_counters[freq])
            
            # Set opacity
            self.stimuli[i].opacity = opacity
            
            # Highlight selected frequency
            if self.selected_frequency == freq:
                self.stimuli[i].lineColor = [0, 1, 0]  # Green border
                self.stimuli[i].lineWidth = 5
            else:
                self.stimuli[i].lineColor = [0, 0, 0]  # Black border
                self.stimuli[i].lineWidth = 1
            
            # Draw
            self.stimuli[i].draw()
            self.text_labels[i].draw()
        
        # Draw feedback
        if self.feedback_text.text:
            self.feedback_text.draw()
        
        # Flip buffer
        self.win.flip()
    
    def set_feedback(self, text, color=None):
        """
        Set feedback text
        
        Args:
            text: Text to display
            color: Text color as [r, g, b] list
        """
        self.feedback_text.text = text
        if color is not None:
            self.feedback_text.color = color
    
    def set_selection(self, frequency):
        """
        Highlight a selected frequency
        
        Args:
            frequency: Frequency to highlight (Hz)
        """
        if frequency in self.target_freqs:
            self.selected_frequency = frequency
            logger.info(f"Selected frequency: {frequency} Hz")
        else:
            self.selected_frequency = None
    
    def start_presentation(self):
        """Start stimulus presentation loop"""
        if not self.setup_window():
            return False
        
        self.is_running = True
        
        # Instructions
        instruction_text = visual.TextStim(
            win=self.win,
            text='SSVEP Visual Stimulus\n\nGaze at one of the flickering boxes\nPress ESC to quit',
            pos=(0, 0),
            color=[1, 1, 1],
            height=30
        )
        
        # Show instructions for 3 seconds
        instruction_text.draw()
        self.win.flip()
        core.wait(3.0)
        
        logger.info("Started stimulus presentation")
        
        # Main presentation loop
        try:
            while self.is_running:
                # Check for quit
                keys = event.getKeys()
                if 'escape' in keys:
                    break
                
                # Draw frame
                self.draw_frame()
                
                # Small delay to prevent excessive CPU usage
                core.wait(0.001)
        
        except KeyboardInterrupt:
            logger.info("Presentation interrupted by user")
        
        finally:
            self.cleanup()
        
        return True
    
    def stop_presentation(self):
        """Stop stimulus presentation"""
        self.is_running = False
    
    def cleanup(self):
        """Clean up resources"""
        if self.win:
            self.win.close()
        logger.info("Stimulus presentation stopped")


def test_stimulus():
    """Test the stimulus presentation"""
    # Test with default config
    stimulus = SSVEPStimulus()
    
    print("Starting SSVEP stimulus test...")
    print("Instructions:")
    print("- Look at one of the flickering boxes")
    print("- Press ESC to quit")
    print("\nStarting in 2 seconds...")
    
    time.sleep(2)
    stimulus.start_presentation()


def main():
    """Main function for stimulus presentation"""
    import argparse
    
    parser = argparse.ArgumentParser(description='SSVEP Visual Stimulus Presentation')
    parser.add_argument('--freqs', nargs='+', type=float, default=config.FREQS,
                       help='Target frequencies (Hz)')
    parser.add_argument('--fullscreen', action='store_true', default=config.FULLSCREEN,
                       help='Run in fullscreen mode')
    parser.add_argument('--window-size', nargs=2, type=int, 
                       default=[config.WINDOW_WIDTH, config.WINDOW_HEIGHT],
                       help='Window size (width height)')
    parser.add_argument('--test', action='store_true',
                       help='Run in test mode with simulated feedback')
    
    args = parser.parse_args()
    
    # Create stimulus
    stimulus = SSVEPStimulus(
        target_freqs=args.freqs,
        window_size=tuple(args.window_size),
        fullscreen=args.fullscreen
    )
    
    if args.test:
        # Test mode - simulate some selections
        def test_feedback():
            time.sleep(5)
            for freq in args.freqs:
                stimulus.set_selection(freq)
                stimulus.set_feedback(f"Detected: {freq} Hz", [0, 1, 0])
                time.sleep(3)
            
            stimulus.set_selection(None)
            stimulus.set_feedback("Test completed", [1, 1, 0])
        
        # Start feedback thread
        feedback_thread = threading.Thread(target=test_feedback)
        feedback_thread.daemon = True
        feedback_thread.start()
    
    # Start presentation
    stimulus.start_presentation()


if __name__ == "__main__":
    main()