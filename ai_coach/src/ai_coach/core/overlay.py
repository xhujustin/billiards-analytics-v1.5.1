"""
Overlay module for AI Coach system.

Provides visualization and text overlay functionality for billiards analytics.
"""

from collections import deque
import numpy as np
from typing import List, Tuple, Optional


class StabilityDetector:
    """
    Detects when all balls on the table have come to a stable rest position.
    
    Monitors ball center coordinates over a rolling window (60 frames ≈ 1 second)
    and uses maximum displacement to determine stability.
    """
    
    # Configuration parameters
    BUFFER_SIZE = 60  # Frames to store (~1 second at 60 FPS)
    DISPLACEMENT_THRESHOLD = 2.0  # pixels - stability threshold
    STABILITY_DURATION = 60  # frames that must be stable to trigger True
    MOVEMENT_THRESHOLD = 5.0  # pixels - threshold to exit cooldown state
    
    def __init__(
        self,
        frame_buffer_size: int = BUFFER_SIZE,
        displacement_threshold: float = DISPLACEMENT_THRESHOLD,
        stable_threshold: int = STABILITY_DURATION,
        cooldown_frames: int = STABILITY_DURATION,
        movement_threshold: float = MOVEMENT_THRESHOLD,
    ):
        """Initialize the StabilityDetector."""
        self.frame_buffer_size = frame_buffer_size
        self.displacement_threshold = displacement_threshold
        self.stable_threshold = stable_threshold
        self.cooldown_frames = cooldown_frames
        self.movement_threshold = movement_threshold

        # Rolling buffer storing ball centers for each frame
        # Format: list of dicts {ball_id: (x, y), ...}
        self.frame_buffer: deque = deque(maxlen=self.frame_buffer_size)
        self.position_buffer = self.frame_buffer
        
        # State tracking
        self.is_in_cooldown = False
        self.stable_frame_count = 0
        self.last_report = False
    
    def is_stable(self, current_balls: List[Tuple[float, float]]) -> bool:
        """
        Check if all balls are in a stable rest position.
        
        Args:
            current_balls: List of ball center coordinates [(x1, y1), (x2, y2), ...]
        
        Returns:
            True if balls are stable (low displacement over 1 second), False otherwise.
            
        Logic:
            1. Add current frame to buffer
            2. If not enough frames yet, return False
            3. Calculate displacement for each ball across frames
            4. Compute maximum displacement
            5. If maximum displacement < DISPLACEMENT_THRESHOLD:
               - Increment stable_frame_count
               - If stable_frame_count >= STABILITY_DURATION and not in cooldown:
                 - Return True, enter cooldown
            6. If maximum displacement >= MOVEMENT_THRESHOLD and in cooldown:
               - Exit cooldown, reset stable_frame_count
            7. Otherwise reset stable_frame_count
        """
        # Store current frame centers in buffer
        self.frame_buffer.append(current_balls)
        
        # Need at least BUFFER_SIZE frames to make a determination
        if len(self.frame_buffer) < self.frame_buffer_size:
            return False
        
        # Calculate displacement of each ball across the buffer window
        displacements = self._calculate_displacements()
        
        if displacements is None or len(displacements) == 0:
            return False
        
        # Any moving ball should block stability, so use the largest displacement
        # observed in the rolling window instead of the spread across balls.
        max_displacement = float(np.max(displacements))
        
        # --- Stability logic ---
        if max_displacement < self.displacement_threshold:
            # Balls are moving very little
            self.stable_frame_count += 1
            
            if self.stable_frame_count >= self.stable_threshold and not self.is_in_cooldown:
                # Stable for required duration - trigger stable event
                self.is_in_cooldown = True
                self.last_report = True
                return True
        elif max_displacement >= self.movement_threshold and self.is_in_cooldown:
            # Significant movement detected, exit cooldown
            self.is_in_cooldown = False
            self.stable_frame_count = 0
            self.last_report = False
        else:
            # Reset counter for insufficient movement changes
            if max_displacement >= self.displacement_threshold:
                self.stable_frame_count = 0
        
        return False
    
    def _calculate_displacements(self) -> Optional[List[float]]:
        """
        Calculate total displacement for each ball across the buffer.
        
        Returns:
            List of displacements (distance from first frame to last frame),
            or None if buffer is empty.
        """
        if len(self.frame_buffer) == 0:
            return None
        
        first_frame = self.frame_buffer[0]
        last_frame = self.frame_buffer[-1]
        
        # Handle case where ball count differs (shouldn't happen normally)
        if len(first_frame) != len(last_frame):
            return None
        
        displacements = []
        
        # Calculate distance traveled for each ball
        for i in range(len(first_frame)):
            start_pos = first_frame[i]
            end_pos = last_frame[i]
            
            # Euclidean distance
            dx = end_pos[0] - start_pos[0]
            dy = end_pos[1] - start_pos[1]
            distance = float(np.sqrt(dx**2 + dy**2))
            
            displacements.append(distance)
        
        return displacements
    
    def reset(self):
        """Reset the detector to initial state."""
        self.frame_buffer.clear()
        self.is_in_cooldown = False
        self.stable_frame_count = 0
        self.last_report = False

    def reset_all(self):
        """Backward-compatible alias for reset()."""
        self.reset()
    
    def get_state(self) -> dict:
        """
        Get current detector state for debugging.
        
        Returns:
            Dictionary with current state information.
        """
        return {
            'buffer_size': len(self.frame_buffer),
            'is_in_cooldown': self.is_in_cooldown,
            'stable_frame_count': self.stable_frame_count,
            'last_report': self.last_report,
        }
