"""Binary choice visual stimulus for SSVEP BCI - Optimized for 2 options"""

import numpy as np
import time
from psychopy import visual, core, event
import sys
import os
import logging

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class BinaryChoiceStimulus:
    """Visual stimulus for 2-choice SSVEP BCI"""
    
    def __init__(self, freq_left: float = 10.0, freq_right: float = 15.0,
                 labels: tuple = ("Option A", "Option B"),
                 window_size: tuple = (1024, 600),
                 fullscreen: bool = False):
        """
        Initialize binary choice stimulus
        
        Args:
            freq_left: Frequency for left option (Hz)
            freq_right: Frequency for right option (Hz)
            labels: Text labels for the two options
            window_size: Window dimensions (width, height)
            fullscreen: Use fullscreen mode
        """
        self.freq_left = freq_left
        self.freq_right = freq_right
        self.frequencies = [freq_left, freq_right]
        self.labels = labels
        self.window_size = window_size
        self.fullscreen = fullscreen
        
        # Visual parameters
        self.box_size = 250  # Larger boxes for easier focusing
        self.separation = 400  # Distance between boxes
        
        # Window and stimuli
        self.win = None
        self.left_box = None
        self.right_box = None
        self.left_label = None
        self.right_label = None
        self.instruction_text = None
        self.feedback_text = None
        self.selection_indicator = None
        
        # Animation state
        self.frame_rate = 60.0
        self.frame_counters = {freq: 0.0 for freq in self.frequencies}
        self.frames_per_cycle = {freq: self.frame_rate / freq for freq in self.frequencies}
        
        # State
        self.is_running = False
        self.selected = None
        self.show_feedback = False
        
    def setup(self) -> bool:
        """Setup PsychoPy window and visual elements"""
        try:
            # Create window
            self.win = visual.Window(
                size=self.window_size,
                fullscr=self.fullscreen,
                monitor='testMonitor',
                units='pix',
                color=[-0.8, -0.8, -0.8],  # Dark gray background
                allowGUI=True
            )
            
            # Get actual refresh rate
            actual_rate = self.win.getActualFrameRate()
            if actual_rate:
                self.frame_rate = actual_rate
                logger.info(f"Monitor refresh rate: {self.frame_rate:.1f} Hz")
                # Recalculate frames per cycle
                for freq in self.frequencies:
                    self.frames_per_cycle[freq] = self.frame_rate / freq
            
            # Create left option box
            self.left_box = visual.Rect(
                win=self.win,
                width=self.box_size,
                height=self.box_size,
                pos=(-self.separation/2, 0),
                fillColor=[1, 1, 1],
                lineColor=[-1, -1, -1],
                lineWidth=3
            )
            
            # Create right option box
            self.right_box = visual.Rect(
                win=self.win,
                width=self.box_size,
                height=self.box_size,
                pos=(self.separation/2, 0),
                fillColor=[1, 1, 1],
                lineColor=[-1, -1, -1],
                lineWidth=3
            )
            
            # Create labels
            self.left_label = visual.TextStim(
                win=self.win,
                text=self.labels[0],
                pos=(-self.separation/2, -self.box_size/2 - 40),
                color=[1, 1, 1],
                height=24,
                font='Arial',
                bold=True
            )
            
            self.right_label = visual.TextStim(
                win=self.win,
                text=self.labels[1],
                pos=(self.separation/2, -self.box_size/2 - 40),
                color=[1, 1, 1],
                height=24,
                font='Arial',
                bold=True
            )
            
            # Create instruction text
            self.instruction_text = visual.TextStim(
                win=self.win,
                text='Look at the box to make your choice',
                pos=(0, self.window_size[1]/2 - 50),
                color=[1, 1, 1],
                height=20,
                font='Arial'
            )
            
            # Create feedback text
            self.feedback_text = visual.TextStim(
                win=self.win,
                text='',
                pos=(0, -self.window_size[1]/2 + 50),
                color=[0, 1, 0],
                height=28,
                font='Arial',
                bold=True
            )
            
            # Create selection indicator (green border)
            self.selection_indicator = visual.Rect(
                win=self.win,
                width=self.box_size + 20,
                height=self.box_size + 20,
                pos=(0, 0),
                fillColor=None,
                lineColor=[0, 1, 0],
                lineWidth=5
            )
            
            # Add frequency indicators
            self.left_freq_text = visual.TextStim(
                win=self.win,
                text=f'{self.freq_left} Hz',
                pos=(-self.separation/2, self.box_size/2 + 30),
                color=[0.7, 0.7, 0.7],
                height=16,
                font='Arial'
            )
            
            self.right_freq_text = visual.TextStim(
                win=self.win,
                text=f'{self.freq_right} Hz',
                pos=(self.separation/2, self.box_size/2 + 30),
                color=[0.7, 0.7, 0.7],
                height=16,
                font='Arial'
            )
            
            logger.info("Visual stimulus setup complete")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup window: {e}")
            return False
    
    def update_flicker(self):
        """Update flicker state for both boxes"""
        # Update frame counters
        for freq in self.frequencies:
            self.frame_counters[freq] += 1.0
            if self.frame_counters[freq] >= self.frames_per_cycle[freq]:
                self.frame_counters[freq] = 0.0
        
        # Calculate opacities
        left_phase = 2 * np.pi * self.frame_counters[self.freq_left] / self.frames_per_cycle[self.freq_left]
        right_phase = 2 * np.pi * self.frame_counters[self.freq_right] / self.frames_per_cycle[self.freq_right]
        
        left_opacity = (np.sin(left_phase) + 1) / 2
        right_opacity = (np.sin(right_phase) + 1) / 2
        
        # Apply opacities
        self.left_box.opacity = left_opacity
        self.right_box.opacity = right_opacity
    
    def draw_frame(self):
        """Draw a single frame"""
        # Update flicker
        self.update_flicker()
        
        # Draw boxes
        self.left_box.draw()
        self.right_box.draw()
        
        # Draw labels
        self.left_label.draw()
        self.right_label.draw()
        
        # Draw frequency indicators
        self.left_freq_text.draw()
        self.right_freq_text.draw()
        
        # Draw instruction
        self.instruction_text.draw()
        
        # Draw selection indicator if something is selected
        if self.selected:
            if self.selected == 'left':
                self.selection_indicator.pos = (-self.separation/2, 0)
            else:
                self.selection_indicator.pos = (self.separation/2, 0)
            self.selection_indicator.draw()
        
        # Draw feedback
        if self.feedback_text.text:
            self.feedback_text.draw()
        
        # Flip buffer
        self.win.flip()
    
    def set_selection(self, choice: str):
        """Set the selected option"""
        if choice in ['left', 'right']:
            self.selected = choice
            if choice == 'left':
                self.feedback_text.text = f'Selected: {self.labels[0]}'
            else:
                self.feedback_text.text = f'Selected: {self.labels[1]}'
            logger.info(f"Selection: {choice}")
    
    def clear_selection(self):
        """Clear the selection"""
        self.selected = None
        self.feedback_text.text = ''
    
    def run(self):
        """Run the stimulus presentation"""
        if not self.setup():
            return False
        
        self.is_running = True
        
        # Show initial instructions
        instructions = visual.TextStim(
            win=self.win,
            text='Binary Choice SSVEP Interface\n\n'
                 'Look at one of the flickering boxes to make your choice.\n'
                 'The boxes flicker at different frequencies.\n\n'
                 f'Left: {self.labels[0]} ({self.freq_left} Hz)\n'
                 f'Right: {self.labels[1]} ({self.freq_right} Hz)\n\n'
                 'Press SPACE to start, ESC to quit',
            pos=(0, 0),
            color=[1, 1, 1],
            height=24,
            font='Arial',
            wrapWidth=800
        )
        
        instructions.draw()
        self.win.flip()
        
        # Wait for space or escape
        keys = event.waitKeys(keyList=['space', 'escape'])
        if 'escape' in keys:
            self.cleanup()
            return False
        
        # Main loop
        try:
            clock = core.Clock()
            demo_timer = 0
            demo_state = 0
            
            while self.is_running:
                # Check for quit
                keys = event.getKeys()
                if 'escape' in keys:
                    break
                
                # Demo mode - simulate selections
                if 'space' in keys:
                    # Toggle between selections for testing
                    if self.selected == 'left':
                        self.set_selection('right')
                    elif self.selected == 'right':
                        self.clear_selection()
                    else:
                        self.set_selection('left')
                
                # Draw frame
                self.draw_frame()
                
                # Control frame rate
                core.wait(0.001)
                
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        
        finally:
            self.cleanup()
        
        return True
    
    def cleanup(self):
        """Clean up resources"""
        self.is_running = False
        if self.win:
            self.win.close()
        logger.info("Stimulus cleaned up")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Binary Choice SSVEP Stimulus')
    parser.add_argument('--left-freq', type=float, default=10.0,
                       help='Left option frequency (Hz)')
    parser.add_argument('--right-freq', type=float, default=15.0,
                       help='Right option frequency (Hz)')
    parser.add_argument('--left-label', default='Option A',
                       help='Label for left option')
    parser.add_argument('--right-label', default='Option B',
                       help='Label for right option')
    parser.add_argument('--fullscreen', action='store_true',
                       help='Run in fullscreen mode')
    
    args = parser.parse_args()
    
    # Create and run stimulus
    stimulus = BinaryChoiceStimulus(
        freq_left=args.left_freq,
        freq_right=args.right_freq,
        labels=(args.left_label, args.right_label),
        fullscreen=args.fullscreen
    )
    
    stimulus.run()


if __name__ == "__main__":
    main()