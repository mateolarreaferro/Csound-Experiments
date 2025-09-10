"""Binary choice visual stimulus for SSVEP BCI using Pygame"""

import pygame
import numpy as np
import time
import sys
import os
import logging

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class BinaryChoiceStimulusPygame:
    """Visual stimulus for 2-choice SSVEP BCI using Pygame"""
    
    def __init__(self, freq_left: float = 10.0, freq_right: float = 15.0,
                 labels: tuple = ("LEFT", "RIGHT"),
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
        
        # Colors
        self.bg_color = (128, 128, 128)  # Gray background
        self.white = (255, 255, 255)
        self.black = (0, 0, 0)
        self.red = (255, 0, 0)
        
        # Initialize Pygame
        pygame.init()
        
        # Set up display
        if fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            self.window_size = self.screen.get_size()
        else:
            self.screen = pygame.display.set_mode(window_size)
        
        pygame.display.set_caption("SSVEP Binary Choice")
        
        # Font for labels
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        
        # Clock for timing
        self.clock = pygame.time.Clock()
        
        # Calculate positions
        center_x = self.window_size[0] // 2
        center_y = self.window_size[1] // 2
        
        self.left_pos = (center_x - self.separation // 2 - self.box_size // 2,
                        center_y - self.box_size // 2)
        self.right_pos = (center_x + self.separation // 2 - self.box_size // 2,
                         center_y - self.box_size // 2)
        
        # Timing variables
        self.start_time = None
        self.left_phase = 0
        self.right_phase = 0
        
        # Control flags
        self.running = False
        self.test_mode = False
        self.current_selection = None
        
        logger.info(f"Initialized binary stimulus - Left: {freq_left}Hz, Right: {freq_right}Hz")
    
    def draw_box(self, position, color, label):
        """Draw a flickering box with label"""
        # Draw box
        pygame.draw.rect(self.screen, color, 
                        (position[0], position[1], self.box_size, self.box_size))
        pygame.draw.rect(self.screen, self.black, 
                        (position[0], position[1], self.box_size, self.box_size), 3)
        
        # Draw label above box
        text = self.font.render(label, True, self.white)
        text_rect = text.get_rect()
        text_rect.centerx = position[0] + self.box_size // 2
        text_rect.bottom = position[1] - 20
        self.screen.blit(text, text_rect)
    
    def draw_instructions(self):
        """Draw instruction text"""
        instructions = [
            "SSVEP Binary Choice",
            f"Left: {self.freq_left} Hz | Right: {self.freq_right} Hz",
            "",
            "Look at one box to make a selection",
            "Press SPACE to start/stop",
            "Press ESC to exit"
        ]
        
        y_offset = 20
        for line in instructions:
            text = self.small_font.render(line, True, self.white)
            text_rect = text.get_rect()
            text_rect.centerx = self.window_size[0] // 2
            text_rect.top = y_offset
            self.screen.blit(text, text_rect)
            y_offset += 30
    
    def draw_feedback(self):
        """Draw feedback for current selection"""
        if self.current_selection is not None:
            if self.current_selection == 0:
                text = f"Selection: {self.labels[0]} ({self.freq_left} Hz)"
                color = self.red
            else:
                text = f"Selection: {self.labels[1]} ({self.freq_right} Hz)"
                color = self.red
            
            feedback = self.font.render(text, True, color)
            feedback_rect = feedback.get_rect()
            feedback_rect.centerx = self.window_size[0] // 2
            feedback_rect.bottom = self.window_size[1] - 50
            self.screen.blit(feedback, feedback_rect)
    
    def update_flicker(self):
        """Update flicker states based on frequencies"""
        if self.start_time is None:
            self.start_time = time.time()
        
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        # Calculate phases
        self.left_phase = np.sin(2 * np.pi * self.freq_left * elapsed)
        self.right_phase = np.sin(2 * np.pi * self.freq_right * elapsed)
        
        # Convert to colors (sine wave to grayscale)
        left_intensity = int((self.left_phase + 1) * 127.5)
        right_intensity = int((self.right_phase + 1) * 127.5)
        
        left_color = (left_intensity, left_intensity, left_intensity)
        right_color = (right_intensity, right_intensity, right_intensity)
        
        return left_color, right_color
    
    def run(self):
        """Main stimulus loop"""
        self.running = True
        stimulating = False
        
        logger.info("Starting stimulus presentation")
        logger.info("Press SPACE to start/stop, ESC to exit")
        
        while self.running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_SPACE:
                        stimulating = not stimulating
                        if stimulating:
                            logger.info("Stimulation started")
                            self.start_time = time.time()
                        else:
                            logger.info("Stimulation stopped")
                    elif event.key == pygame.K_t:
                        self.test_mode = not self.test_mode
                        logger.info(f"Test mode: {self.test_mode}")
                    elif event.key == pygame.K_1:
                        self.current_selection = 0
                        logger.info(f"Manual selection: {self.labels[0]}")
                    elif event.key == pygame.K_2:
                        self.current_selection = 1
                        logger.info(f"Manual selection: {self.labels[1]}")
            
            # Clear screen
            self.screen.fill(self.bg_color)
            
            # Draw instructions
            self.draw_instructions()
            
            if stimulating:
                # Update flicker
                left_color, right_color = self.update_flicker()
                
                # Draw boxes
                self.draw_box(self.left_pos, left_color, self.labels[0])
                self.draw_box(self.right_pos, right_color, self.labels[1])
            else:
                # Draw static boxes
                self.draw_box(self.left_pos, self.white, self.labels[0])
                self.draw_box(self.right_pos, self.white, self.labels[1])
            
            # Draw feedback if in test mode
            if self.test_mode:
                self.draw_feedback()
            
            # Update display
            pygame.display.flip()
            
            # Control frame rate (60 FPS)
            self.clock.tick(60)
        
        # Cleanup
        pygame.quit()
        logger.info("Stimulus presentation ended")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Binary SSVEP Stimulus using Pygame')
    parser.add_argument('--freq-left', type=float, default=10.0,
                       help='Left box frequency (Hz)')
    parser.add_argument('--freq-right', type=float, default=15.0,
                       help='Right box frequency (Hz)')
    parser.add_argument('--fullscreen', action='store_true',
                       help='Run in fullscreen mode')
    parser.add_argument('--test', action='store_true',
                       help='Enable test mode with manual selection')
    
    args = parser.parse_args()
    
    # Create and run stimulus
    stimulus = BinaryChoiceStimulusPygame(
        freq_left=args.freq_left,
        freq_right=args.freq_right,
        fullscreen=args.fullscreen
    )
    
    if args.test:
        stimulus.test_mode = True
        logger.info("Test mode enabled - Press 1 or 2 to simulate selection")
    
    try:
        stimulus.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()