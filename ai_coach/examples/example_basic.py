"""
Example 1: Basic Static Image Processing

This example demonstrates how to use AI Coach with a static image.
Shows: stabilit detection, semantic conversion, and panel rendering.
"""

import sys
import numpy as np
import cv2
from pathlib import Path
from typing import List, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_coach import (
    StabilityDetector,
    CoordinateSemanticizer,
    draw_coach_panel,
)


def main():
    # Create test image (800x600 white background)
    image = np.ones((600, 800, 3), dtype=np.uint8) * 255
    
    # Add some circles to simulate balls
    cv2.circle(image, (100, 100), 10, (0, 0, 255), -1)  # Red circle
    cv2.circle(image, (150, 150), 10, (0, 255, 0), -1)  # Green circle
    cv2.circle(image, (200, 200), 10, (255, 0, 0), -1)  # Blue circle
    
    print("Processing image...")
    
    # Initialize components
    detector = StabilityDetector(
        displacement_threshold=2.0,
        stable_threshold=5,
        cooldown_frames=30,
    )
    
    semanticizer = CoordinateSemanticizer(
        table_width=800,
        table_height=600,
    )
    
    # Test stability detection
    balls: List[Tuple[float, float]] = [(100, 100), (150, 150), (200, 200)]
    is_stable = detector.is_stable(balls)
    print(f"Ball stability: {is_stable}")
    
    # Test semantic conversion
    semantic = semanticizer.coordinate_to_semantic(100, 100)
    print(f"Position semantic: {semantic}")
    
    # Create advice
    advice_json = {
        "title": "AI Coach Advice",
        "sections": {
            "Observation": f"Balls at {semantic}",
            "Suggestion": "Execute pocket strategy",
            "Next Step": "Aim center pocket",
        }
    }
    
    # Render panel
    result = draw_coach_panel(image, advice_json, alpha=0.6, position="right")
    
    # Display result
    cv2.imshow("AI Coach - Basic Example", result)
    print("\nPress any key to close...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    print("Example completed!")


if __name__ == "__main__":
    main()
