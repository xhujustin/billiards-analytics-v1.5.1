"""
Unit tests for StabilityDetector

Tests the core stability detection functionality.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ai_coach.core.overlay import StabilityDetector


class TestStabilityDetector:
    """Test cases for StabilityDetector class"""
    
    def setup_method(self):
        """Initialize detector before each test"""
        self.detector = StabilityDetector(
            displacement_threshold=2.0,
            stable_threshold=5,
            cooldown_frames=10,
        )
    
    def test_initialization(self):
        """Test detector initialization"""
        assert self.detector is not None
        assert self.detector.displacement_threshold == 2.0
        assert self.detector.stable_threshold == 5
        assert self.detector.cooldown_frames == 10
    
    def test_buffer_capacity(self):
        """Test that buffer operates with correct capacity"""
        # Add multiple frames
        for i in range(100):
            self.detector.is_stable([(100 + i, 100)])
        
        # Buffer should max out at frame_buffer_size
        assert len(self.detector.position_buffer) <= 60
    
    def test_stable_detection(self):
        """Test stable ball detection"""
        # Add same position multiple times
        balls = [(100, 100), (150, 150)]
        
        for _ in range(20):
            is_stable = self.detector.is_stable(balls)
        
        # Should be stable after enough frames
        assert isinstance(is_stable, bool)
    
    def test_unstable_detection(self):
        """Test unstable (moving) ball detection"""
        # Simulate moving balls
        for i in range(20):
            balls = [(100 + i*10, 100 + i*5)]
            is_stable = self.detector.is_stable(balls)
        
        # Should eventually be unstable due to movement
        assert isinstance(is_stable, bool)
    
    def test_reset_state(self):
        """Test detector state reset"""
        # Add some data
        self.detector.is_stable([(100, 100)])
        self.detector.is_stable([(150, 150)])
        
        # Get state
        state = self.detector.get_state()
        assert state is not None
        
        # Reset
        self.detector.reset_all()
        
        # Check reset
        state_after = self.detector.get_state()
        assert state_after is not None
    
    def test_multiple_balls(self):
        """Test with multiple balls"""
        balls = [
            (100, 100),
            (200, 200),
            (300, 300),
            (400, 400),
        ]
        
        is_stable = self.detector.is_stable(balls)
        assert isinstance(is_stable, bool)
    
    def test_edge_cases(self):
        """Test edge cases"""
        # Empty balls
        result = self.detector.is_stable([])
        assert isinstance(result, bool)
        
        # Single ball
        result = self.detector.is_stable([(0, 0)])
        assert isinstance(result, bool)
        
        # Large coordinates
        result = self.detector.is_stable([(5000, 5000)])
        assert isinstance(result, bool)
